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

from lexitrace.database import Base, build_engine, build_session_factory  # noqa: E402
from lexitrace.engine import (  # noqa: E402
    apply_decision_feedback,
    apply_memory_state_override,
    infer,
    memory_trust_profile,
    observe_correction,
    teach_explicit,
)
from lexitrace.models import Decision, Memory, Observation  # noqa: E402
from lexitrace.semantic import DisabledSemanticEncoder  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the event-derived memory lifecycle against a no-lifecycle ablation."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "data" / "benchmark" / "lifecycle_journeys.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "lifecycle",
    )
    parser.add_argument(
        "--feedback-scope-mode",
        choices=("legacy", "auto"),
        default="auto",
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def reset_session(session) -> None:
    session.execute(delete(Decision))
    session.execute(delete(Observation))
    session.execute(delete(Memory))
    session.commit()


def run_journey(
    session,
    journey: dict[str, Any],
    *,
    enabled: bool,
    feedback_scope_mode: str = "auto",
) -> list[dict[str, Any]]:
    encoder = DisabledSemanticEncoder()
    aliases: dict[str, str] = {}
    rows = []
    for index, event in enumerate(journey["events"], 1):
        event_type = event["type"]
        response: dict[str, Any] | None = None
        if event_type == "teach":
            memory = teach_explicit(
                session,
                user_id="lifecycle-user",
                canonical_form=event["canonical_form"],
                variants=event["variants"],
                scope_mode=event.get("scope_mode", "global"),
                positive_context=[],
                negative_context=[],
                event_id=event.get("event_id"),
                semantic_encoder=encoder,
            )
            aliases[event["alias"]] = memory.id
        elif event_type == "correct":
            _, memory_ids, _ = observe_correction(
                session,
                user_id="lifecycle-user",
                raw_asr_text="",
                formatted_text=event["formatted_text"],
                accepted_text=event["accepted_text"],
                confirm_candidates=False,
                event_id=event.get("event_id"),
                semantic_encoder=encoder,
                enable_auto_lifecycle=enabled,
            )
            if event["alias"] not in aliases:
                aliases[event["alias"]] = memory_ids[0]
        elif event_type == "state":
            memory = session.get(Memory, aliases[event["alias"]])
            apply_memory_state_override(session, memory=memory, state=event["state"])
            session.commit()
        elif event_type == "infer":
            _, response = infer(
                session,
                user_id="lifecycle-user",
                raw_asr_text="",
                formatted_text=event["formatted_text"],
                semantic_encoder=encoder,
            )
            if event.get("feedback"):
                apply_decision_feedback(
                    session,
                    trace_id=response["trace_id"],
                    verdict=event["feedback"],
                    feedback_scope=feedback_scope_mode,
                    corrected_text=event["formatted_text"],
                    suppress_memories=False,
                    semantic_encoder=encoder,
                    enable_auto_lifecycle=enabled,
                )
        else:
            raise ValueError(f"Unsupported event type: {event_type}")

        memory = session.get(Memory, aliases[event["alias"]])
        trust = memory_trust_profile(memory)
        checks = {
            "state": memory.state == event.get("expected_state", memory.state),
            "positive_events": trust["positive_events"]
            == event.get("expected_positive_events", trust["positive_events"]),
            "negative_events": trust["negative_events"]
            == event.get("expected_negative_events", trust["negative_events"]),
            "distinct_contexts": trust["distinct_contexts"]
            == event.get("expected_distinct_contexts", trust["distinct_contexts"]),
        }
        if response is not None:
            checks["output"] = response["memory_aware_text"] == event["expected_output"]
            checks["action"] = response["action"] == event["expected_action"]
        rows.append(
            {
                "journey_id": journey["journey_id"],
                "event_index": index,
                "event": event,
                "actual_state": memory.state,
                "trust_profile": trust,
                "inference": response,
                "checks": checks,
                "exact": all(checks.values()),
            }
        )
    return rows


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    query_rows = [row for row in rows if row["inference"] is not None]
    wrong_interventions = sum(
        row["inference"]["memory_aware_text"] != row["event"]["formatted_text"]
        and row["inference"]["memory_aware_text"] != row["event"]["expected_output"]
        for row in query_rows
    )
    return {
        "events": len(rows),
        "event_accuracy": round(sum(row["exact"] for row in rows) / len(rows), 4),
        "failed_events": sum(not row["exact"] for row in rows),
        "wrong_interventions": wrong_interventions,
    }


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Memory lifecycle journey report",
        "",
        f"Dataset: `{summary['dataset']}`  ",
        f"SHA-256: `{summary['dataset_sha256']}`  ",
        f"Journeys: **{summary['journeys']}**",
        "",
        "| System | Event accuracy | Failed events | Wrong interventions |",
        "|---|---:|---:|---:|",
    ]
    for name, result in summary["systems"].items():
        lines.append(
            f"| {name} | {result['event_accuracy']:.1%} | "
            f"{result['failed_events']} | {result['wrong_interventions']} |"
        )
    lines.extend(
        [
            "",
            "The ablation receives and stores the same observations, but automatic promotion and "
            "demotion are disabled. Explicit teaching and suppression remain user-authorized in "
            "both systems. Every assertion and posterior component is retained in `cases.json`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    dataset = args.dataset.resolve()
    journeys = load_jsonl(dataset)
    engine = build_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine)
    all_rows = {}
    with session_factory() as session:
        for name, enabled in {"no_lifecycle_ablation": False, "event_lifecycle": True}.items():
            rows = []
            for journey in journeys:
                reset_session(session)
                rows.extend(
                    run_journey(
                        session,
                        journey,
                        enabled=enabled,
                        feedback_scope_mode=args.feedback_scope_mode,
                    )
                )
            all_rows[name] = rows
    engine.dispose()
    summary = {
        "dataset": dataset.relative_to(ROOT).as_posix(),
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "journeys": len(journeys),
        "feedback_scope_mode": args.feedback_scope_mode,
        "systems": {name: metrics(rows) for name, rows in all_rows.items()},
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
