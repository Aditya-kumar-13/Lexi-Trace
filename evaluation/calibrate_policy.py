from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze an apply threshold using only the predeclared calibration split."
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=ROOT / "results" / "robustness" / "cases.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "calibration",
    )
    parser.add_argument(
        "--safety-cases",
        type=Path,
        default=ROOT / "results" / "latest" / "cases.jsonl",
        help="Frozen safety corpus that constrains promotion but is not optimized.",
    )
    parser.add_argument("--baseline-threshold", type=Decimal, default=Decimal("0.93"))
    parser.add_argument("--minimum", type=Decimal, default=Decimal("0.85"))
    parser.add_argument("--maximum", type=Decimal, default=Decimal("0.95"))
    parser.add_argument("--step", type=Decimal, default=Decimal("0.005"))
    return parser.parse_args()


def load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def load_calibration_rows(path: Path) -> list[dict[str, Any]]:
    rows = load_rows(path)
    calibration = [row for row in rows if row.get("split") == "calibration"]
    if not calibration:
        raise ValueError("No predeclared calibration rows were found")
    return calibration


def thresholds(start: Decimal, stop: Decimal, step: Decimal) -> list[float]:
    if step <= 0 or start > stop:
        raise ValueError("Threshold search range is invalid")
    values: list[float] = []
    current = start
    while current <= stop:
        values.append(float(current))
        current += step
    return values


def candidate_action(candidate: dict[str, Any], apply: float, suggest: float) -> str:
    blockers = candidate["blockers"]
    if candidate["score"] >= apply and not blockers:
        return "apply"
    if "NEGATIVE_CONTEXT_EVIDENCE" in blockers:
        return "abstain"
    if candidate["score"] >= suggest:
        return "suggest"
    return "abstain"


def simulate(
    row: dict[str, Any],
    *,
    apply: float,
    suggest: float = 0.72,
    minimum_winner_margin: float = 0.12,
) -> dict[str, Any]:
    candidates = deepcopy(row["systems"]["lexitrace"]["candidates"])
    for candidate in candidates:
        candidate["action"] = candidate_action(candidate, apply, suggest)
    candidates.sort(key=lambda item: (-item["score"], item["start"], -item["end"]))

    winners: list[dict[str, Any]] = []
    occupied: list[tuple[int, int]] = []
    for candidate in candidates:
        if candidate["action"] != "apply":
            continue
        overlapping = [
            other
            for other in candidates
            if other is not candidate
            and other["start"] < candidate["end"]
            and candidate["start"] < other["end"]
        ]
        runner_up = max((other["score"] for other in overlapping), default=0.0)
        if overlapping and candidate["score"] - runner_up < minimum_winner_margin:
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
    return {"output": output, "action": action, "intervened": bool(winners)}


def metrics(rows: list[dict[str, Any]], apply: float) -> dict[str, Any]:
    outcomes = [(row, simulate(row, apply=apply)) for row in rows]
    exact = [result["output"] == row["expected_output"] for row, result in outcomes]
    actions = [result["action"] == row["expected_action"] for row, result in outcomes]
    wrong = [
        result["intervened"] and result["output"] != row["expected_output"]
        for row, result in outcomes
    ]
    return {
        "apply_threshold": apply,
        "cases": len(rows),
        "exact_matches": sum(exact),
        "exact_match_rate": round(sum(exact) / len(rows), 4),
        "action_matches": sum(actions),
        "action_accuracy": round(sum(actions) / len(rows), 4),
        "wrong_interventions": sum(wrong),
    }


def main() -> None:
    args = parse_args()
    cases_path = args.cases.resolve()
    safety_path = args.safety_cases.resolve()
    output_path = args.output.resolve()
    rows = load_calibration_rows(cases_path)
    safety_rows = load_rows(safety_path)
    if not safety_rows:
        raise ValueError("Safety corpus is empty")
    search = [metrics(rows, value) for value in thresholds(args.minimum, args.maximum, args.step)]
    baseline = metrics(rows, float(args.baseline_threshold))
    baseline_safety = metrics(safety_rows, float(args.baseline_threshold))
    safety_by_threshold = {
        item["apply_threshold"]: metrics(safety_rows, item["apply_threshold"]) for item in search
    }
    calibration_eligible = [item for item in search if item["wrong_interventions"] == 0]
    calibration_candidate = max(
        calibration_eligible,
        key=lambda item: (
            item["exact_matches"],
            item["action_matches"],
            item["apply_threshold"],
        ),
    )
    eligible = [
        item
        for item in calibration_eligible
        if safety_by_threshold[item["apply_threshold"]]["wrong_interventions"]
        <= baseline_safety["wrong_interventions"]
        and safety_by_threshold[item["apply_threshold"]]["exact_matches"]
        >= baseline_safety["exact_matches"]
    ]
    if not eligible:
        raise RuntimeError("No threshold satisfied the zero-wrong-intervention safety invariant")
    selected = max(
        eligible,
        key=lambda item: (
            item["exact_matches"],
            item["action_matches"],
            item["apply_threshold"],
        ),
    )
    candidate_safety = safety_by_threshold[calibration_candidate["apply_threshold"]]
    promotion_allowed = (
        calibration_candidate["wrong_interventions"] <= baseline["wrong_interventions"]
        and calibration_candidate["exact_matches"] >= baseline["exact_matches"]
        and candidate_safety["wrong_interventions"] <= baseline_safety["wrong_interventions"]
        and candidate_safety["exact_matches"] >= baseline_safety["exact_matches"]
    )
    artifact = {
        "artifact_version": "calibrated-decision-policy-v1",
        "policy_id": f"safe-apply-{int(selected['apply_threshold'] * 1000):03d}",
        "source_cases": (
            cases_path.relative_to(ROOT).as_posix()
            if cases_path.is_relative_to(ROOT)
            else str(cases_path)
        ),
        "source_cases_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
        "safety_cases": (
            safety_path.relative_to(ROOT).as_posix()
            if safety_path.is_relative_to(ROOT)
            else str(safety_path)
        ),
        "safety_cases_sha256": hashlib.sha256(safety_path.read_bytes()).hexdigest(),
        "split_used": "calibration",
        "heldout_rows_accessed": 0,
        "calibration_cases": len(rows),
        "safety_cases_count": len(safety_rows),
        "objective": [
            "zero_wrong_interventions",
            "maximize_exact_matches",
            "maximize_action_matches",
            "prefer_the_most_conservative_tie",
        ],
        "search_space": {
            "minimum": float(args.minimum),
            "maximum": float(args.maximum),
            "step": float(args.step),
        },
        "baseline": baseline,
        "baseline_safety": baseline_safety,
        "calibration_candidate": calibration_candidate,
        "calibration_candidate_safety": candidate_safety,
        "selected": selected,
        "selected_safety": safety_by_threshold[selected["apply_threshold"]],
        "deployment_gate": {
            "status": "promote" if promotion_allowed else "reject_candidate_keep_active",
            "promotion_allowed": promotion_allowed,
            "candidate_threshold": calibration_candidate["apply_threshold"],
            "active_threshold": selected["apply_threshold"],
            "violations": [
                violation
                for violation, failed in (
                    (
                        "safety_wrong_interventions_increased",
                        candidate_safety["wrong_interventions"]
                        > baseline_safety["wrong_interventions"],
                    ),
                    (
                        "safety_exact_matches_decreased",
                        candidate_safety["exact_matches"] < baseline_safety["exact_matches"],
                    ),
                )
                if failed
            ],
            "rollback_when": {
                "safety_wrong_interventions_above": baseline_safety["wrong_interventions"],
                "safety_exact_matches_below": baseline_safety["exact_matches"],
            },
        },
        "search_results": search,
    }
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "policy.json").write_text(
        json.dumps(artifact, indent=2) + "\n", encoding="utf-8"
    )
    report = "\n".join(
        [
            "# Frozen policy calibration",
            "",
            f"Calibration rows: **{len(rows)}**",
            "Held-out rows accessed: **0**",
            f"Baseline: **{baseline['exact_matches']}/{len(rows)}**, "
            f"{baseline['wrong_interventions']} wrong interventions",
            f"Calibration-only candidate: **{calibration_candidate['apply_threshold']:.3f}**",
            f"Candidate safety result: **{candidate_safety['exact_matches']}/{len(safety_rows)}**, "
            f"{candidate_safety['wrong_interventions']} wrong interventions",
            f"Safe selected threshold: **{selected['apply_threshold']:.3f}**",
            f"Deployment gate: **{artifact['deployment_gate']['status']}**",
            "",
            "The held-out split is evaluated only after this artifact is frozen.",
            "",
        ]
    )
    (output_path / "report.md").write_text(report, encoding="utf-8")
    print(json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()
