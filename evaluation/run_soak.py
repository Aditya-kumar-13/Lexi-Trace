from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from evidence import database_snapshot  # noqa: E402
from lexitrace.database import Base, build_engine, build_session_factory  # noqa: E402
from lexitrace.engine import infer, teach_explicit  # noqa: E402
from lexitrace.semantic import DisabledSemanticEncoder  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Measure sustained local decision behavior.")
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--output", type=Path, default=ROOT / "results" / "soak")
    return parser.parse_args()


def percentile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * quantile))
    return ordered[index]


def main() -> None:
    args = parse_args()
    if args.iterations < 1:
        raise ValueError("iterations must be positive")
    encoder = DisabledSemanticEncoder()
    scenarios = [
        ("Ask Aditya to review the Kiwi deployment.", "Ask Aaditya to review the Kivi deployment."),
        ("The ordinary document is ready.", "The ordinary document is ready."),
        ("Kivi sent the report to Aaditya.", "Kivi sent the report to Aaditya."),
    ]
    latencies: list[float] = []
    trace_ids: set[str] = set()
    failures: list[dict] = []
    with tempfile.TemporaryDirectory(prefix="lexitrace-soak-") as temp_dir:
        url = f"sqlite:///{(Path(temp_dir) / 'soak.db').as_posix()}"
        engine = build_engine(url)
        Base.metadata.create_all(engine)
        factory = build_session_factory(engine)
        with factory() as session:
            for canonical, variant in (("Kivi", "Kiwi"), ("Aaditya", "Aditya")):
                teach_explicit(
                    session,
                    user_id="soak-user",
                    canonical_form=canonical,
                    variants=[variant],
                    scope_mode="global",
                    positive_context=[],
                    negative_context=[],
                    semantic_encoder=encoder,
                )
            before = database_snapshot(session)
            for index in range(args.iterations):
                formatted_text, expected = scenarios[index % len(scenarios)]
                _, response = infer(
                    session,
                    user_id="soak-user",
                    raw_asr_text="",
                    formatted_text=formatted_text,
                    semantic_encoder=encoder,
                )
                latencies.append(response["total_latency_ms"])
                trace_ids.add(response["trace_id"])
                if response["memory_aware_text"] != expected:
                    failures.append(
                        {
                            "iteration": index,
                            "expected": expected,
                            "actual": response["memory_aware_text"],
                        }
                    )
            after = database_snapshot(session)
        engine.dispose()

    summary = {
        "iterations": args.iterations,
        "unique_traces": len(trace_ids),
        "failures": len(failures),
        "latency_ms": {
            "mean": round(statistics.fmean(latencies), 3),
            "p50": round(percentile(latencies, 0.50), 3),
            "p95": round(percentile(latencies, 0.95), 3),
            "p99": round(percentile(latencies, 0.99), 3),
        },
        "database": {
            "before_bytes": before["allocated_bytes"],
            "after_bytes": after["allocated_bytes"],
            "growth_bytes": after["allocated_bytes"] - before["allocated_bytes"],
            "rows": after["rows"],
        },
        "hosted_requests": 0,
        "estimated_api_cost_usd": 0.0,
    }
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "failures.json").write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
    report = "\n".join(
        [
            "# Local soak report",
            "",
            f"Decisions: **{args.iterations}**",
            f"Unique traces: **{len(trace_ids)}**",
            f"Failures: **{len(failures)}**",
            f"p95 latency: **{summary['latency_ms']['p95']:.3f} ms**",
            f"Database growth: **{summary['database']['growth_bytes']} bytes**",
            "Hosted requests: **0**",
            "",
        ]
    )
    (output / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
