from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = "v7-calibration-corpus-v1"


def memory(
    canonical: str,
    variant: str,
    *,
    scope: str = "global",
    state: str = "confirmed",
    source: str = "",
    accepted: str = "",
) -> dict:
    return {
        "canonical_form": canonical,
        "variants": [variant],
        "scope_mode": scope,
        "state": state,
        "source_formatted": source,
        "source_accepted": accepted,
    }


def case(
    case_id: str,
    category: str,
    memories: list[dict],
    formatted: str,
    expected: str,
    action: str,
    **extra: object,
) -> dict:
    return {
        "case_id": case_id,
        "category": category,
        "memories": memories,
        "formatted_text": formatted,
        "expected_output": expected,
        "expected_action": action,
        "dataset_version": VERSION,
        "split": "calibration",
        **extra,
    }


def calibration_cases() -> list[dict]:
    rows: list[dict] = []
    global_terms = [
        ("Nivetha", "Niveta"),
        ("Grafana", "Graf anna"),
        ("Zscaler", "Z scaler"),
        ("ClickHouse", "Click house"),
        ("Hasura", "Hazura"),
        ("Meilisearch", "Mealy search"),
    ]
    frames = [
        "Ask {variant} to inspect the release.",
        "Send the incident notes to {variant}.",
        "Open the {variant} workspace now.",
        "Add {variant} to tomorrow's review.",
    ]
    for term_index, (canonical, variant) in enumerate(global_terms):
        for frame_index, frame in enumerate(frames):
            formatted = frame.format(variant=variant)
            rows.append(
                case(
                    f"cal-global-exact-{term_index:02d}-{frame_index:02d}",
                    "confirmed-global-exact",
                    [memory(canonical, variant)],
                    formatted,
                    formatted.replace(variant, canonical),
                    "apply",
                )
            )

    for index, (canonical, variant) in enumerate(global_terms[:4]):
        formatted = f"Please route this approval to {variant}."
        rows.append(
            case(
                f"cal-unconfirmed-{index:02d}",
                "unconfirmed-memory",
                [memory(canonical, variant, state="candidate")],
                formatted,
                formatted,
                "suggest",
            )
        )

    contextual = [
        (
            "Kora",
            "Cora",
            "Deploy Cora through the edge platform after the build.",
            [
                "Roll out Cora through the edge platform tonight.",
                "The deployment dashboard for Cora shows a healthy build.",
                "Check Cora's edge logs before releasing the service.",
            ],
            [
                "Cora will meet us beside the library.",
                "I sent Cora a birthday invitation.",
                "Cora reserved a table for the family.",
            ],
        ),
        (
            "Myntra",
            "Mantra",
            "Open Mantra and review the shopping cart campaign.",
            [
                "Check the Mantra storefront campaign metrics.",
                "The shopping cart in Mantra still has the test order.",
                "Publish the apparel sale through Mantra today.",
            ],
            [
                "Repeat the mantra slowly during meditation.",
                "That mantra helps me focus before sunrise.",
                "She wrote the mantra in her journal.",
            ],
        ),
        (
            "Aiven",
            "Ivan",
            "Scale the Ivan Kafka cluster in the cloud console.",
            [
                "The Ivan cloud console reports Kafka lag.",
                "Resize the managed database cluster in Ivan.",
                "Review Ivan service alerts before the migration.",
            ],
            [
                "Ivan is bringing dessert to the picnic.",
                "I called Ivan about his train ticket.",
                "Ivan coaches the school football team.",
            ],
        ),
        (
            "Vercel",
            "Verse cell",
            "Publish the web preview through Verse cell deployment.",
            [
                "The Verse cell preview deployment passed its checks.",
                "Inspect the web build logs in Verse cell.",
                "Promote the Verse cell preview to production.",
            ],
            [
                "The poem has a verse cell marked in blue.",
                "Biology class discussed a cell after the verse.",
                "Copy that verse; cell references belong below it.",
            ],
        ),
    ]
    for term_index, (canonical, variant, source, positives, negatives) in enumerate(contextual):
        learned = memory(
            canonical,
            variant,
            scope="contextual",
            source=source,
            accepted=source.replace(variant, canonical),
        )
        for sample_index, formatted in enumerate(positives):
            rows.append(
                case(
                    f"cal-context-positive-{term_index:02d}-{sample_index:02d}",
                    "contextual-positive",
                    [learned],
                    formatted,
                    formatted.replace(variant, canonical),
                    "apply",
                )
            )
        for sample_index, formatted in enumerate(negatives):
            rows.append(
                case(
                    f"cal-context-negative-{term_index:02d}-{sample_index:02d}",
                    "contextual-homograph-negative",
                    [learned],
                    formatted,
                    formatted,
                    "suggest",
                )
            )

    occurrence_frames = [
        "Ask Niveta to send Niveta the checklist.",
        "Niveta reviewed the plan, and Niveta approved it.",
        "Message Niveta before Niveta joins the call.",
        "Niveta owns the draft that Niveta shared.",
    ]
    for index, formatted in enumerate(occurrence_frames):
        rows.append(
            case(
                f"cal-repeated-span-{index:02d}",
                "independent-repeated-spans",
                [memory("Nivetha", "Niveta")],
                formatted,
                formatted.replace("Niveta", "Nivetha"),
                "apply",
            )
        )

    asr_cases = [
        (0.99, "apply"),
        (0.95, "apply"),
        (0.90, "abstain"),
        (0.75, "abstain"),
        (0.55, "abstain"),
        (0.30, "abstain"),
    ]
    for index, (confidence, action) in enumerate(asr_cases):
        formatted = "Open the monitoring overview."
        alternative = "Open the Graf anna overview."
        expected = "Open the Grafana overview." if action == "apply" else formatted
        rows.append(
            case(
                f"cal-asr-alternative-{index:02d}",
                "asr-alternative-confidence",
                [memory("Grafana", "Graf anna")],
                formatted,
                expected,
                action,
                alternatives=[
                    {
                        "text": alternative,
                        "confidence": confidence,
                        "provider": "calibration-asr",
                        "model": "voice-cal-1",
                    }
                ],
            )
        )
    return rows


def safety_cases() -> list[dict]:
    rows: list[dict] = []
    ambiguous = [
        (
            "Luma",
            "Looma",
            "Render the Looma scene with the video design tool.",
            "Looma will collect her passport after lunch.",
        ),
        (
            "Brevo",
            "Bravo",
            "Send the Bravo email campaign from the marketing console.",
            "The audience shouted bravo after the final song.",
        ),
        (
            "Snyk",
            "Sneak",
            "Run the Sneak dependency security scan in CI.",
            "We can sneak through the side entrance quietly.",
        ),
        (
            "RiveryAI",
            "Rivery",
            "Monitor the Rivery data pipeline in the cloud console.",
            "The rivery landscape appeared after the storm.",
        ),
    ]
    for index, (canonical, variant, source, negative) in enumerate(ambiguous):
        learned = memory(
            canonical,
            variant,
            scope="contextual",
            source=source,
            accepted=source.replace(variant, canonical),
        )
        rows.append(
            case(
                f"safety-context-negative-{index:02d}",
                "safety-context-homograph",
                [learned],
                negative,
                negative,
                "suggest",
            )
        )
        rows.append(
            case(
                f"safety-context-positive-{index:02d}",
                "safety-context-positive",
                [learned],
                source,
                source.replace(variant, canonical),
                "apply",
            )
        )

    pending = [
        ("Dhruvi", "Dhruvee"),
        ("OpenTofu", "Open tofu"),
        ("Langfuse", "Lang fuse"),
        ("Qonto", "Quanto"),
    ]
    for index, (canonical, variant) in enumerate(pending):
        formatted = f"Ask {variant} to approve the production change."
        rows.append(
            case(
                f"safety-unconfirmed-{index:02d}",
                "safety-unconfirmed",
                [memory(canonical, variant, state="candidate")],
                formatted,
                formatted,
                "suggest",
            )
        )

    for index, confidence in enumerate((1.0, 0.99, 0.97, 0.90)):
        formatted = "Read the ordinary project update."
        rows.append(
            case(
                f"safety-asr-context-block-{index:02d}",
                "safety-provider-confidence-abuse",
                [
                    memory(
                        "Brevo",
                        "Bravo",
                        scope="contextual",
                        source="Send the Bravo newsletter from the marketing console.",
                        accepted="Send the Brevo newsletter from the marketing console.",
                    )
                ],
                formatted,
                formatted,
                "suggest" if confidence >= 0.9 else "abstain",
                alternatives=[
                    {
                        "text": "Read the bravo project update.",
                        "confidence": confidence,
                        "provider": "untrusted-safety-asr",
                        "model": "voice-safety-1",
                    }
                ],
            )
        )
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows)
    path.write_text(payload, encoding="utf-8")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "cases": len(rows),
        "categories": dict(sorted(Counter(row["category"] for row in rows).items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the predeclared v7 calibration corpora.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT / "data" / "benchmark" / "v7_calibration_manifest.json",
    )
    args = parser.parse_args()
    calibration_path = ROOT / "data" / "benchmark" / "v7_calibration.jsonl"
    safety_path = ROOT / "data" / "benchmark" / "v7_calibration_safety.jsonl"
    manifest = {
        "dataset_version": VERSION,
        "status": "frozen_before_score_search",
        "roles": {
            "calibration": write_jsonl(calibration_path, calibration_cases()),
            "safety": write_jsonl(safety_path, safety_cases()),
        },
        "final_holdout_accessed": False,
    }
    manifest_path = args.manifest.resolve()
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
