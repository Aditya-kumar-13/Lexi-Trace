from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "evaluation"))

from lexitrace.database import Base, build_engine, build_session_factory  # noqa: E402
from lexitrace.semantic import DisabledSemanticEncoder  # noqa: E402
from run_journeys import load_jsonl, metrics, reset_session, run_journey  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate learned ASR reliability against a no-learning ablation."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "data" / "benchmark" / "asr_journeys.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "asr-learning",
    )
    parser.add_argument(
        "--asr-reliability-mode",
        choices=("exact_route", "model_route"),
        default="exact_route",
    )
    return parser.parse_args()


def intervention_curve(rows: list[dict[str, Any]]) -> list[dict[str, float | int]]:
    curve = []
    for threshold in (0.90, 0.92, 0.93, 0.94, 0.96):
        predicted = 0
        correct = 0
        useful_total = sum(row["candidate_expected_useful"] for row in rows)
        for row in rows:
            if not row["candidates"]:
                continue
            candidate = max(row["candidates"], key=lambda item: item["score"])
            would_apply = candidate["score"] >= threshold and not candidate["blockers"]
            predicted += would_apply
            correct += would_apply and row["candidate_expected_useful"]
        curve.append(
            {
                "threshold": threshold,
                "interventions": predicted,
                "precision": round(correct / predicted, 4) if predicted else 1.0,
                "coverage": round(correct / useful_total, 4) if useful_total else 0.0,
            }
        )
    return curve


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Learned ASR reliability journey report",
        "",
        f"Dataset: `{summary['dataset']}`  ",
        f"SHA-256: `{summary['dataset_sha256']}`  ",
        f"Journeys: **{summary['journeys']}**",
        "",
        "| System | Exact output | Action accuracy | Wrong interventions | p95 latency |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, result in summary["systems"].items():
        lines.append(
            f"| {name} | {result['exact_match_rate']:.1%} | "
            f"{result['action_accuracy']:.1%} | {result['wrong_interventions']} | "
            f"{result['p95_latency_ms']:.3f} ms |"
        )
    lines.extend(
        [
            "",
            "## Precision and coverage",
            "",
            "The curve replays the committed chronological labels at alternate apply thresholds. "
            "Training suggestions explicitly confirmed by the user count as useful candidates.",
            "",
            "| Threshold | Interventions | Precision | Useful-candidate coverage |",
            "|---:|---:|---:|---:|",
        ]
    )
    for point in summary["precision_coverage_curve"]:
        lines.append(
            f"| {point['threshold']:.2f} | {point['interventions']} | "
            f"{point['precision']:.1%} | {point['coverage']:.1%} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "The product and ablation receive the same events. Only the learned ASR contribution "
            "is disabled in the ablation. Provider, model, rank, and exact confusion pair are part "
            "of the reliability key, and context blockers remain authoritative. This synthetic "
            "suite demonstrates mechanism and regression safety; it is not a production accuracy "
            "claim.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    dataset = args.dataset.resolve()
    journeys = load_jsonl(dataset)
    systems = {"no_learning_ablation": False, "learned_asr": True}
    all_rows: dict[str, list[dict[str, Any]]] = {}
    database_peaks: dict[str, dict[str, Any]] = {}
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine)
    with session_factory() as session:
        for system_name, enabled in systems.items():
            rows: list[dict[str, Any]] = []
            for journey in journeys:
                reset_session(session)
                rows.extend(
                    run_journey(
                        session,
                        journey,
                        DisabledSemanticEncoder(),
                        enable_learned_asr=enabled,
                        asr_reliability_mode=args.asr_reliability_mode,
                    )
                )
            all_rows[system_name] = rows
            snapshots = [row["database"] for row in rows]
            database_peaks[system_name] = {
                "peak_allocated_bytes": max(item["allocated_bytes"] for item in snapshots),
                "peak_rows": {
                    table: max(item["rows"][table] for item in snapshots)
                    for table in snapshots[0]["rows"]
                },
            }
    engine.dispose()

    summary = {
        "dataset": dataset.relative_to(ROOT).as_posix(),
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "journeys": len(journeys),
        "asr_reliability_mode": args.asr_reliability_mode,
        "systems": {
            name: {**metrics(rows), "database": database_peaks[name]}
            for name, rows in all_rows.items()
        },
        "precision_coverage_curve": intervention_curve(all_rows["learned_asr"]),
        "hosted_requests": 0,
        "estimated_api_cost_usd": 0.0,
    }
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "cases.json").write_text(json.dumps(all_rows, indent=2) + "\n", encoding="utf-8")
    (output / "report.md").write_text(render_report(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nResults: {output}")


if __name__ == "__main__":
    main()
