from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRIBUTIONS = (
    "score_lexical_contribution",
    "score_authorization_contribution",
    "score_context_contribution",
    "score_phonetic_contribution",
    "score_asr_alternative_contribution",
    "score_learned_asr_contribution",
    "score_negative_context_contribution",
)
HISTOGRAM_EDGES = (-1.0, 0.0, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.000001)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate policy-v7 baseline instrumentation.")
    parser.add_argument("--cases", type=Path, action="append", required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results" / "v7" / "development" / "current" / "instrumentation",
    )
    return parser.parse_args()


def percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return round(ordered[index], 4)


def distribution(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "minimum": round(min(values), 4) if values else 0.0,
        "mean": round(statistics.mean(values), 4) if values else 0.0,
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "maximum": round(max(values), 4) if values else 0.0,
    }


def histogram(values: list[float]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for left, right in zip(HISTOGRAM_EDGES, HISTOGRAM_EDGES[1:], strict=False):
        label = f"[{left:.1f},{min(right, 1.0):.1f}{']' if right > 1.0 else ')'}"
        counts[label] = sum(left <= value < right for value in values)
    return counts


def read_rows(paths: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    rows: list[dict[str, Any]] = []
    sources = []
    for path in paths:
        resolved = path.resolve()
        content = resolved.read_bytes()
        parsed = [json.loads(line) for line in content.decode("utf-8").splitlines() if line]
        rows.extend(parsed)
        sources.append(
            {
                "path": resolved.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return rows, sources


def render_report(summary: dict[str, Any], failures: list[dict[str, Any]]) -> str:
    candidate = summary["candidate_generation"]
    scoring = summary["scoring"]
    lines = [
        "# Policy v7 baseline instrumentation",
        "",
        "This is diagnostic development evidence, not final-holdout performance.",
        "",
        f"- Cases: **{summary['cases']}**",
        f"- Retained candidates: **{scoring['candidates']}**",
        f"- Scored candidates before cross-variant deduplication: **{candidate['scored_total']}**",
        f"- Cross-variant duplicates removed: **{candidate['duplicates_removed']}**",
        f"- Retained duplicate-key violations: **{candidate['retained_duplicate_violations']}**",
        f"- Upper-clamped candidates: **{scoring['upper_clamp_count']}**",
        f"- Lower-clamped candidates: **{scoring['lower_clamp_count']}**",
        "",
        "## Context controller",
        "",
    ]
    for name, count in scoring["context_controller"].items():
        lines.append(f"- {name}: **{count}**")
    lines.extend(["", "## Contribution activity", ""])
    for name, values in scoring["contributions"].items():
        lines.append(
            f"- {name}: non-zero **{values['nonzero']}**, mean **{values['mean']:.4f}**, "
            f"mean absolute **{values['mean_absolute']:.4f}**"
        )
    lines.extend(["", "## Visible failures", ""])
    if not failures:
        lines.append("None.")
    else:
        lines.append("| Case | Category | Expected | Actual | Expected action | Actual action |")
        lines.append("|---|---|---|---|---|---|")
        for failure in failures:
            lines.append(
                "| {case_id} | {category} | {expected} | {actual} | {expected_action} | "
                "{actual_action} |".format(**failure)
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    rows, sources = read_rows(args.cases)
    candidates = [
        candidate for row in rows for candidate in row["systems"]["lexitrace"].get("candidates", [])
    ]
    diagnostics = [row["systems"]["lexitrace"].get("candidate_generation", {}) for row in rows]
    retained_duplicate_violations = sum(
        int(item.get("retained_key_duplicates", 0)) for item in diagnostics
    )
    raw_stage_totals: dict[str, int] = defaultdict(int)
    method_stage_totals: dict[str, Counter[str]] = defaultdict(Counter)
    for item in diagnostics:
        for source_name in ("direct", "asr_alternatives"):
            source = item.get(source_name, {})
            for key, value in source.items():
                if key.endswith("_by_method"):
                    method_stage_totals[f"{source_name}.{key}"].update(value)
                elif isinstance(value, int):
                    raw_stage_totals[f"{source_name}.{key}"] += value

    feature_rows = [candidate["features"] for candidate in candidates]
    contributions = {}
    for name in CONTRIBUTIONS:
        values = [float(features[name]) for features in feature_rows]
        contributions[name] = {
            "nonzero": sum(value != 0.0 for value in values),
            "mean": round(statistics.mean(values), 4) if values else 0.0,
            "mean_absolute": (
                round(statistics.mean(abs(value) for value in values), 4) if values else 0.0
            ),
        }

    raw_scores = [float(features["score_before_clamp"]) for features in feature_rows]
    sparse_positive = [float(features["sparse_positive_similarity"]) for features in feature_rows]
    semantic_positive = [
        float(features["semantic_positive_similarity"]) for features in feature_rows
    ]
    semantic_negative = [
        float(features["semantic_negative_similarity"]) for features in feature_rows
    ]
    controller = Counter(str(features["context_controller"]) for features in feature_rows)
    latencies_by_candidate_count: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        system = row["systems"]["lexitrace"]
        latencies_by_candidate_count[len(system.get("candidates", []))].append(
            float(system["latency_ms"])
        )
    failures = []
    for row in rows:
        actual = row["systems"]["lexitrace"]
        if actual["exact"] and actual["action_matches"]:
            continue
        failures.append(
            {
                "case_id": row["case_id"],
                "category": row["category"],
                "expected": row["expected_output"],
                "actual": actual["output"],
                "expected_action": row["expected_action"],
                "actual_action": actual["action"],
                "candidates": actual.get("candidates", []),
            }
        )

    summary = {
        "artifact_version": "v7-baseline-instrumentation-v1",
        "evidence_role": "structural_development",
        "sources": sources,
        "cases": len(rows),
        "candidate_generation": {
            "scored_total": sum(int(item.get("scored_total", 0)) for item in diagnostics),
            "unique_memory_span_keys": sum(
                int(item.get("unique_memory_span_keys", 0)) for item in diagnostics
            ),
            "duplicates_removed": sum(
                int(item.get("cross_variant_duplicates_removed", 0)) for item in diagnostics
            ),
            "higher_score_replacements": sum(
                int(item.get("higher_score_replacements", 0)) for item in diagnostics
            ),
            "maximum_memory_span_multiplicity": max(
                (int(item.get("maximum_memory_span_multiplicity", 0)) for item in diagnostics),
                default=0,
            ),
            "retained_duplicate_violations": retained_duplicate_violations,
            "generation_stages": dict(sorted(raw_stage_totals.items())),
            "generation_methods": {
                stage: dict(sorted(counts.items()))
                for stage, counts in sorted(method_stage_totals.items())
            },
        },
        "scoring": {
            "candidates": len(candidates),
            "score_before_clamp": distribution(raw_scores),
            "upper_clamp_count": sum(value > 1.0 for value in raw_scores),
            "lower_clamp_count": sum(value < 0.0 for value in raw_scores),
            "context_controller": dict(sorted(controller.items())),
            "contributions": contributions,
            "sparse_positive": distribution(sparse_positive),
            "semantic_positive": distribution(semantic_positive),
            "semantic_negative": distribution(semantic_negative),
            "semantic_positive_histogram": histogram(semantic_positive),
            "semantic_negative_histogram": histogram(semantic_negative),
        },
        "latency_by_retained_candidate_count": {
            str(count): distribution(values)
            for count, values in sorted(latencies_by_candidate_count.items())
        },
        "failures": len(failures),
    }
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "failures.json").write_text(json.dumps(failures, indent=2) + "\n", encoding="utf-8")
    (output / "report.md").write_text(render_report(summary, failures), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
