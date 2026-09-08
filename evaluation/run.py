from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
import tempfile
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
from lexitrace.engine import infer, teach_explicit  # noqa: E402
from lexitrace.models import Decision, Memory, Observation  # noqa: E402
from lexitrace.semantic import (  # noqa: E402
    DisabledSemanticEncoder,
    FastEmbedSemanticEncoder,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the reproducible LexiTrace benchmark.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "data" / "benchmark" / "smoke.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "latest",
    )
    parser.add_argument("--model", default="BAAI/bge-small-en-v1.5")
    parser.add_argument("--cache-dir", default=str(ROOT / "data" / "models"))
    parser.add_argument(
        "--disable-semantic",
        action="store_true",
        help="Run the deterministic sparse ablation instead of the default hybrid product.",
    )
    parser.add_argument(
        "--asr-confidence-mode",
        choices=("legacy_double", "single_path"),
        default="legacy_double",
    )
    parser.add_argument(
        "--semantic-retrieval-mode",
        choices=("centroid", "nearest_example"),
        default="nearest_example",
    )
    parser.add_argument(
        "--minimum-conflict-positive-context",
        type=float,
        default=0.20,
    )
    parser.add_argument(
        "--authorization-score-mode",
        choices=("boolean", "posterior"),
        default="boolean",
    )
    return parser.parse_args()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"Invalid JSON on {path}:{line_number}: {error}") from error
            required = {
                "case_id",
                "category",
                "memories",
                "formatted_text",
                "expected_output",
                "expected_action",
            }
            missing = required - case.keys()
            if missing:
                raise ValueError(f"{path}:{line_number} is missing {sorted(missing)}")
            cases.append(case)
    if not cases:
        raise ValueError(f"Dataset is empty: {path}")
    case_ids = [case["case_id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Dataset contains duplicate case_id values")
    return cases


def reset_session(session) -> None:
    session.execute(delete(Decision))
    session.execute(delete(Observation))
    session.execute(delete(Memory))
    session.commit()


def seed_case(session, case: dict[str, Any], semantic_encoder) -> None:
    for item in case["memories"]:
        memory = teach_explicit(
            session,
            user_id=case.get("user_id", "benchmark-user"),
            canonical_form=item["canonical_form"],
            variants=item["variants"],
            scope_mode=item.get("scope_mode", "global"),
            positive_context=item.get("positive_context", []),
            negative_context=item.get("negative_context", []),
            formatted_text=item.get("source_formatted", ""),
            accepted_text=item.get("source_accepted", ""),
            semantic_encoder=semantic_encoder,
        )
        memory.state = item.get("state", "confirmed")
        session.commit()


def replace_phrase(text: str, variant: str, canonical: str) -> str:
    escaped = re.escape(variant).replace(r"\ ", r"\s+")
    return re.sub(
        rf"(?<!\w){escaped}(?!\w)",
        lambda _match: canonical,
        text,
        flags=re.IGNORECASE | re.UNICODE,
    )


def no_memory(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "output": case["formatted_text"],
        "action": "abstain",
        "latency_ms": 0.0,
        "trace_id": None,
    }


def naive_dictionary(case: dict[str, Any]) -> dict[str, Any]:
    output = case["formatted_text"]
    for memory in case["memories"]:
        for variant in memory["variants"]:
            output = replace_phrase(output, variant, memory["canonical_form"])
    return {
        "output": output,
        "action": "apply" if output != case["formatted_text"] else "abstain",
        "latency_ms": 0.0,
        "trace_id": None,
    }


def full_system(
    session,
    case: dict[str, Any],
    semantic_encoder,
    asr_confidence_mode: str = "legacy_double",
    semantic_retrieval_mode: str = "nearest_example",
    minimum_conflict_positive_context: float = 0.20,
    authorization_score_mode: str = "boolean",
) -> dict[str, Any]:
    _, response = infer(
        session,
        user_id=case.get("user_id", "benchmark-user"),
        raw_asr_text=case.get("raw_asr_text", ""),
        formatted_text=case["formatted_text"],
        alternatives=case.get("alternatives", []),
        asr=case.get("asr"),
        semantic_encoder=semantic_encoder,
        asr_confidence_mode=asr_confidence_mode,
        semantic_retrieval_mode=semantic_retrieval_mode,
        minimum_conflict_positive_context=minimum_conflict_positive_context,
        authorization_score_mode=authorization_score_mode,
    )
    return {
        "output": response["memory_aware_text"],
        "action": response["action"],
        "latency_ms": response["total_latency_ms"],
        "trace_id": response["trace_id"],
        "candidates": response["candidates"],
        "candidate_generation": response["candidate_generation"],
        "policy_version": response["policy_version"],
        "semantic": response["semantic"],
    }


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return ordered[index]


def calculate_metrics(rows: list[dict[str, Any]], system: str) -> dict[str, Any]:
    results = [row["systems"][system] for row in rows]
    required = [row["expected_output"] != row["formatted_text"] for row in rows]
    exact = [
        result["output"] == row["expected_output"]
        for row, result in zip(rows, results, strict=True)
    ]
    changed = [
        result["output"] != row["formatted_text"] for row, result in zip(rows, results, strict=True)
    ]
    useful = [is_changed and is_exact for is_changed, is_exact in zip(changed, exact, strict=True)]
    required_correct = [
        is_required and is_exact for is_required, is_exact in zip(required, exact, strict=True)
    ]
    no_change_correct = [
        (not is_required) and is_exact
        for is_required, is_exact in zip(required, exact, strict=True)
    ]
    wrong_interventions = [
        is_changed and not is_exact for is_changed, is_exact in zip(changed, exact, strict=True)
    ]
    latencies = [float(result["latency_ms"]) for result in results]
    action_matches = [
        result["action"] == row["expected_action"]
        for row, result in zip(rows, results, strict=True)
    ]

    interventions = sum(changed)
    required_count = sum(required)
    no_change_count = len(rows) - required_count
    return {
        "cases": len(rows),
        "exact_matches": sum(exact),
        "exact_match_rate": round(sum(exact) / len(rows), 4),
        "action_accuracy": round(sum(action_matches) / len(rows), 4),
        "interventions": interventions,
        "useful_interventions": sum(useful),
        "wrong_interventions": sum(wrong_interventions),
        "intervention_precision": round(sum(useful) / interventions, 4) if interventions else None,
        "intervention_recall": round(sum(required_correct) / required_count, 4)
        if required_count
        else None,
        "incorrect_intervention_rate": round(sum(wrong_interventions) / len(rows), 4),
        "abstention_accuracy": round(sum(no_change_correct) / no_change_count, 4)
        if no_change_count
        else None,
        "latency_ms": {
            "mean": round(statistics.fmean(latencies), 3),
            "p50": round(percentile(latencies, 0.50), 3),
            "p95": round(percentile(latencies, 0.95), 3),
            "p99": round(percentile(latencies, 0.99), 3),
        },
    }


def render_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# LexiTrace benchmark report",
        "",
        f"Dataset: `{summary['dataset']}`",
        f"SHA-256: `{summary['dataset_sha256']}`",
        f"Cases: **{summary['case_count']}**",
        "",
        "## System comparison",
        "",
        "| System | Exact match | Action accuracy | Precision | Recall | "
        "Incorrect interventions | p95 latency |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for system, metrics in summary["systems"].items():
        precision = metrics["intervention_precision"]
        recall = metrics["intervention_recall"]
        lines.append(
            "| {system} | {exact:.1%} | {action:.1%} | {precision} | {recall} | {incorrect:.1%} | "
            "{latency:.3f} ms |".format(
                system=system,
                exact=metrics["exact_match_rate"],
                action=metrics["action_accuracy"],
                precision="n/a" if precision is None else f"{precision:.1%}",
                recall="n/a" if recall is None else f"{recall:.1%}",
                incorrect=metrics["incorrect_intervention_rate"],
                latency=metrics["latency_ms"]["p95"],
            )
        )

    usage = summary["model_usage"]
    database = summary["database"]
    lines.extend(
        [
            "",
            "## Operational accounting",
            "",
            f"- Embedding execution: **{usage['execution']}**",
            f"- Embedding calls: **{usage['embedding_calls']}**",
            f"- Hosted model requests: **{usage['hosted_requests']}**",
            f"- Estimated API cost: **${usage['estimated_api_cost_usd']:.2f}**",
            f"- Peak allocated SQLite bytes: **{database['peak_allocated_bytes']}**",
            f"- Peak persisted trace payload bytes: **{database['peak_trace_payload_bytes']}**",
        ]
    )
    if set(summary["split_counts"]) != {"all"}:
        lines.extend(
            [
                "",
                "## Predeclared split results",
                "",
                "| Split | Cases | Exact match | Action accuracy | Wrong interventions |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for split, count in summary["split_counts"].items():
            split_metrics = summary["lexitrace_by_split"][split]
            lines.append(
                f"| {split} | {count} | {split_metrics['exact_match_rate']:.1%} | "
                f"{split_metrics['action_accuracy']:.1%} | "
                f"{split_metrics['wrong_interventions']} |"
            )

    failures = [
        row
        for row in rows
        if not row["systems"]["lexitrace"]["exact"]
        or not row["systems"]["lexitrace"]["action_matches"]
    ]
    lines.extend(["", "## LexiTrace failures", ""])
    if not failures:
        lines.append("No failures in this benchmark.")
    else:
        lines.extend(
            [
                "| Case | Category | Expected | Actual | Action |",
                "|---|---|---|---|---|",
            ]
        )
        for row in failures:
            actual = row["systems"]["lexitrace"]
            lines.append(
                f"| {row['case_id']} | {row['category']} | {row['expected_output']} | "
                f"{actual['output']} | {actual['action']} |"
            )
    split_names = set(summary["split_counts"])
    if split_names == {"adversarial_discovery"}:
        interpretation = (
            "This is a bounded adversarial discovery suite, not a held-out or production-accuracy "
            "claim. Its complete case-level results remain visible for regression and review."
        )
    elif split_names == {"calibration", "heldout"}:
        interpretation = (
            "This is a fixed synthetic robustness suite with historical calibration/held-out "
            "labels. Both partitions are known regression evidence for v7; all failures remain "
            "visible, and no external or production-accuracy claim is made."
        )
    else:
        interpretation = (
            "This is the north-star smoke suite, not a production-accuracy claim. Contextual "
            "cases are initialized from observed correction sentences rather than source-code "
            "keyword gates."
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            interpretation,
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    dataset_path = args.dataset.resolve()
    output_path = args.output.resolve()
    cases = load_jsonl(dataset_path)
    dataset_hash = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    rows: list[dict[str, Any]] = []
    base_encoder = (
        DisabledSemanticEncoder()
        if args.disable_semantic
        else FastEmbedSemanticEncoder(args.model, args.cache_dir)
    )
    semantic_encoder = CountingSemanticEncoder(base_encoder)

    with tempfile.TemporaryDirectory(prefix="lexitrace-eval-") as temp_dir:
        database_url = f"sqlite:///{(Path(temp_dir) / 'evaluation.db').as_posix()}"
        engine = build_engine(database_url)
        Base.metadata.create_all(engine)
        session_factory = build_session_factory(engine)
        with session_factory() as session:
            for case in cases:
                reset_session(session)
                seed_case(session, case, semantic_encoder)
                systems: dict[str, dict[str, Any]] = {
                    "no_memory": no_memory(case),
                    "naive_dictionary": naive_dictionary(case),
                    "lexitrace": full_system(
                        session,
                        case,
                        semantic_encoder,
                        args.asr_confidence_mode,
                        args.semantic_retrieval_mode,
                        args.minimum_conflict_positive_context,
                        args.authorization_score_mode,
                    ),
                }
                for result in systems.values():
                    result["exact"] = result["output"] == case["expected_output"]
                    result["action_matches"] = result["action"] == case["expected_action"]
                memory_state = memory_state_snapshot(session)
                storage = database_snapshot(session)
                rows.append(
                    {
                        "case_id": case["case_id"],
                        "category": case["category"],
                        "split": case.get("split", "all"),
                        "inputs": {
                            "raw_asr_text": case.get("raw_asr_text", ""),
                            "formatted_text": case["formatted_text"],
                            "alternatives": case.get("alternatives", []),
                        },
                        "formatted_text": case["formatted_text"],
                        "expected": {
                            "output": case["expected_output"],
                            "action": case["expected_action"],
                        },
                        "expected_output": case["expected_output"],
                        "expected_action": case["expected_action"],
                        "memory_state": memory_state,
                        "database": storage,
                        "systems": systems,
                    }
                )
        engine.dispose()

    system_names = ("no_memory", "naive_dictionary", "lexitrace")
    split_names = sorted({row["split"] for row in rows})
    summary = {
        "dataset": dataset_path.relative_to(ROOT).as_posix()
        if dataset_path.is_relative_to(ROOT)
        else str(dataset_path),
        "dataset_sha256": dataset_hash,
        "case_count": len(cases),
        "minimum_conflict_positive_context": args.minimum_conflict_positive_context,
        "authorization_score_mode": args.authorization_score_mode,
        "dataset_versions": sorted({case.get("dataset_version", "unspecified") for case in cases}),
        "split_counts": {
            split: sum(row["split"] == split for row in rows) for split in split_names
        },
        "lexitrace_by_split": {
            split: calculate_metrics([row for row in rows if row["split"] == split], "lexitrace")
            for split in split_names
        },
        "model_usage": semantic_encoder.usage(),
        "database": {
            "peak_allocated_bytes": max(row["database"]["allocated_bytes"] for row in rows),
            "peak_trace_payload_bytes": max(row["database"]["trace_payload_bytes"] for row in rows),
            "peak_rows": {
                table: max(row["database"]["rows"][table] for row in rows)
                for table in rows[0]["database"]["rows"]
            },
        },
        "systems": {name: calculate_metrics(rows, name) for name in system_names},
    }
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    with (output_path / "cases.jsonl").open("w", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    (output_path / "report.md").write_text(render_report(summary, rows), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nReport: {output_path / 'report.md'}")


if __name__ == "__main__":
    main()
