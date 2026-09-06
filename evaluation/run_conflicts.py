from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from evidence import CountingSemanticEncoder, database_snapshot  # noqa: E402
from lexitrace.database import Base, build_engine, build_session_factory  # noqa: E402
from lexitrace.engine import apply_decision_feedback, infer, teach_explicit  # noqa: E402
from lexitrace.semantic import FastEmbedSemanticEncoder  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay conflict-learning journeys.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "data" / "benchmark" / "conflict_journeys.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "conflicts",
    )
    parser.add_argument("--model", default="BAAI/bge-small-en-v1.5")
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "models"))
    parser.add_argument(
        "--semantic-retrieval-mode",
        choices=("centroid", "nearest_example"),
        default="nearest_example",
    )
    parser.add_argument("--minimum-conflict-positive-context", type=float, default=0.20)
    parser.add_argument(
        "--feedback-scope-mode",
        choices=("legacy", "auto"),
        default="auto",
    )
    parser.add_argument("--semantic-evidence-cap", type=int, default=12)
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if not rows or len({row["journey_id"] for row in rows}) != len(rows):
        raise ValueError("Conflict journeys must be non-empty with unique IDs")
    return rows


def replay(
    journey: dict[str, Any],
    *,
    reverse: bool,
    semantic_encoder,
    semantic_retrieval_mode: str,
    minimum_conflict_positive_context: float,
    feedback_scope_mode: str,
    semantic_evidence_cap: int | None,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="lexitrace-conflict-") as temp_dir:
        url = f"sqlite:///{(Path(temp_dir) / 'conflict.db').as_posix()}"
        engine = build_engine(url)
        Base.metadata.create_all(engine)
        factory = build_session_factory(engine)
        rows: list[dict[str, Any]] = []
        with factory() as session:
            memories = list(journey["memories"])
            if reverse:
                memories.reverse()
            for item in memories:
                teach_explicit(
                    session,
                    user_id="conflict-user",
                    canonical_form=item["canonical_form"],
                    variants=item["variants"],
                    scope_mode=item.get("scope_mode", "global"),
                    positive_context=[],
                    negative_context=[],
                    formatted_text=item.get("source_formatted", ""),
                    accepted_text=item.get("source_accepted", ""),
                    semantic_encoder=semantic_encoder,
                    semantic_evidence_cap=semantic_evidence_cap,
                )
            for index, event in enumerate(journey["events"]):
                _, response = infer(
                    session,
                    user_id="conflict-user",
                    raw_asr_text="",
                    formatted_text=event["formatted_text"],
                    semantic_encoder=semantic_encoder,
                    semantic_retrieval_mode=semantic_retrieval_mode,
                    minimum_conflict_positive_context=minimum_conflict_positive_context,
                )
                exact = response["memory_aware_text"] == event["expected_output"]
                action_matches = response["action"] == event["expected_action"]
                if event.get("feedback_canonical"):
                    target = next(
                        candidate
                        for candidate in response["candidates"]
                        if candidate["canonical_form"] == event["feedback_canonical"]
                    )
                    apply_decision_feedback(
                        session,
                        trace_id=response["trace_id"],
                        verdict="correct",
                        feedback_scope=feedback_scope_mode,
                        corrected_text=event["expected_output"],
                        suppress_memories=False,
                        candidate_memory_id=target["memory_id"],
                        candidate_start=target["start"],
                        semantic_encoder=semantic_encoder,
                        semantic_evidence_cap=semantic_evidence_cap,
                    )
                rows.append(
                    {
                        "event_index": index,
                        "input": event["formatted_text"],
                        "expected_output": event["expected_output"],
                        "expected_action": event["expected_action"],
                        "actual_output": response["memory_aware_text"],
                        "actual_action": response["action"],
                        "exact": exact,
                        "action_matches": action_matches,
                        "wrong_intervention": (
                            response["memory_aware_text"] != event["formatted_text"] and not exact
                        ),
                        "candidates": response["candidates"],
                    }
                )
            storage = database_snapshot(session)
        engine.dispose()
    return {"events": rows, "database": storage}


def main() -> None:
    args = parse_args()
    dataset = args.dataset.resolve()
    output = args.output.resolve()
    journeys = load_jsonl(dataset)
    encoder = CountingSemanticEncoder(FastEmbedSemanticEncoder(args.model, args.cache_dir))
    cases: list[dict[str, Any]] = []
    for journey in journeys:
        replay_options = {
            "semantic_encoder": encoder,
            "semantic_retrieval_mode": args.semantic_retrieval_mode,
            "minimum_conflict_positive_context": args.minimum_conflict_positive_context,
            "feedback_scope_mode": args.feedback_scope_mode,
            "semantic_evidence_cap": args.semantic_evidence_cap,
        }
        normal = replay(journey, reverse=False, **replay_options)
        reversed_order = replay(journey, reverse=True, **replay_options)
        deterministic = [
            (event["actual_output"], event["actual_action"]) for event in normal["events"]
        ] == [
            (event["actual_output"], event["actual_action"]) for event in reversed_order["events"]
        ]
        cases.append(
            {
                "journey_id": journey["journey_id"],
                "normal": normal,
                "reversed": reversed_order,
                "insertion_order_deterministic": deterministic,
            }
        )

    events = [event for case in cases for event in case["normal"]["events"]]
    summary = {
        "dataset": dataset.relative_to(ROOT).as_posix(),
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "journeys": len(journeys),
        "semantic_retrieval_mode": args.semantic_retrieval_mode,
        "minimum_conflict_positive_context": args.minimum_conflict_positive_context,
        "feedback_scope_mode": args.feedback_scope_mode,
        "semantic_evidence_cap": args.semantic_evidence_cap,
        "events": len(events),
        "exact_match_rate": round(sum(event["exact"] for event in events) / len(events), 4),
        "action_accuracy": round(sum(event["action_matches"] for event in events) / len(events), 4),
        "wrong_interventions": sum(event["wrong_intervention"] for event in events),
        "deterministic_journeys": sum(case["insertion_order_deterministic"] for case in cases),
        "model_usage": encoder.usage(),
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "cases.json").write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    report = "\n".join(
        [
            "# Conflict-learning evaluation",
            "",
            f"Journeys: **{summary['journeys']}**",
            f"Events: **{summary['events']}**",
            f"Exact output: **{summary['exact_match_rate']:.1%}**",
            f"Action accuracy: **{summary['action_accuracy']:.1%}**",
            f"Wrong interventions: **{summary['wrong_interventions']}**",
            f"Insertion-order deterministic: **{summary['deterministic_journeys']}/{len(cases)}**",
            "",
        ]
    )
    (output / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
