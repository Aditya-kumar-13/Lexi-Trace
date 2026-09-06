from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two structural evaluation case files.")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def correct(row: dict, actual: dict) -> bool:
    return actual["output"] == row["expected_output"] and actual["action"] == row["expected_action"]


def wrong_intervention(row: dict, actual: dict) -> bool:
    return actual["output"] != row["formatted_text"] and actual["output"] != row["expected_output"]


def main() -> None:
    args = parse_args()
    baseline_path = args.baseline.resolve()
    candidate_path = args.candidate.resolve()
    baseline_rows = {row["case_id"]: row for row in load(baseline_path)}
    candidate_rows = {row["case_id"]: row for row in load(candidate_path)}
    if baseline_rows.keys() != candidate_rows.keys():
        raise SystemExit("Structural runs contain different case IDs.")
    differences = []
    counts = {"action_changed": 0, "output_changed": 0, "fixed": 0, "broken": 0}
    baseline_wrong = 0
    candidate_wrong = 0
    for case_id in sorted(baseline_rows):
        baseline = baseline_rows[case_id]
        candidate = candidate_rows[case_id]
        old = baseline["systems"]["lexitrace"]
        new = candidate["systems"]["lexitrace"]
        old_correct = correct(baseline, old)
        new_correct = correct(candidate, new)
        baseline_wrong += wrong_intervention(baseline, old)
        candidate_wrong += wrong_intervention(candidate, new)
        action_changed = old["action"] != new["action"]
        output_changed = old["output"] != new["output"]
        fixed = not old_correct and new_correct
        broken = old_correct and not new_correct
        counts["action_changed"] += action_changed
        counts["output_changed"] += output_changed
        counts["fixed"] += fixed
        counts["broken"] += broken
        if action_changed or output_changed or fixed or broken:
            differences.append(
                {
                    "case_id": case_id,
                    "category": baseline["category"],
                    "expected_output": baseline["expected_output"],
                    "expected_action": baseline["expected_action"],
                    "baseline": {"output": old["output"], "action": old["action"]},
                    "candidate": {"output": new["output"], "action": new["action"]},
                    "fixed": fixed,
                    "broken": broken,
                }
            )
    total = len(baseline_rows)
    summary = {
        "artifact_version": "structural-comparison-v1",
        "evidence_role": "structural_development",
        "experiment": args.experiment,
        "cases": total,
        "baseline": {
            "path": baseline_path.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(baseline_path.read_bytes()).hexdigest(),
            "wrong_interventions": baseline_wrong,
        },
        "candidate": {
            "path": candidate_path.relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
            "wrong_interventions": candidate_wrong,
        },
        **counts,
        "decision_impact_rate": round(counts["action_changed"] / max(1, total), 4),
        "selection": "none; structural development comparison only",
    }
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "differences.json").write_text(
        json.dumps(differences, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
