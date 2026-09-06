from pathlib import Path

from fastapi.testclient import TestClient
from lexitrace.config import Settings
from lexitrace.database import Base, build_engine
from lexitrace.main import create_app


class DomainSemanticEncoder:
    enabled = True
    model_name = "test/domain-encoder"

    def encode(self, text: str) -> list[float]:
        normalized = text.casefold()
        if any(term in normalized for term in ("dashboard", "service", "platform", "deployment")):
            return [1.0, 0.0, 0.0]
        if any(term in normalized for term in ("fruit", "breakfast", "slice")):
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]

    def status(self) -> dict:
        return {
            "enabled": True,
            "model": self.model_name,
            "state": "ready",
            "error": None,
        }


class SpySemanticEncoder:
    enabled = True
    model_name = "test/spy-encoder"

    def __init__(self) -> None:
        self.calls = 0

    def encode(self, text: str) -> list[float]:
        self.calls += 1
        return [1.0, 0.0]

    def status(self) -> dict:
        return {
            "enabled": True,
            "model": self.model_name,
            "state": "ready",
            "error": None,
        }


def make_client(tmp_path: Path, semantic_encoder=None) -> TestClient:
    database_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    app = create_app(
        Settings(database_url=database_url, cors_origins=()),
        semantic_encoder_override=semantic_encoder,
    )
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
        assert "NEGATIVE_CONTEXT_EVIDENCE" in negative.json()["candidates"][0]["blockers"]


def test_correction_observation_builds_context_profile_and_generalizes(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        observation = client.post(
            "/api/v1/observations/correction",
            json={
                "formatted_text": "Review the Kiwi service dashboard.",
                "accepted_text": "Review the Kivi service dashboard.",
                "confirm_candidates": True,
            },
        )
        assert observation.status_code == 201
        memory_id = observation.json()["created_memory_ids"][0]
        memory = client.get(f"/api/v1/memories/{memory_id}").json()
        learned_features = {item["feature"] for item in memory["context_profile"]["positive"]}
        assert "token:service" in learned_features
        assert "token:dashboard" in learned_features
        assert memory["context_profile"]["positive_sources"] == ["accepted_correction"]
        evidence = client.get(f"/api/v1/memories/{memory_id}/context-evidence").json()
        assert evidence
        assert {item["observation_id"] for item in evidence} == set(
            observation.json()["observation_ids"]
        )
        assert {item["source_type"] for item in evidence} == {"accepted_correction"}

        related = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Check the Kiwi service deployment."},
        ).json()
        assert related["memory_aware_text"] == "Check the Kivi service deployment."
        assert related["action"] == "apply"
        assert related["candidates"][0]["blockers"] == []

        unrelated = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Slice the kiwi after breakfast."},
        ).json()
        assert unrelated["memory_aware_text"] == "Slice the kiwi after breakfast."
        assert "CONTEXT_EVIDENCE_INSUFFICIENT" in unrelated["candidates"][0]["blockers"]
        assert unrelated["candidates"][0]["score"] != 0.89


def test_semantic_profile_generalizes_without_shared_context_words(tmp_path: Path) -> None:
    with make_client(tmp_path, DomainSemanticEncoder()) as client:
        memory = teach(
            client,
            positive_context=[],
            negative_context=[],
            formatted_text="Review the Kiwi service dashboard.",
            accepted_text="Review the Kivi service dashboard.",
        )
        assert memory["semantic_evidence_count"] == 1
        semantic_evidence = client.get(f"/api/v1/memories/{memory['id']}/semantic-evidence").json()
        assert semantic_evidence[0]["model_name"] == "test/domain-encoder"
        assert semantic_evidence[0]["dimension"] == 3

        related = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Inspect the Kiwi platform deployment."},
        ).json()
        candidate = related["candidates"][0]
        assert related["memory_aware_text"] == "Inspect the Kivi platform deployment."
        assert candidate["features"]["sparse_positive_similarity"] == 0.0
        assert candidate["features"]["semantic_positive_similarity"] == 1.0
        assert candidate["blockers"] == []

        unrelated = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Slice the kiwi after breakfast."},
        ).json()
        assert unrelated["memory_aware_text"] == "Slice the kiwi after breakfast."
        assert "CONTEXT_EVIDENCE_INSUFFICIENT" in unrelated["candidates"][0]["blockers"]


def test_high_confidence_asr_alternative_can_retrieve_an_unseen_surface(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        teach(
            client,
            canonical_form="Kivi",
            variants=["Kiwi"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )
        response = client.post(
            "/api/v1/infer",
            json={
                "formatted_text": "Open the company dashboard.",
                "alternatives": [
                    {
                        "text": "Open the Kiwi dashboard.",
                        "confidence": 0.95,
                        "provider": "test-asr",
                    }
                ],
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["memory_aware_text"] == "Open the Kivi dashboard."
        candidate = result["candidates"][0]
        assert candidate["features"]["match_method"] == "asr_alternative"
        assert candidate["features"]["asr_provider"] == "test-asr"
        assert "ASR_ALTERNATIVE_SUPPORT" in candidate["reason_codes"]


def test_rejected_intervention_adds_negative_context_evidence(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        memory = teach(
            client,
            positive_context=[],
            negative_context=[],
            formatted_text="Buy Kiwi fruit at the market.",
            accepted_text="Buy Kivi fruit at the market.",
        )
        inference = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Buy Kiwi fruit at the market."},
        ).json()
        assert inference["action"] == "apply"
        feedback = client.post(
            f"/api/v1/decisions/{inference['trace_id']}/feedback",
            json={
                "verdict": "incorrect",
                "corrected_text": "Buy Kiwi fruit at the market.",
            },
        )
        assert feedback.status_code == 200
        client.patch(f"/api/v1/memories/{memory['id']}", json={"state": "confirmed"})

        repeated = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Buy Kiwi fruit at the market."},
        ).json()
        assert repeated["action"] == "abstain"
        assert "NEGATIVE_CONTEXT_EVIDENCE" in repeated["candidates"][0]["blockers"]
        updated = client.get(f"/api/v1/memories/{memory['id']}").json()
        assert updated["context_profile"]["negative_observations"] == 1
        assert updated["context_profile"]["negative_sources"] == ["rejected_intervention"]


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


def test_global_exact_memory_skips_semantics_and_prunes_overlapping_fuzzy_spans(
    tmp_path: Path,
) -> None:
    encoder = SpySemanticEncoder()
    with make_client(tmp_path, encoder) as client:
        teach(
            client,
            canonical_form="Kubernetes",
            variants=["Kuber net ease"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )
        response = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Open the Kuber net ease dashboard."},
        ).json()

        assert response["memory_aware_text"] == "Open the Kubernetes dashboard."
        assert response["action"] == "apply"
        assert len(response["candidates"]) == 1
        assert response["candidates"][0]["features"]["match_method"] == "exact"
        assert response["candidates"][0]["features"]["semantic_model"] == "not_required"
        assert encoder.calls == 0


def test_manual_context_override_remains_auditable_and_replaceable(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        memory = teach(
            client,
            positive_context=["service"],
            negative_context=[],
        )
        updated = client.patch(
            f"/api/v1/memories/{memory['id']}",
            json={"positive_context": ["deployment"]},
        )
        assert updated.status_code == 200
        profile_features = {
            item["feature"] for item in updated.json()["context_profile"]["positive"]
        }
        assert "token:deployment" in profile_features
        assert "token:service" not in profile_features
        evidence = client.get(f"/api/v1/memories/{memory['id']}/context-evidence").json()
        assert {item["source_type"] for item in evidence} == {"manual_override"}


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


def test_confirmed_suggestions_learn_provider_specific_asr_reliability(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        memory = teach(
            client,
            canonical_form="Aaditya",
            variants=["Aditya"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )
        request = {
            "formatted_text": "Ask Adithya to review this.",
            "asr": {
                "provider": "acme-asr",
                "model": "voice-2",
                "confidence": 0.97,
            },
        }

        for expected_observations in range(3):
            inference = client.post("/api/v1/infer", json=request).json()
            candidate = inference["candidates"][0]
            assert inference["action"] == "suggest"
            assert candidate["features"]["asr_reliability_observations"] == expected_observations
            feedback = client.post(
                f"/api/v1/decisions/{inference['trace_id']}/feedback",
                json={
                    "verdict": "correct",
                    "candidate_memory_id": memory["id"],
                    "candidate_start": candidate["start"],
                },
            )
            assert feedback.status_code == 200
            assert len(feedback.json()["asr_outcome_ids"]) == 1

        learned = client.post("/api/v1/infer", json=request).json()
        candidate = learned["candidates"][0]
        assert learned["action"] == "apply"
        assert learned["memory_aware_text"] == "Ask Aaditya to review this."
        assert candidate["features"]["asr_reliability_state"] == "active"
        assert candidate["features"]["asr_reliability_observations"] == 3
        assert candidate["features"]["asr_reliability_posterior"] == 0.5714
        assert "LEARNED_ASR_RELIABILITY" in candidate["reason_codes"]

        other_model = client.post(
            "/api/v1/infer",
            json={**request, "asr": {**request["asr"], "model": "voice-3"}},
        ).json()
        assert other_model["action"] == "suggest"
        assert other_model["candidates"][0]["features"]["asr_reliability_state"] == "cold_start"

        evidence = client.get(f"/api/v1/memories/{memory['id']}/asr-evidence")
        assert evidence.status_code == 200
        assert len(evidence.json()) == 3
        assert {item["provider"] for item in evidence.json()} == {"acme-asr"}
        assert {item["model"] for item in evidence.json()} == {"voice-2"}

        repeated_feedback = client.post(
            f"/api/v1/decisions/{inference['trace_id']}/feedback",
            json={
                "verdict": "correct",
                "candidate_memory_id": memory["id"],
                "candidate_start": candidate["start"],
            },
        )
        assert repeated_feedback.status_code == 200
        assert client.get(f"/api/v1/memories/{memory['id']}/asr-evidence").json() == evidence.json()


def test_learned_asr_signal_cannot_bypass_context_safety(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        memory = teach(
            client,
            canonical_form="Aaditya",
            variants=["Aditya"],
            scope_mode="contextual",
            positive_context=[],
            negative_context=[],
            formatted_text="Ask Adithya about the service deployment.",
            accepted_text="Ask Aaditya about the service deployment.",
        )
        asr = {"provider": "acme-asr", "model": "voice-2", "confidence": 0.99}
        for _ in range(3):
            inference = client.post(
                "/api/v1/infer",
                json={
                    "formatted_text": "Ask Adithya about the service deployment.",
                    "asr": asr,
                },
            ).json()
            candidate = inference["candidates"][0]
            client.post(
                f"/api/v1/decisions/{inference['trace_id']}/feedback",
                json={
                    "verdict": "correct",
                    "candidate_memory_id": memory["id"],
                    "candidate_start": candidate["start"],
                },
            )

        unrelated = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Slice Adithya with the fruit.", "asr": asr},
        ).json()
        candidate = unrelated["candidates"][0]
        assert candidate["features"]["asr_reliability_state"] == "active"
        assert "CONTEXT_EVIDENCE_INSUFFICIENT" in candidate["blockers"]
        assert unrelated["action"] != "apply"
        assert unrelated["memory_aware_text"] == "Slice Adithya with the fruit."


def test_feedback_requires_a_visible_target_when_nothing_was_applied(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        teach(
            client,
            canonical_form="Aaditya",
            variants=["Aditya"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )
        inference = client.post(
            "/api/v1/infer", json={"formatted_text": "Ask Adithya to join."}
        ).json()
        assert inference["action"] == "suggest"
        feedback = client.post(
            f"/api/v1/decisions/{inference['trace_id']}/feedback",
            json={"verdict": "correct"},
        )
        assert feedback.status_code == 422
