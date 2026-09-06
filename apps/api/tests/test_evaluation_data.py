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


def test_asr_learning_journeys_cover_activation_and_drift() -> None:
    path = ROOT / "data" / "benchmark" / "asr_journeys.jsonl"
    journeys = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    assert len(journeys) >= 4
    assert len({journey["journey_id"] for journey in journeys}) == len(journeys)
    identifiers = {journey["journey_id"] for journey in journeys}
    assert {
        "learn-repeated-primary-confusion",
        "provider-drift-does-not-transfer",
        "model-drift-does-not-transfer",
        "context-blocker-outranks-learned-asr",
    } <= identifiers
    assert all(
        sum(event.get("feedback") == "correct" for event in journey["events"]) >= 3
        for journey in journeys
    )


def test_lifecycle_journeys_cover_replay_diversity_and_state_changes() -> None:
    path = ROOT / "data" / "benchmark" / "lifecycle_journeys.jsonl"
    journeys = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    assert len(journeys) >= 5
    identifiers = {journey["journey_id"] for journey in journeys}
    assert {
        "diverse-passive-corrections-auto-confirm",
        "replayed-event-has-zero-influence",
        "same-context-does-not-satisfy-diversity",
        "contradiction-demotes-confirmed-memory",
        "explicit-suppression-is-authoritative",
    } <= identifiers


def test_conflict_journeys_cover_ties_learning_order_and_multiple_edits() -> None:
    path = ROOT / "data" / "benchmark" / "conflict_journeys.jsonl"
    journeys = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    assert len(journeys) == 4
    assert {journey["journey_id"] for journey in journeys} == {
        "feedback-resolves-contextual-collision",
        "unresolved-tie-never-silently-chooses",
        "learned-context-selects-collision-winner",
        "multiple-independent-memories-apply",
    }
    assert any(len(journey["memories"]) > 1 for journey in journeys)
    assert any(len(journey["events"]) > 1 for journey in journeys)


def test_semantic_safety_journeys_separate_learning_events_from_scored_cases() -> None:
    path = ROOT / "data" / "benchmark" / "v7_semantic_safety_development.jsonl"
    journeys = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    assert {journey["journey_id"] for journey in journeys} == {
        "kivi-negative-feedback-neighborhood",
        "kiwi-overlapping-memory-collision",
    }
    events = [event for journey in journeys for event in journey["events"]]
    learning_events = [event for event in events if event.get("score_case") is False]
    scored_inferences = [
        event for event in events if event["type"] == "infer" and event.get("score_case", True)
    ]

    assert len(learning_events) == 3
    assert all(event.get("feedback") == "incorrect" for event in learning_events)
    assert len(scored_inferences) == 13
    assert sum(event["expected_action"] == "abstain" for event in scored_inferences) == 4
    assert sum(event["expected_action"] == "suggest" for event in scored_inferences) == 2
    assert sum(event["expected_action"] == "apply" for event in scored_inferences) == 7


def test_asr_route_development_data_covers_rank_help_and_contradiction() -> None:
    path = ROOT / "data" / "benchmark" / "v7_asr_route_development.jsonl"
    journeys = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    assert {journey["journey_id"] for journey in journeys} == {
        "rank-backoff-can-recover-a-stable-confusion",
        "rank-pooling-must-respect-contradictory-outcomes",
    }
    events = [event for journey in journeys for event in journey["events"]]
    learning_events = [event for event in events if event.get("score_case") is False]
    assert sum(event.get("feedback") == "correct" for event in learning_events) == 6
    assert sum(event.get("feedback") == "incorrect" for event in learning_events) == 3
    assert {
        alternative["rank"] for event in events for alternative in event.get("alternatives", [])
    } == {
        1,
        2,
    }


def test_semantic_storage_journey_exceeds_cap_and_contains_duplicates() -> None:
    path = ROOT / "data" / "benchmark" / "v7_semantic_storage_development.jsonl"
    journey = json.loads(path.read_text(encoding="utf-8").strip())
    teaching = [event for event in journey["events"] if event["type"] == "teach"]
    inferences = [event for event in journey["events"] if event["type"] == "infer"]
    contexts = [event["formatted_text"] for event in teaching]

    assert len(teaching) == 18
    assert len(set(contexts)) == 16
    assert len(inferences) == 8
    assert all(event["expected_action"] == "apply" for event in inferences)
