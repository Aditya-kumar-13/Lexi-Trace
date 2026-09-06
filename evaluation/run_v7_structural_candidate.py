from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the frozen v7 structural candidate.")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "v7" / "development" / "current" / "structural-candidate",
    )
    parser.add_argument(
        "--reuse-results",
        action="store_true",
        help="Rebuild the manifest from existing suite artifacts without rerunning them.",
    )
    parser.add_argument(
        "--role",
        choices=("development", "regression"),
        default="development",
    )
    return parser.parse_args()


def run(command: list[str]) -> None:
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode:
        raise SystemExit(f"candidate command failed with exit code {completed.returncode}")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def distribution(values: list[float]) -> dict:
    ordered = sorted(values)

    def percentile(fraction: float) -> float:
        index = round((len(ordered) - 1) * fraction)
        return round(ordered[index], 6)

    return {
        "count": len(ordered),
        "minimum": round(ordered[0], 6),
        "p25": percentile(0.25),
        "median": percentile(0.50),
        "p75": percentile(0.75),
        "maximum": round(ordered[-1], 6),
        "mean": round(sum(ordered) / len(ordered), 6),
        "nonzero": sum(value != 0.0 for value in ordered),
    }


def instrument_static_outputs(outputs: list[Path]) -> dict:
    candidates: list[dict] = []
    generation = Counter()
    for path in outputs:
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            result = row["systems"]["lexitrace"]
            candidates.extend(result["candidates"])
            for key, value in result["candidate_generation"].items():
                if isinstance(value, int):
                    generation[key] += value
    raw_scores = [float(item["features"]["score_before_clamp"]) for item in candidates]
    clamped_scores = [float(item["score"]) for item in candidates]
    controllers = Counter(str(item["features"]["context_controller"]) for item in candidates)
    routes = Counter(str(item["features"]["match_method"]) for item in candidates)
    contributions = {}
    contribution_keys = sorted(
        key
        for key in candidates[0]["features"]
        if key.startswith("score_") and key.endswith("_contribution")
    )
    for key in contribution_keys:
        values = [float(item["features"][key]) for item in candidates]
        contributions[key] = {
            "mean": round(sum(values) / len(values), 6),
            "nonzero": sum(value != 0.0 for value in values),
        }
    return {
        "cases": sum(1 for path in outputs for line in path.read_text().splitlines() if line),
        "candidates": len(candidates),
        "candidate_generation": dict(sorted(generation.items())),
        "raw_score_mean": round(sum(raw_scores) / len(raw_scores), 6),
        "clamped_score_mean": round(sum(clamped_scores) / len(clamped_scores), 6),
        "upper_clamped": sum(value > 1.0 for value in raw_scores),
        "lower_clamped": sum(value < 0.0 for value in raw_scores),
        "context_controllers": dict(sorted(controllers.items())),
        "candidate_routes": dict(sorted(routes.items())),
        "context_distributions": {
            key: distribution([float(item["features"][key]) for item in candidates])
            for key in (
                "sparse_positive_similarity",
                "sparse_negative_similarity",
                "semantic_positive_similarity",
                "semantic_negative_similarity",
            )
        },
        "score_contributions": contributions,
    }


def main() -> None:
    args = parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    python = sys.executable
    static_common = [
        "--semantic-retrieval-mode",
        "nearest_example",
        "--minimum-conflict-positive-context",
        "0.20",
        "--authorization-score-mode",
        "boolean",
    ]
    journey_common = [
        "--semantic-retrieval-mode",
        "nearest_example",
        "--minimum-conflict-positive-context",
        "0.20",
        "--feedback-scope-mode",
        "auto",
        "--asr-reliability-mode",
        "exact_route",
        "--authorization-score-mode",
        "boolean",
        "--semantic-evidence-cap",
        "12",
    ]
    runs = [
        (
            "smoke",
            [python, "evaluation/run.py", "--dataset", "data/benchmark/smoke.jsonl"],
            static_common,
        ),
        (
            "robustness",
            [python, "evaluation/run.py", "--dataset", "data/benchmark/robustness.jsonl"],
            static_common,
        ),
        ("journeys", [python, "evaluation/run_journeys.py"], journey_common),
        (
            "multimodal",
            [
                python,
                "evaluation/run_journeys.py",
                "--dataset",
                "data/benchmark/v7_semantic_multimodal_development.jsonl",
            ],
            journey_common,
        ),
        (
            "semantic-safety",
            [
                python,
                "evaluation/run_journeys.py",
                "--dataset",
                "data/benchmark/v7_semantic_safety_development.jsonl",
            ],
            journey_common,
        ),
        (
            "semantic-storage",
            [
                python,
                "evaluation/run_journeys.py",
                "--dataset",
                "data/benchmark/v7_semantic_storage_development.jsonl",
            ],
            journey_common,
        ),
        (
            "asr-learning",
            [
                python,
                "evaluation/run_asr_learning.py",
                "--asr-reliability-mode",
                "exact_route",
            ],
            [],
        ),
        (
            "lifecycle",
            [python, "evaluation/run_lifecycle.py", "--feedback-scope-mode", "auto"],
            [],
        ),
        (
            "conflicts",
            [python, "evaluation/run_conflicts.py"],
            [
                "--semantic-retrieval-mode",
                "nearest_example",
                "--minimum-conflict-positive-context",
                "0.20",
                "--feedback-scope-mode",
                "auto",
                "--semantic-evidence-cap",
                "12",
            ],
        ),
    ]
    if not args.reuse_results:
        for name, command, options in runs:
            run([*command, *options, "--output", str(output / name)])

    summaries = {name: load_json(output / name / "summary.json") for name, _, _ in runs}
    instrumentation = instrument_static_outputs(
        [output / "smoke" / "cases.jsonl", output / "robustness" / "cases.jsonl"]
    )
    manifest = {
        "status": (
            "regression_candidate_complete"
            if args.role == "regression"
            else "structural_candidate_frozen_for_calibration"
        ),
        "dataset_role": "regression" if args.role == "regression" else "development_only",
        "configuration": {
            "semantic_retrieval": "nearest_example",
            "semantic_evidence_cap_per_memory_polarity": 12,
            "feedback_scope": "auto",
            "minimum_conflict_positive_context": 0.20,
            "asr_reliability": "exact_route",
            "asr_confidence": "legacy_double",
            "authorization": "boolean",
            "phonetic_matcher": "metaphone_active_indic_alternative_unselected",
        },
        "instrumentation": instrumentation,
        "summaries": {
            name: {
                "path": f"{name}/summary.json",
                "sha256": sha256(output / name / "summary.json"),
                "content": summary,
            }
            for name, summary in summaries.items()
        },
        "final_holdout_accessed": False,
        "next_stage": "score_recalibration",
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
