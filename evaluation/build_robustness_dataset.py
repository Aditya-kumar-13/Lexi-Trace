from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "benchmark" / "robustness.jsonl"
DATASET_VERSION = "backend-phonetic-robustness-v1"


def split_for(case_id: str) -> str:
    bucket = hashlib.sha256(case_id.encode()).digest()[0] % 5
    return "calibration" if bucket < 2 else "heldout"


def memory(
    canonical: str,
    variant: str,
    *,
    scope: str = "global",
    state: str = "confirmed",
    source_formatted: str = "",
    source_accepted: str = "",
) -> dict[str, Any]:
    return {
        "canonical_form": canonical,
        "variants": [variant],
        "scope_mode": scope,
        "state": state,
        "source_formatted": source_formatted,
        "source_accepted": source_accepted,
    }


def add_case(cases: list[dict[str, Any]], case: dict[str, Any]) -> None:
    case["dataset_version"] = DATASET_VERSION
    case["split"] = split_for(case["case_id"])
    cases.append(case)


def replace_once(text: str, source: str, target: str) -> str:
    if source not in text:
        raise ValueError(f"{source!r} is missing from {text!r}")
    return text.replace(source, target, 1)


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    global_terms = [
        ("Aaditya", "Aditya"),
        ("José", "Jose"),
        ("Sarvam", "Sarvum"),
        ("Postgres", "post grass"),
        ("Qdrant", "Q drant"),
        ("Supabase", "super base"),
        ("Figma", "fig ma"),
        ("Shivangi", "Shivangee"),
        ("Kubernetes", "Kuber net ease"),
        ("PyTorch", "pie torch"),
    ]
    global_templates = [
        "Ask {variant} to review the draft.",
        "Send the notes to {variant} today.",
        "Open the {variant} workspace.",
        "Add {variant} to the meeting agenda.",
    ]
    for term_index, (canonical, variant) in enumerate(global_terms):
        for template_index, template in enumerate(global_templates):
            formatted = template.format(variant=variant)
            add_case(
                cases,
                {
                    "case_id": f"global-exact-{term_index:02d}-{template_index:02d}",
                    "category": "global-exact-positive",
                    "memories": [memory(canonical, variant)],
                    "raw_asr_text": formatted.casefold().rstrip("."),
                    "formatted_text": formatted,
                    "expected_output": replace_once(formatted, variant, canonical),
                    "expected_action": "apply",
                },
            )

    fuzzy_terms = [
        ("Aaditya", "Aditya", "Aditiya"),
        ("Aaditya", "Aditya", "Adithya"),
        ("Sarvam", "Sarvam", "Sarvum"),
        ("Figma", "Figma", "Figmah"),
        ("Postgres", "Postgres", "Postgress"),
        ("Supabase", "Supabase", "Supabaze"),
        ("Qdrant", "Qdrant", "Qdrent"),
        ("Shivangi", "Shivangi", "Shivangee"),
    ]
    fuzzy_templates = [
        "Message {surface} before lunch.",
        "Ask {surface} to open the file.",
        "The {surface} item is ready.",
    ]
    for term_index, (canonical, variant, surface) in enumerate(fuzzy_terms):
        for template_index, template in enumerate(fuzzy_templates):
            formatted = template.format(surface=surface)
            add_case(
                cases,
                {
                    "case_id": f"global-unseen-phonetic-{term_index:02d}-{template_index:02d}",
                    "category": "global-unseen-phonetic-positive",
                    "memories": [memory(canonical, variant)],
                    "raw_asr_text": formatted.casefold().rstrip("."),
                    "formatted_text": formatted,
                    "expected_output": replace_once(formatted, surface, canonical),
                    "expected_action": "apply",
                },
            )

    boundary_cases = [
        ("Anne", "Ann", "The annual planning session starts now."),
        ("Sam", "Sam", "Use the same document for both meetings."),
        ("Kivi", "Kiwi", "Kiwis contain vitamin C."),
        ("Art", "Art", "The article was published yesterday."),
        ("May", "May", "Maybe we should postpone this."),
    ]
    for case_index, (canonical, variant, sentence) in enumerate(boundary_cases):
        for suffix in range(4):
            formatted = sentence.replace(".", f" #{suffix + 1}.")
            add_case(
                cases,
                {
                    "case_id": f"boundary-negative-{case_index:02d}-{suffix:02d}",
                    "category": "word-boundary-negative",
                    "memories": [memory(canonical, variant)],
                    "formatted_text": formatted,
                    "expected_output": formatted,
                    "expected_action": "abstain",
                },
            )

    contextual_terms = [
        (
            "Kivi",
            "Kiwi",
            "Review the Kiwi service dashboard.",
            "Review the Kivi service dashboard.",
            [
                "Inspect the Kiwi service release.",
                "Check the Kiwi dashboard deployment.",
                "Open the Kiwi service logs.",
                "Share the Kiwi dashboard report.",
                "Restart the Kiwi service worker.",
                "Audit the Kiwi dashboard permissions.",
                "Test the Kiwi service integration.",
                "Document the Kiwi deployment dashboard.",
            ],
        ),
        (
            "Postgres",
            "post grass",
            "Move the database service to post grass.",
            "Move the database service to Postgres.",
            [
                "Back up the post grass database.",
                "Restart the post grass database service.",
                "Inspect the post grass query logs.",
                "Migrate the service database to post grass.",
                "Check the post grass database index.",
                "Tune the post grass query service.",
                "Restore the post grass database snapshot.",
                "Monitor the post grass service connection.",
            ],
        ),
        (
            "Supabase",
            "super base",
            "Open the super base project dashboard.",
            "Open the Supabase project dashboard.",
            [
                "Review the super base project settings.",
                "Open the super base dashboard logs.",
                "Rotate the super base project key.",
                "Check the super base dashboard status.",
                "Invite Priya to the super base project.",
                "Inspect the super base project database.",
                "Deploy the super base dashboard update.",
                "Archive the super base project logs.",
            ],
        ),
        (
            "Qdrant",
            "Q drant",
            "Query the Q drant vector database.",
            "Query the Qdrant vector database.",
            [
                "Back up the Q drant vector collection.",
                "Inspect the Q drant database index.",
                "Query the Q drant vector collection.",
                "Restart the Q drant database node.",
                "Measure the Q drant vector latency.",
                "Create a Q drant database snapshot.",
                "Delete the Q drant vector collection.",
                "Monitor the Q drant database cluster.",
            ],
        ),
        (
            "Figma",
            "fig ma",
            "Review the fig ma design file.",
            "Review the Figma design file.",
            [
                "Open the fig ma design prototype.",
                "Share the fig ma design file.",
                "Comment on the fig ma prototype.",
                "Export the fig ma design frame.",
                "Duplicate the fig ma prototype file.",
                "Inspect the fig ma design tokens.",
                "Rename the fig ma design page.",
                "Archive the fig ma prototype file.",
            ],
        ),
        (
            "PyTorch",
            "pie torch",
            "Train the model with pie torch.",
            "Train the model with PyTorch.",
            [
                "Export the pie torch model weights.",
                "Profile the pie torch model training.",
                "Load the pie torch model checkpoint.",
                "Optimize the pie torch training loop.",
                "Test the pie torch model output.",
                "Inspect the pie torch training loss.",
                "Run the pie torch model benchmark.",
                "Document the pie torch training setup.",
            ],
        ),
    ]
    for term_index, (
        canonical,
        variant,
        source_formatted,
        source_accepted,
        targets,
    ) in enumerate(contextual_terms):
        for target_index, formatted in enumerate(targets):
            add_case(
                cases,
                {
                    "case_id": f"context-positive-{term_index:02d}-{target_index:02d}",
                    "category": "contextual-positive",
                    "memories": [
                        memory(
                            canonical,
                            variant,
                            scope="contextual",
                            source_formatted=source_formatted,
                            source_accepted=source_accepted,
                        )
                    ],
                    "raw_asr_text": formatted.casefold().rstrip("."),
                    "formatted_text": formatted,
                    "expected_output": replace_once(formatted, variant, canonical),
                    "expected_action": "apply",
                },
            )

    negative_groups = [
        (
            "Kivi",
            "Kiwi",
            "Review the Kiwi service dashboard.",
            "Review the Kivi service dashboard.",
            [
                "Slice the Kiwi fruit after breakfast.",
                "Buy Kiwi fruit at the market.",
                "Add Kiwi to the breakfast bowl.",
                "Peel the Kiwi before lunch.",
                "Blend Kiwi into the smoothie.",
                "Plant a Kiwi vine in the garden.",
                "Serve Kiwi with the fruit salad.",
                "The Kiwi fruit is ripe today.",
            ],
        ),
        (
            "Postgres",
            "post grass",
            "Move the database service to post grass.",
            "Move the database service to Postgres.",
            [
                "Place the post grass sign in the garden.",
                "Trim the post grass near the fence.",
                "Water the post grass after sunset.",
                "The post grass area needs soil.",
                "Walk past the post grass field.",
                "Paint the post grass marker green.",
                "Move the post grass seed bag outside.",
                "Photograph the post grass garden bed.",
            ],
        ),
        (
            "Supabase",
            "super base",
            "Open the super base project dashboard.",
            "Open the Supabase project dashboard.",
            [
                "The super base player reached home plate.",
                "Build a super base for the model rocket.",
                "Paint the super base before assembly.",
                "Move the super base beside the wall.",
                "That super base supports the sculpture.",
                "Measure the super base with a ruler.",
                "Pack the super base in the crate.",
                "Repair the super base after the game.",
            ],
        ),
    ]
    for group_index, (
        canonical,
        variant,
        source_formatted,
        source_accepted,
        targets,
    ) in enumerate(negative_groups):
        for repeat in range(2):
            for target_index, base in enumerate(targets):
                formatted = base.replace(".", f" #{repeat + 1}.")
                add_case(
                    cases,
                    {
                        "case_id": (
                            f"context-negative-{group_index:02d}-{repeat:02d}-{target_index:02d}"
                        ),
                        "category": "contextual-deliberate-no-change",
                        "memories": [
                            memory(
                                canonical,
                                variant,
                                scope="contextual",
                                source_formatted=source_formatted,
                                source_accepted=source_accepted,
                            )
                        ],
                        "formatted_text": formatted,
                        "expected_output": formatted,
                        "expected_action": "suggest",
                    },
                )

    for state, expected_action in (("candidate", "suggest"), ("suppressed", "abstain")):
        for index in range(12):
            formatted = f"Ask Aditya to review lifecycle draft {index + 1}."
            add_case(
                cases,
                {
                    "case_id": f"lifecycle-{state}-{index:02d}",
                    "category": f"memory-{state}",
                    "memories": [memory("Aaditya", "Aditya", state=state)],
                    "formatted_text": formatted,
                    "expected_output": formatted,
                    "expected_action": expected_action,
                },
            )

    for index in range(16):
        formatted = f"Ask Jahn to join collision meeting {index + 1}."
        add_case(
            cases,
            {
                "case_id": f"collision-{index:02d}",
                "category": "ambiguous-collision",
                "memories": [memory("John", "Jahn"), memory("Jon", "Jahn")],
                "formatted_text": formatted,
                "expected_output": formatted,
                "expected_action": "suggest",
            },
        )

    for index in range(12):
        confidence = 0.95 if index % 2 == 0 else 0.35
        expected_output = (
            f"Open the Kivi dashboard for ASR case {index + 1}."
            if confidence > 0.9
            else f"Open the company dashboard for ASR case {index + 1}."
        )
        expected_action = "apply" if confidence > 0.9 else "abstain"
        add_case(
            cases,
            {
                "case_id": f"asr-alternative-{index:02d}",
                "category": "asr-nbest-evidence",
                "memories": [memory("Kivi", "Kiwi")],
                "raw_asr_text": f"open the company dashboard for asr case {index + 1}",
                "formatted_text": f"Open the company dashboard for ASR case {index + 1}.",
                "alternatives": [
                    {
                        "text": f"Open the Kiwi dashboard for ASR case {index + 1}.",
                        "confidence": confidence,
                        "provider": "synthetic-nbest-v1",
                    }
                ],
                "expected_output": expected_output,
                "expected_action": expected_action,
            },
        )

    for index in range(20):
        formatted = f"Ask Priya to review unrelated draft {index + 1}."
        add_case(
            cases,
            {
                "case_id": f"irrelevant-memory-{index:02d}",
                "category": "irrelevant-memory",
                "memories": [memory("Aaditya", "Aditya")],
                "formatted_text": formatted,
                "expected_output": formatted,
                "expected_action": "abstain",
            },
        )

    return cases


def main() -> None:
    cases = build_cases()
    case_ids = [case["case_id"] for case in cases]
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Duplicate case IDs")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8", newline="\n") as stream:
        for case in cases:
            stream.write(json.dumps(case, ensure_ascii=False, separators=(",", ":")) + "\n")
    counts = {
        split: sum(case["split"] == split for case in cases) for split in ("calibration", "heldout")
    }
    print(json.dumps({"output": str(OUTPUT), "cases": len(cases), "splits": counts}, indent=2))


if __name__ == "__main__":
    main()
