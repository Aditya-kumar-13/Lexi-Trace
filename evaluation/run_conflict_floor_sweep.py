from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOORS = (0.15, 0.20, 0.25, 0.30)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare conflict context floors on development data."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "data" / "benchmark" / "v7_semantic_safety_development.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "v7" / "development" / "current" / "conflict-floor-sweep",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    dataset = args.dataset.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for floor in FLOORS:
        run_output = output / f"floor-{floor:.2f}"
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "evaluation" / "run_journeys.py"),
                "--dataset",
                str(dataset),
                "--semantic-retrieval-mode",
                "nearest_example",
                "--disable-auto-lifecycle",
                "--minimum-conflict-positive-context",
                f"{floor:.2f}",
                "--output",
                str(run_output),
            ],
            cwd=ROOT,
            check=False,
        )
        if completed.returncode:
            raise SystemExit(f"floor {floor:.2f} failed with exit code {completed.returncode}")
        summary = json.loads((run_output / "summary.json").read_text(encoding="utf-8"))
        metrics = summary["systems"]["hybrid"]
        rows.append(
            {
                "floor": floor,
                "exact_match_rate": metrics["exact_match_rate"],
                "action_accuracy": metrics["action_accuracy"],
                "wrong_interventions": metrics["wrong_interventions"],
                "summary": (run_output / "summary.json").relative_to(output).as_posix(),
                "cases": (run_output / "cases.json").relative_to(output).as_posix(),
            }
        )

    safe_rows = [row for row in rows if row["wrong_interventions"] == 0]
    best_exact = max(row["exact_match_rate"] for row in safe_rows)
    selected = min(
        (row for row in safe_rows if row["exact_match_rate"] == best_exact),
        key=lambda row: row["floor"],
    )
    comparison = {
        "dataset": dataset.relative_to(ROOT).as_posix(),
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "dataset_role": "exploratory_development",
        "retrieval_mode": "nearest_example",
        "auto_lifecycle_enabled": False,
        "floors": list(FLOORS),
        "selection_rule": (
            "zero wrong interventions, then maximum exact-match rate, then the least "
            "restrictive floor"
        ),
        "runs": rows,
        "selected_development_candidate": selected["floor"],
        "promotion_status": "not_promoted",
    }
    (output / "comparison.json").write_text(
        json.dumps(comparison, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(comparison, indent=2))


if __name__ == "__main__":
    main()
