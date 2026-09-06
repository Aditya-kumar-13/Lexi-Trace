from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "benchmark" / "v7_adversarial_round1.jsonl"


def memory(canonical: str, variant: str, scope: str = "global") -> dict:
    return {
        "canonical_form": canonical,
        "variants": [variant],
        "scope_mode": scope,
        "state": "confirmed",
        "source_formatted": "",
        "source_accepted": "",
    }


def row(
    case_id: str,
    category: str,
    memories: list[dict],
    text: str,
    output: str,
    action: str,
    **extra: object,
) -> dict:
    return {
        "case_id": case_id,
        "category": category,
        "memories": memories,
        "formatted_text": text,
        "expected_output": output,
        "expected_action": action,
        "dataset_version": "v7-adversarial-round1-v1",
        "split": "adversarial_discovery",
        **extra,
    }


def build() -> list[dict]:
    rows: list[dict] = []
    unrelated = [
        "The audience shouted Bravo after the encore.",
        "Everyone yelled Bravo when the curtain fell.",
        "Her final note earned a loud Bravo.",
        "The review simply said Bravo to the cast.",
        "We heard Bravo from the balcony.",
        "The conductor smiled when they called Bravo.",
        "One spectator whispered Bravo at the end.",
        "They printed Bravo beneath the concert photo.",
    ]
    contextual = memory("Brevo", "Bravo", "contextual")
    contextual["source_formatted"] = "Send the Bravo email campaign from the marketing console."
    contextual["source_accepted"] = "Send the Brevo email campaign from the marketing console."
    for index, text in enumerate(unrelated):
        rows.append(
            row(
                f"rt1-provider-abuse-{index:02d}",
                "provider-confidence-abuse",
                [contextual],
                text,
                text,
                "suggest",
                asr={"provider": "hostile-asr", "model": "voice-x", "confidence": 1.0},
            )
        )

    unicode_terms = [
        ("Zoë", "Zoe"),
        ("Nguyễn", "Nguyen"),
        ("Łukasz", "Lukasz"),
        ("İrem", "Irem"),
        ("Søren", "Soren"),
        ("François", "Francois"),
        ("Núria", "Nuria"),
        ("Māori", "Maori"),
    ]
    for index, (canonical, variant) in enumerate(unicode_terms):
        text = f"🔊 Ask {variant} to review café notes #{index + 1}."
        rows.append(
            row(
                f"rt1-unicode-{index:02d}",
                "unicode-offset",
                [memory(canonical, variant)],
                text,
                text.replace(variant, canonical),
                "apply",
            )
        )

    for index in range(8):
        memories = [memory("Aaditya", "Aditya"), memory("Adithya", "Aditya")]
        if index % 2:
            memories.reverse()
        text = f"Ask Aditya to inspect ambiguous draft {index + 1}."
        rows.append(
            row(
                f"rt1-collision-{index:02d}",
                "reversed-insertion-collision",
                memories,
                text,
                text,
                "suggest",
            )
        )

    repeated = [
        "Zoe asked Zoe to join.",
        "Zoe called Zoe before lunch.",
        "Zoe sent Zoe the report.",
        "Zoe and Zoe reviewed it.",
        "Message Zoe, then remind Zoe.",
        "Zoe thanked Zoe publicly.",
        "Invite Zoe after Zoe replies.",
        "Zoe owns the note Zoe shared.",
    ]
    for index, text in enumerate(repeated):
        rows.append(
            row(
                f"rt1-repeated-{index:02d}",
                "multiple-independent-spans",
                [memory("Zoë", "Zoe")],
                text,
                text.replace("Zoe", "Zoë"),
                "apply",
            )
        )

    code_switched = [
        "Kal bazaar se Kiwi phal lena.",
        "Mujhe do Kiwi fruit chahiye.",
        "Aaj Kiwi ka juice bana do.",
        "Fridge mein Kiwi fruit rakha hai.",
        "Kiwi phal ka chilka hatao.",
        "Bacchon ke liye Kiwi slice karo.",
        "Market wali Kiwi ka daam kya hai?",
        "Nashta ke saath Kiwi fruit dena.",
    ]
    kivi = memory("Kivi", "Kiwi", "contextual")
    kivi["source_formatted"] = "Deploy the Kiwi speech service through the production dashboard."
    kivi["source_accepted"] = "Deploy the Kivi speech service through the production dashboard."
    for index, text in enumerate(code_switched):
        rows.append(
            row(
                f"rt1-code-switch-{index:02d}",
                "code-switched-negative-context",
                [kivi],
                text,
                text,
                "suggest",
            )
        )
    return rows


def main() -> None:
    rows = build()
    if len(rows) != 40:
        raise RuntimeError(f"Round 1 must contain exactly 40 cases, got {len(rows)}")
    payload = "".join(
        json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n" for item in rows
    )
    OUTPUT.write_text(payload, encoding="utf-8")
    print(
        json.dumps(
            {
                "path": OUTPUT.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
                "cases": len(rows),
                "categories": dict(sorted(Counter(item["category"] for item in rows).items())),
                "role": "adversarial_discovery",
                "final_holdout_accessed": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
