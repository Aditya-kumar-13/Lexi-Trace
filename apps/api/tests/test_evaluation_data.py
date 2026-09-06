import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_robustness_dataset_is_fixed_varied_and_predeclared() -> None:
    path = ROOT / "data" / "benchmark" / "robustness.jsonl"
    cases = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    assert len(cases) == 252
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert {case["dataset_version"] for case in cases} == {"backend-phonetic-robustness-v1"}
    assert {case["split"] for case in cases} == {"calibration", "heldout"}

    categories = {case["category"] for case in cases}
    assert {
        "global-exact-positive",
        "global-unseen-phonetic-positive",
        "word-boundary-negative",
        "contextual-positive",
        "contextual-deliberate-no-change",
        "memory-candidate",
        "memory-suppressed",
        "ambiguous-collision",
        "asr-nbest-evidence",
        "irrelevant-memory",
    } <= categories

    for case in cases:
        bucket = hashlib.sha256(case["case_id"].encode()).digest()[0] % 5
        expected_split = "calibration" if bucket < 2 else "heldout"
        assert case["split"] == expected_split
        if case["expected_action"] == "apply":
            assert case["expected_output"] != case["formatted_text"]
        else:
            assert case["expected_output"] == case["formatted_text"]
