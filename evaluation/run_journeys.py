from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import delete

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from evidence import (  # noqa: E402
    CountingSemanticEncoder,
    database_snapshot,
    memory_state_snapshot,
)
from lexitrace.database import Base, build_engine, build_session_factory  # noqa: E402
from lexitrace.engine import (  # noqa: E402
    apply_decision_feedback,
    apply_memory_state_override,
    infer,
    observe_correction,
    teach_explicit,
)
from lexitrace.models import Decision, Memory, Observation  # noqa: E402
from lexitrace.semantic import (  # noqa: E402
    DisabledSemanticEncoder,
    FastEmbedSemanticEncoder,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run chronological hybrid-context journeys and the sparse ablation."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "data" / "benchmark" / "journeys.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "journeys",
    )
    parser.add_argument("--model", default="BAAI/bge-small-en-v1.5")
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "models"))
    parser.add_argument(
        "--semantic-retrieval-mode",
        choices=("centroid", "nearest_example"),
        default="centroid",
    )
    parser.add_argument(
        "--disable-auto-lifecycle",
        action="store_true",
        help="Keep memory state fixed while still recording feedback evidence.",
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    journeys = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not journeys:
        raise ValueError(f"Journey dataset is empty: {path}")
    return journeys


def reset_session(session) -> None:
    session.execute(delete(Decision))
    session.execute(delete(Observation))
    session.execute(delete(Memory))
    session.commit()


def run_journey(
    session,
    journey: dict[str, Any],
    encoder,
    *,
    enable_learned_asr: bool = True,
    semantic_retrieval_mode: str = "centroid",
    enable_auto_lifecycle: bool = True,
) -> list[dict[str, Any]]:
    memories: dict[str, str] = {}
    rows: list[dict[str, Any]] = []
    for event_index, event in enumerate(journey["events"], 1):
        event_type = event["type"]
        if event_type == "teach":
            memory = teach_explicit(
                session,
                user_id="journey-user",
                canonical_form=event["canonical_form"],
                variants=event["variants"],
                scope_mode=event.get("scope_mode", "global"),
                positive_context=event.get("positive_context", []),
                negative_context=event.get("negative_context", []),
                formatted_text=event.get("formatted_text", ""),
                accepted_text=event.get("accepted_text", ""),
                event_id=event.get("event_id"),
                semantic_encoder=encoder,
            )
            memories[event["alias"]] = memory.id
            continue
        if event_type == "confirm":
            memory = session.get(Memory, memories[event["alias"]])
            apply_memory_state_override(session, memory=memory, state="confirmed")
            session.commit()
            continue
        if event_type == "correction":
            observe_correction(
                session,
                user_id="journey-user",
                raw_asr_text=event.get("raw_asr_text", ""),
                formatted_text=event["formatted_text"],
                accepted_text=event["accepted_text"],
                confirm_candidates=False,
                event_id=event.get("event_id"),
                semantic_encoder=encoder,
            )
            continue
        if event_type != "infer":
            raise ValueError(f"Unsupported journey event: {event_type}")

        _, response = infer(
            session,
            user_id="journey-user",
            raw_asr_text="",
            formatted_text=event["formatted_text"],
            alternatives=event.get("alternatives", []),
            asr=event.get("asr"),
            enable_learned_asr=enable_learned_asr,
            semantic_encoder=encoder,
            semantic_retrieval_mode=semantic_retrieval_mode,
        )
        row = {
            "journey_id": journey["journey_id"],
            "event_index": event_index,
            "formatted_text": event["formatted_text"],
            "expected_output": event["expected_output"],
            "actual_output": response["memory_aware_text"],
            "expected_action": event["expected_action"],
            "actual_action": response["action"],
            "exact": response["memory_aware_text"] == event["expected_output"],
            "action_matches": response["action"] == event["expected_action"],
            "latency_ms": response["total_latency_ms"],
            "trace_id": response["trace_id"],
            "candidates": response["candidates"],
            "inputs": {
                "raw_asr_text": event.get("raw_asr_text", ""),
                "formatted_text": event["formatted_text"],
                "alternatives": event.get("alternatives", []),
                "asr": event.get("asr"),
            },
            "expected": {
                "output": event["expected_output"],
                "action": event["expected_action"],
            },
            "memory_state": memory_state_snapshot(session),
            "database": database_snapshot(session),
            "feedback": event.get("feedback"),
            "candidate_expected_useful": (
                event.get("feedback") == "correct"
                or event["expected_output"] != event["formatted_text"]
            ),
            "score_case": event.get("score_case", True),
        }
        rows.append(row)
        if event.get("feedback"):
            apply_decision_feedback(
                session,
                trace_id=response["trace_id"],
                verdict=event["feedback"],
                corrected_text=event["formatted_text"],
                suppress_memories=False,
                candidate_memory_id=(
                    memories[event["feedback_target"]] if event.get("feedback_target") else None
                ),
                semantic_encoder=encoder,
                enable_auto_lifecycle=enable_auto_lifecycle,
            )
    return rows


def metrics(rows: list[dict[str, Any]]) -> dict[str, float | int]:
    rows = [row for row in rows if row["score_case"]]
    if not rows:
        raise ValueError("Journey dataset has no scored inference events")
    wrong_interventions = sum(
        row["actual_output"] != row["formatted_text"] and not row["exact"] for row in rows
    )
    latencies = sorted(float(row["latency_ms"]) for row in rows)
    p95_index = min(len(latencies) - 1, round((len(latencies) - 1) * 0.95))
    return {
        "queries": len(rows),
        "exact_match_rate": round(sum(row["exact"] for row in rows) / len(rows), 4),
        "action_accuracy": round(sum(row["action_matches"] for row in rows) / len(rows), 4),
        "wrong_interventions": wrong_interventions,
        "mean_latency_ms": round(sum(latencies) / len(latencies), 3),
        "p95_latency_ms": round(latencies[p95_index], 3),
    }


def render_report(summary: dict[str, Any], rows: dict[str, list[dict[str, Any]]]) -> str:
    lines = [
        "# LexiTrace chronological journey report",
        "",
        f"Dataset: `{summary['dataset']}`",
        f"SHA-256: `{summary['dataset_sha256']}`",
        f"Local model: `{summary['model']}`",
        f"Journeys: **{summary['journeys']}**",
        "",
        "| System | Query exact match | Action accuracy | Wrong interventions | p95 latency |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, result in summary["systems"].items():
        lines.append(
            f"| {name} | {result['exact_match_rate']:.1%} | "
            f"{result['action_accuracy']:.1%} | {result['wrong_interventions']} | "
            f"{result['p95_latency_ms']:.3f} ms |"
        )
    lines.extend(["", "## Operational accounting", ""])
    for name, result in summary["systems"].items():
        usage = result["model_usage"]
        database = result["database"]
        lines.extend(
            [
                f"### {name}",
                "",
                f"- Embedding execution: **{usage['execution']}**",
                f"- Embedding calls: **{usage['embedding_calls']}**",
                f"- Embedded input characters: **{usage['input_characters']}**",
                f"- Hosted requests: **{usage['hosted_requests']}**",
                f"- Estimated API cost: **${usage['estimated_api_cost_usd']:.2f}**",
                f"- Peak allocated SQLite bytes: **{database['peak_allocated_bytes']}**",
                f"- Peak vector payload bytes: **{database['peak_vector_payload_bytes']}**",
                "",
            ]
        )
    sparse_failures = [
        row for row in rows["sparse_ablation"] if not row["exact"] or not row["action_matches"]
    ]
    lines.extend(
        [
            "",
            "## Ablation differences",
            "",
            "| Journey | Expected action | Sparse action |",
            "|---|---|---|",
        ]
    )
    for row in sparse_failures:
        lines.append(f"| {row['journey_id']} | {row['expected_action']} | {row['actual_action']} |")
    hybrid_failures = [
        row for row in rows["hybrid"] if not row["exact"] or not row["action_matches"]
    ]
    lines.extend(["", "## Hybrid failures", ""])
    if not hybrid_failures:
        lines.append("No hybrid failures in this compact development suite.")
    else:
        lines.extend(
            [
                "| Journey | Expected output | Actual output | Expected action | Actual action |",
                "|---|---|---|---|---|",
            ]
        )
        for row in hybrid_failures:
            lines.append(
                f"| {row['journey_id']} | {row['expected_output']} | {row['actual_output']} | "
                f"{row['expected_action']} | {row['actual_action']} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Events are executed in chronological order against an initially empty database. "
            "The hybrid system and sparse ablation receive identical teaching, correction, "
            "inference, and feedback events. This compact development suite demonstrates the "
            "mechanisms; it is not an external claim of production accuracy.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    dataset = args.dataset.resolve()
    journeys = load_jsonl(dataset)
    systems = {
        "sparse_ablation": CountingSemanticEncoder(DisabledSemanticEncoder()),
        "hybrid": CountingSemanticEncoder(FastEmbedSemanticEncoder(args.model, args.cache_dir)),
    }
    all_rows: dict[str, list[dict[str, Any]]] = {}
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine)
    with session_factory() as session:
        for system_name, encoder in systems.items():
            system_rows: list[dict[str, Any]] = []
            for journey in journeys:
                reset_session(session)
                system_rows.extend(
                    run_journey(
                        session,
                        journey,
                        encoder,
                        semantic_retrieval_mode=args.semantic_retrieval_mode,
                        enable_auto_lifecycle=not args.disable_auto_lifecycle,
                    )
                )
            all_rows[system_name] = system_rows
    engine.dispose()

    summary = {
        "dataset": dataset.relative_to(ROOT).as_posix(),
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "journeys": len(journeys),
        "model": args.model,
        "semantic_retrieval_mode": args.semantic_retrieval_mode,
        "auto_lifecycle_enabled": not args.disable_auto_lifecycle,
        "systems": {
            name: {
                **metrics(rows),
                "model_usage": systems[name].usage(),
                "database": {
                    "peak_allocated_bytes": max(row["database"]["allocated_bytes"] for row in rows),
                    "peak_vector_payload_bytes": max(
                        row["database"]["vector_payload_bytes"] for row in rows
                    ),
                    "peak_rows": {
                        table: max(row["database"]["rows"][table] for row in rows)
                        for table in rows[0]["database"]["rows"]
                    },
                },
            }
            for name, rows in all_rows.items()
        },
    }
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "cases.json").write_text(json.dumps(all_rows, indent=2) + "\n", encoding="utf-8")
    (output / "report.md").write_text(render_report(summary, all_rows), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nResults: {output}")


if __name__ == "__main__":
    main()
