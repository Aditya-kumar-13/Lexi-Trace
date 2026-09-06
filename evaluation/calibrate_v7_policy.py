from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
CONFLICT_CONTEXT_FLOOR = 0.20
CONFLICT_CONTEXT_ADVANTAGE = 0.15
MINIMUM_WINNER_MARGIN = 0.12

SEARCH_SPACE = {
    "context_transform": ["linear", "sqrt", "legacy_power_035"],
    "lexical_weight": [0.60, 0.65, 0.70],
    "authorization_weight": [0.05, 0.10, 0.14],
    "context_weight": [0.05, 0.10, 0.15],
    "phonetic_weight": [0.00, 0.05, 0.10],
    "asr_alternative_weight": [0.05, 0.10],
    "learned_asr_weight": [0.09, 0.15, 0.21],
    "negative_context_weight": [0.65, 1.00],
    "apply_threshold": [0.85, 0.89, 0.93, 0.95],
    "suggest_threshold": [0.65, 0.72],
}

BASELINE = {
    "context_transform": "legacy_power_035",
    "lexical_weight": 0.72,
    "authorization_weight": 0.14,
    "context_weight": 0.10,
    "phonetic_weight": 0.10,
    "asr_alternative_weight": 0.10,
    "learned_asr_weight": 0.09,
    "negative_context_weight": 0.65,
    "apply_threshold": 0.93,
    "suggest_threshold": 0.72,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate the frozen v7 architecture.")
    parser.add_argument(
        "--static-traces",
        type=Path,
        default=ROOT / "results" / "v7" / "calibration" / "input-traces" / "cases.jsonl",
    )
    parser.add_argument(
        "--journey-traces",
        type=Path,
        default=ROOT / "results" / "v7" / "calibration" / "journey-traces" / "cases.json",
    )
    parser.add_argument(
        "--safety-traces",
        type=Path,
        default=ROOT / "results" / "v7" / "safety" / "precalibration-traces" / "cases.jsonl",
    )
    parser.add_argument(
        "--corpus-manifest",
        type=Path,
        default=ROOT / "data" / "benchmark" / "v7_calibration_manifest.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "v7" / "calibration" / "candidate-v1",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def static_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for source in load_jsonl(path):
        rows.append(
            {
                "case_id": source["case_id"],
                "category": source["category"],
                "formatted_text": source["formatted_text"],
                "expected_output": source["expected_output"],
                "expected_action": source["expected_action"],
                "candidates": source["systems"]["lexitrace"]["candidates"],
            }
        )
    return rows


def journey_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for source in payload["hybrid"]:
        rows.append(
            {
                "case_id": f"{source['journey_id']}:{source['event_index']}",
                "category": f"journey:{source['journey_id']}",
                "formatted_text": source["formatted_text"],
                "expected_output": source["expected_output"],
                "expected_action": source["expected_action"],
                "candidates": source["candidates"],
            }
        )
    return rows


def context_signal(features: dict[str, Any], transform: str) -> float:
    if features["scope_mode"] == "global":
        return 1.0
    positive = float(features["positive_context_similarity"])
    if transform == "linear":
        return positive
    if transform == "sqrt":
        return math.sqrt(positive)
    if transform == "legacy_power_035":
        return min(1.0, (positive**0.35) * 1.2)
    raise ValueError(f"Unknown context transform: {transform}")


def rescore(candidate: dict[str, Any], config: dict[str, Any]) -> float:
    features = candidate["features"]
    learned_active = float(features["asr_reliability_contribution"]) != 0.0
    raw = (
        config["lexical_weight"] * float(features["lexical_signal"])
        + config["authorization_weight"] * float(features["authorization_signal"])
        + config["context_weight"] * context_signal(features, config["context_transform"])
        + config["phonetic_weight"] * float(bool(features["phonetic_match"]))
        + config["asr_alternative_weight"]
        * float(features["asr_alternative_confidence"])
        + config["learned_asr_weight"]
        * float(features["asr_reliability_posterior"])
        * learned_active
        - config["negative_context_weight"]
        * float(features["negative_context_similarity"])
    )
    candidate["calibration_raw_score"] = raw
    candidate["score"] = max(0.0, min(1.0, raw))
    return candidate["score"]


def initial_action(candidate: dict[str, Any], config: dict[str, Any]) -> str:
    if candidate["score"] >= config["apply_threshold"] and not candidate["blockers"]:
        return "apply"
    if "NEGATIVE_CONTEXT_EVIDENCE" in candidate["blockers"]:
        return "abstain"
    if candidate["score"] >= config["suggest_threshold"]:
        return "suggest"
    return "abstain"


def overlaps(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return left["start"] < right["end"] and right["start"] < left["end"]


def simulate(row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    candidates = [dict(source) for source in row["candidates"]]
    for candidate in candidates:
        rescore(candidate, config)
        candidate["action"] = initial_action(candidate, config)
    candidates.sort(
        key=lambda item: (
            -item["score"],
            item["start"],
            -item["end"],
            item["canonical_form"].casefold(),
        )
    )
    winners: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []
    for candidate in candidates:
        if candidate["action"] != "apply":
            continue
        competing = [other for other in candidates if other is not candidate and overlaps(candidate, other)]
        runner_up = max((other["score"] for other in competing), default=0.0)
        if competing and candidate["score"] - runner_up < MINIMUM_WINNER_MARGIN:
            features = candidate["features"]
            strength = float(features["positive_context_similarity"]) - float(
                features["negative_context_similarity"]
            )
            competing_strength = max(
                (
                    float(other["features"]["positive_context_similarity"])
                    - float(other["features"]["negative_context_similarity"])
                    for other in competing
                ),
                default=0.0,
            )
            if not (
                float(features["positive_context_similarity"]) >= CONFLICT_CONTEXT_FLOOR
                and strength - competing_strength >= CONFLICT_CONTEXT_ADVANTAGE
            ):
                candidate["action"] = "suggest"
                continue
        if any(left < candidate["end"] and candidate["start"] < right for left, right in occupied):
            candidate["action"] = "abstain"
            continue
        winners.append(candidate)
        occupied.append((candidate["start"], candidate["end"]))

    output = row["formatted_text"]
    for winner in sorted(winners, key=lambda item: item["start"], reverse=True):
        output = output[: winner["start"]] + winner["output_span"] + output[winner["end"] :]
    action = (
        "apply"
        if winners
        else "suggest"
        if any(candidate["action"] == "suggest" for candidate in candidates)
        else "abstain"
    )
    return {
        "output": output,
        "action": action,
        "intervened": bool(winners),
        "raw_scores": [candidate["calibration_raw_score"] for candidate in candidates],
    }


def metrics(
    rows: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    include_failures: bool = False,
) -> dict[str, Any]:
    results = [(row, simulate(row, config)) for row in rows]
    exact = sum(result["output"] == row["expected_output"] for row, result in results)
    action_matches = sum(result["action"] == row["expected_action"] for row, result in results)
    wrong = sum(
        result["intervened"] and result["output"] != row["expected_output"]
        for row, result in results
    )
    useful = sum(
        result["intervened"] and result["output"] == row["expected_output"]
        for row, result in results
    )
    raw_scores = [score for _, result in results for score in result["raw_scores"]]
    failures = [
        {
            "case_id": row["case_id"],
            "category": row["category"],
            "expected_output": row["expected_output"],
            "actual_output": result["output"],
            "expected_action": row["expected_action"],
            "actual_action": result["action"],
            "wrong_intervention": result["intervened"] and result["output"] != row["expected_output"],
        }
        for row, result in results
        if include_failures
        and (result["output"] != row["expected_output"] or result["action"] != row["expected_action"])
    ]
    result = {
        "cases": len(rows),
        "exact_matches": exact,
        "action_matches": action_matches,
        "wrong_interventions": wrong,
        "useful_interventions": useful,
        "upper_clamped": sum(score > 1.0 for score in raw_scores),
        "lower_clamped": sum(score < 0.0 for score in raw_scores),
        "candidate_scores": len(raw_scores),
    }
    if include_failures:
        result["failures"] = failures
    return result


def configurations() -> Iterable[dict[str, Any]]:
    keys = list(SEARCH_SPACE)
    for values in itertools.product(*(SEARCH_SPACE[key] for key in keys)):
        yield dict(zip(keys, values, strict=True))


def selection_key(result: dict[str, Any]) -> tuple:
    metrics_value = result["metrics"]
    config = result["config"]
    return (
        -metrics_value["wrong_interventions"],
        metrics_value["exact_matches"],
        metrics_value["action_matches"],
        metrics_value["useful_interventions"],
        -metrics_value["upper_clamped"],
        config["apply_threshold"],
        -sum(
            config[key]
            for key in config
            if key.endswith("_weight") and key != "negative_context_weight"
        ),
        json.dumps(config, sort_keys=True),
    )


def compact(result: dict[str, Any]) -> dict[str, Any]:
    return {"config": result["config"], "metrics": {k: v for k, v in result["metrics"].items() if k != "failures"}}


def main() -> None:
    args = parse_args()
    static_path = args.static_traces.resolve()
    journey_path = args.journey_traces.resolve()
    safety_path = args.safety_traces.resolve()
    manifest_path = args.corpus_manifest.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    corpus_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_roles = corpus_manifest["roles"]
    source_checks = {
        role: sha256(ROOT / record["path"]) == record["sha256"]
        for role, record in expected_roles.items()
    }
    if not all(source_checks.values()):
        raise RuntimeError(f"Frozen corpus hash mismatch: {source_checks}")

    calibration = static_rows(static_path) + journey_rows(journey_path)
    safety = static_rows(safety_path)
    baseline = {
        "config": BASELINE,
        "metrics": metrics(calibration, BASELINE, include_failures=True),
    }
    search_path = output / "search-results.jsonl"
    selected: dict[str, Any] | None = None
    searched = 0
    with search_path.open("w", encoding="utf-8") as stream:
        for config in configurations():
            result = {"config": config, "metrics": metrics(calibration, config)}
            stream.write(json.dumps(compact(result), separators=(",", ":")) + "\n")
            searched += 1
            if selected is None or selection_key(result) > selection_key(selected):
                selected = result
    assert selected is not None
    selected["metrics"] = metrics(calibration, selected["config"], include_failures=True)

    selected_safety = metrics(safety, selected["config"], include_failures=True)
    safety_passed = selected_safety["wrong_interventions"] == 0
    artifact = {
        "artifact_version": "v7-score-calibration-v1",
        "status": "safety_pass" if safety_passed else "rejected_by_safety",
        "policy_candidate": "2026-09-v7-calibration-candidate-1",
        "selection_rule": [
            "minimize_wrong_automatic_interventions",
            "maximize_exact_outputs",
            "maximize_action_matches",
            "maximize_useful_interventions",
            "minimize_upper_clamping",
            "prefer_more_conservative_apply_threshold",
            "prefer_lower_positive_weight_sum",
            "stable_lexical_tie_break",
        ],
        "search_space": SEARCH_SPACE,
        "searched_candidates": searched,
        "inputs": {
            "corpus_manifest": {"path": str(manifest_path.relative_to(ROOT)), "sha256": sha256(manifest_path)},
            "static_traces": {"path": str(static_path.relative_to(ROOT)), "sha256": sha256(static_path)},
            "journey_traces": {"path": str(journey_path.relative_to(ROOT)), "sha256": sha256(journey_path)},
            "safety_traces": {"path": str(safety_path.relative_to(ROOT)), "sha256": sha256(safety_path)},
        },
        "corpus_hash_checks": source_checks,
        "calibration_cases": len(calibration),
        "safety_cases": len(safety),
        "baseline": baseline,
        "selected": selected,
        "selected_safety": selected_safety,
        "safety_was_not_used_for_selection": True,
        "final_holdout_accessed": False,
        "search_results": {"path": search_path.name, "sha256": sha256(search_path)},
    }
    (output / "policy.json").write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    report = [
        "# V7 score calibration candidate 1",
        "",
        f"Search candidates: **{searched}**",
        f"Calibration cases: **{len(calibration)}**",
        f"Safety cases opened after selection: **{len(safety)}**",
        "Final holdout accessed: **no**",
        "",
        f"Baseline: {baseline['metrics']['exact_matches']}/{len(calibration)} exact, "
        f"{baseline['metrics']['wrong_interventions']} wrong automatic edits, "
        f"{baseline['metrics']['upper_clamped']} upper-clamped candidate scores.",
        f"Selected: {selected['metrics']['exact_matches']}/{len(calibration)} exact, "
        f"{selected['metrics']['wrong_interventions']} wrong automatic edits, "
        f"{selected['metrics']['upper_clamped']} upper-clamped candidate scores.",
        f"Independent safety result: {selected_safety['exact_matches']}/{len(safety)} exact, "
        f"{selected_safety['wrong_interventions']} wrong automatic edits.",
        f"Gate: **{artifact['status']}**",
        "",
        "The safety corpus was evaluated only after the calibration-only selection was fixed. It did not choose among candidates.",
        "",
        "## Selected constants",
        "",
        "```json",
        json.dumps(selected["config"], indent=2),
        "```",
        "",
        "## Visible calibration failures",
        "",
    ]
    if selected["metrics"]["failures"]:
        for failure in selected["metrics"]["failures"]:
            report.append(
                f"- `{failure['case_id']}`: expected {failure['expected_action']} / "
                f"`{failure['expected_output']}`, got {failure['actual_action']} / "
                f"`{failure['actual_output']}`."
            )
    else:
        report.append("None.")
    (output / "report.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print(json.dumps(artifact, indent=2))
    if not safety_passed:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
