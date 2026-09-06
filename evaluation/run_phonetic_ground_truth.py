from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import jellyfish

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from lexitrace.phonetics import indic_transliteration_similarity  # noqa: E402

THRESHOLDS = tuple(round(0.70 + step * 0.01, 2) for step in range(30))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate phonetic equality on labeled name pairs."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=ROOT / "data" / "benchmark" / "v7_indic_phonetic_development.jsonl",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "v7" / "development" / "current" / "phonetics",
    )
    return parser.parse_args()


def metaphone_equal(left: str, right: str) -> bool:
    return jellyfish.metaphone(left) == jellyfish.metaphone(right)


def metrics(cases: list[dict], prediction_key: str) -> dict:
    true_positive = sum(row["same_name"] and row[prediction_key] for row in cases)
    false_positive = sum(not row["same_name"] and row[prediction_key] for row in cases)
    false_negative = sum(row["same_name"] and not row[prediction_key] for row in cases)
    true_negative = sum(not row["same_name"] and not row[prediction_key] for row in cases)
    return {
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "true_negative": true_negative,
        "accuracy": round((true_positive + true_negative) / len(cases), 4),
        "precision": round(true_positive / max(1, true_positive + false_positive), 4),
        "recall": round(true_positive / max(1, true_positive + false_negative), 4),
    }


def main() -> None:
    args = parse_args()
    dataset = args.dataset.resolve()
    rows = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line]
    cases = []
    for row in rows:
        predicted = metaphone_equal(row["left"], row["right"])
        cases.append(
            {
                **row,
                "metaphone_same": predicted,
                "indic_similarity": round(
                    indic_transliteration_similarity(row["left"], row["right"]), 4
                ),
                "metaphone_correct": predicted == row["same_name"],
            }
        )
    baseline = metrics(cases, "metaphone_same")
    curve = []
    for threshold in THRESHOLDS:
        enriched = [{**row, "indic_same": row["indic_similarity"] >= threshold} for row in cases]
        curve.append({"threshold": threshold, **metrics(enriched, "indic_same")})
    failures = [row for row in cases if not row["metaphone_correct"]]
    summary = {
        "artifact_version": "indic-phonetic-development-v1",
        "evidence_role": "structural_development",
        "algorithm": "jellyfish.metaphone equality",
        "dataset": dataset.relative_to(ROOT).as_posix(),
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "pairs": len(cases),
        "labels": dict(Counter("same" if row["same_name"] else "different" for row in cases)),
        "metaphone": {**baseline, "failures": len(failures)},
        "indic_similarity_curve": curve,
        "selection": "none; structural development curve only",
    }
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "cases.json").write_text(json.dumps(cases, indent=2) + "\n", encoding="utf-8")
    (output / "failures.json").write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
