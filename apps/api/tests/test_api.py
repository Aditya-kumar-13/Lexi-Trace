from pathlib import Path

from fastapi.testclient import TestClient
from lexitrace.config import Settings
from lexitrace.main import create_app


def make_client(tmp_path: Path) -> TestClient:
    database_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    app = create_app(Settings(database_url=database_url, cors_origins=()))
    return TestClient(app)


def teach(client: TestClient, **overrides) -> dict:
    payload = {
        "user_id": "demo-user",
        "canonical_form": "Kivi",
        "variants": ["Kiwi"],
        "scope_mode": "contextual",
        "positive_context": ["Sarvam service"],
        "negative_context": ["fruit food shopping"],
    }
    payload.update(overrides)
    response = client.post("/api/v1/observations/explicit", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_contextual_memory_applies_in_positive_context_and_abstains_in_negative_context(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        teach(client)
        positive = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Review the Sarvam Kiwi service."},
        )
        assert positive.status_code == 200
        assert positive.json()["memory_aware_text"] == "Review the Sarvam Kivi service."
        assert positive.json()["action"] == "apply"

        negative = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Buy kiwi fruit from the shop."},
        )
        assert negative.status_code == 200
        assert negative.json()["memory_aware_text"] == "Buy kiwi fruit from the shop."
        assert negative.json()["action"] == "abstain"
        assert "NEGATIVE_CONTEXT_MATCH" in negative.json()["candidates"][0]["reason_codes"]


def test_global_name_memory_applies_without_context(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        teach(
            client,
            canonical_form="Aaditya",
            variants=["Aditya"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )
        response = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Ask Aditya to review this."},
        )
        assert response.status_code == 200
        assert response.json()["memory_aware_text"] == "Ask Aaditya to review this."


def test_passive_correction_stays_candidate_until_confirmed(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        observation = client.post(
            "/api/v1/observations/correction",
            json={
                "formatted_text": "Message Aditya today.",
                "accepted_text": "Message Aaditya today.",
            },
        )
        assert observation.status_code == 201
        memory_id = observation.json()["created_memory_ids"][0]
        before = client.post("/api/v1/infer", json={"formatted_text": "Message Aditya tomorrow."})
        assert before.json()["action"] == "suggest"
        assert before.json()["memory_aware_text"] == "Message Aditya tomorrow."

        confirmed = client.patch(f"/api/v1/memories/{memory_id}", json={"state": "confirmed"})
        assert confirmed.status_code == 200
        after = client.post("/api/v1/infer", json={"formatted_text": "Message Aditya tomorrow."})
        assert after.json()["memory_aware_text"] == "Message Aaditya tomorrow."


def test_reset_removes_all_user_state(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        teach(client)
        client.post("/api/v1/infer", json={"formatted_text": "Sarvam Kiwi service"})
        response = client.post("/api/v1/reset")
        assert response.status_code == 200
        assert response.json() == {
            "deleted_memories": 1,
            "deleted_observations": 1,
            "deleted_decisions": 1,
        }
        assert client.get("/api/v1/memories").json() == []


def test_unseen_phonetic_variant_can_apply_when_similarity_is_strong(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        teach(
            client,
            canonical_form="Aaditya",
            variants=["Aditya"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )
        response = client.post("/api/v1/infer", json={"formatted_text": "Ask Aditiya to join."})
        assert response.status_code == 200
        result = response.json()
        assert result["memory_aware_text"] == "Ask Aaditya to join."
        assert result["candidates"][0]["features"]["match_method"] == "phonetic_fuzzy"


def test_short_fuzzy_word_is_not_treated_as_a_safe_candidate(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        teach(
            client,
            canonical_form="Sam",
            variants=["Sam"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )
        response = client.post("/api/v1/infer", json={"formatted_text": "Use the same document."})
        assert response.status_code == 200
        assert response.json()["memory_aware_text"] == "Use the same document."
        assert response.json()["candidates"] == []


def test_memory_history_and_rejected_feedback_demote_an_intervention(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        memory = teach(
            client,
            canonical_form="Aaditya",
            variants=["Aditya"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )
        inference = client.post(
            "/api/v1/infer", json={"formatted_text": "Ask Aditya to join."}
        ).json()
        feedback = client.post(
            f"/api/v1/decisions/{inference['trace_id']}/feedback",
            json={"verdict": "incorrect", "corrected_text": "Ask Aditya to join."},
        )
        assert feedback.status_code == 200
        assert feedback.json()["resulting_states"][memory["id"]] == "candidate"

        history = client.get(f"/api/v1/memories/{memory['id']}/history")
        assert history.status_code == 200
        assert [item["action"] for item in history.json()] == [
            "explicit_teach",
            "intervention_rejected",
        ]
        memory_after = client.get(f"/api/v1/memories/{memory['id']}").json()
        assert memory_after["contradiction_count"] == 1
        assert memory_after["evidence_confidence"] == 0.75
