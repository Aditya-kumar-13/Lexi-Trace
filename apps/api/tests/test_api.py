from concurrent.futures import ThreadPoolExecutor
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


def make_client(
    tmp_path: Path,
    semantic_encoder=None,
    max_request_bytes: int = 65_536,
) -> TestClient:
    database_url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    engine = build_engine(database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    app = create_app(
        Settings(
            database_url=database_url,
            cors_origins=(),
            max_request_bytes=max_request_bytes,
        ),
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


def test_formatter_context_returns_bounded_retrieval_hints_without_authorizing_edits(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        teach(client)
        response = client.post(
            "/api/v1/formatter-context",
            json={"raw_asr_text": "Review the Kiwi service dashboard."},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["retrieved_count"] == 1
        assert result["memories"][0]["canonical_form"] == "Kivi"
        assert result["memories"][0]["matched_span"] == "Kiwi"
        assert result["contract"]["stage"] == "before_formatter"
        assert result["contract"]["retrieval_is_edit_permission"] is False
        assert "retrieval only" in result["prompt_fragment"]


def test_formatter_context_exposes_ambiguous_memories_instead_of_choosing_one(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        teach(
            client,
            canonical_form="Aaditya",
            variants=["Aditya"],
            positive_context=["finance approval"],
        )
        teach(
            client,
            canonical_form="Adithya",
            variants=["Aditya"],
            positive_context=["design review"],
        )
        result = client.post(
            "/api/v1/formatter-context",
            json={"raw_asr_text": "Ask Aditya to join."},
        ).json()
        assert result["retrieved_count"] == 2
        assert all(item["ambiguous"] for item in result["memories"])
        assert {item["canonical_form"] for item in result["memories"]} == {
            "Aaditya",
            "Adithya",
        }


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
                "feedback_scope": "context",
                "corrected_text": "Buy Kiwi fruit at the market.",
            },
        )
        assert feedback.status_code == 200
        feedback_body = feedback.json()
        assert feedback_body["resulting_states"][memory["id"]] == "confirmed"
        assert feedback_body["resolved_feedback_scopes"][memory["id"]] == "context"
        assert feedback_body["trust_profiles"][memory["id"]]["negative_events"] == 0
        assert feedback_body["trust_profiles"][memory["id"]]["contextual_negative_events"] == 1
        repeated_feedback = client.post(
            f"/api/v1/decisions/{inference['trace_id']}/feedback",
            json={
                "verdict": "incorrect",
                "feedback_scope": "context",
                "corrected_text": "Buy Kiwi fruit at the market.",
            },
        )
        assert repeated_feedback.status_code == 200
        assert (
            repeated_feedback.json()["trust_profiles"][memory["id"]]["contextual_negative_events"]
            == 1
        )

        repeated = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Buy Kiwi fruit at the market."},
        ).json()
        assert repeated["action"] == "abstain"
        assert "NEGATIVE_CONTEXT_EVIDENCE" in repeated["candidates"][0]["blockers"]
        updated = client.get(f"/api/v1/memories/{memory['id']}").json()
        assert updated["context_profile"]["negative_observations"] == 1
        assert updated["context_profile"]["negative_sources"] == ["rejected_intervention"]


def test_identity_rejection_can_demote_a_contextual_memory(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        memory = teach(
            client,
            positive_context=[],
            negative_context=[],
            formatted_text="Open the Kiwi service dashboard.",
            accepted_text="Open the Kivi service dashboard.",
        )
        inference = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Open the Kiwi service dashboard."},
        ).json()
        feedback = client.post(
            f"/api/v1/decisions/{inference['trace_id']}/feedback",
            json={"verdict": "incorrect", "feedback_scope": "identity"},
        )

        assert feedback.status_code == 200
        body = feedback.json()
        assert body["resolved_feedback_scopes"][memory["id"]] == "identity"
        assert body["resulting_states"][memory["id"]] == "candidate"
        assert body["trust_profiles"][memory["id"]]["negative_events"] == 1


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


def test_candidate_instrumentation_exposes_deduplication_and_score_arithmetic(
    tmp_path: Path,
) -> None:
    with make_client(tmp_path) as client:
        teach(
            client,
            canonical_form="Aaditya",
            variants=["Aditya", "Adithya"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )
        response = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Ask Aditya to review this."},
        ).json()

        assert len(response["candidates"]) == 1
        diagnostics = response["candidate_generation"]
        assert diagnostics["scored_total"] >= 2
        assert diagnostics["unique_memory_span_keys"] == 1
        assert diagnostics["cross_variant_duplicates_removed"] >= 1
        assert diagnostics["retained_key_duplicates"] == 0

        candidate = response["candidates"][0]
        features = candidate["features"]
        contribution_keys = (
            "score_lexical_contribution",
            "score_authorization_contribution",
            "score_context_contribution",
            "score_phonetic_contribution",
            "score_asr_alternative_contribution",
            "score_learned_asr_contribution",
            "score_negative_context_contribution",
        )
        contribution_total = round(sum(features[key] for key in contribution_keys), 4)
        assert contribution_total == features["score_before_clamp"]
        assert features["score_after_clamp"] == candidate["score"]
        assert features["score_clamp_delta"] == round(
            features["score_after_clamp"] - features["score_before_clamp"], 4
        )


def test_separate_occurrences_receive_separate_context_decisions(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        teach(
            client,
            positive_context=["service deployment dashboard"],
            negative_context=["fresh fruit market"],
        )
        response = client.post(
            "/api/v1/infer",
            json={
                "formatted_text": (
                    "Review the Kiwi service deployment dashboard before the afternoon meeting. "
                    "After dinner, buy fresh kiwi fruit at the market."
                )
            },
        ).json()

        assert response["memory_aware_text"] == (
            "Review the Kivi service deployment dashboard before the afternoon meeting. "
            "After dinner, buy fresh kiwi fruit at the market."
        )
        assert len(response["candidates"]) == 2
        assert [candidate["action"] for candidate in response["candidates"]] == [
            "apply",
            "abstain",
        ]
        assert response["candidates"][0]["start"] != response["candidates"][1]["start"]
        assert "NEGATIVE_CONTEXT_EVIDENCE" in response["candidates"][1]["blockers"]
        assert response["candidates"][1]["features"]["score_negative_context_contribution"] < 0


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


def test_passive_corrections_auto_confirm_with_distinct_idempotent_evidence(
    tmp_path: Path,
) -> None:
    examples = [
        ("correction-1", "Message Aditya today.", "Message Aaditya today."),
        ("correction-2", "Ask Aditya to review it.", "Ask Aaditya to review it."),
        ("correction-3", "Email the report to Aditya.", "Email the report to Aaditya."),
    ]
    with make_client(tmp_path) as client:
        first = client.post(
            "/api/v1/observations/correction",
            json={
                "event_id": examples[0][0],
                "formatted_text": examples[0][1],
                "accepted_text": examples[0][2],
            },
        ).json()
        memory_id = first["created_memory_ids"][0]
        assert first["trust_profiles"][memory_id]["positive_events"] == 1
        assert client.get(f"/api/v1/memories/{memory_id}").json()["state"] == "candidate"

        duplicate = client.post(
            "/api/v1/observations/correction",
            json={
                "event_id": examples[0][0],
                "formatted_text": examples[0][1],
                "accepted_text": examples[0][2],
            },
        ).json()
        assert duplicate["observation_ids"] == first["observation_ids"]
        assert duplicate["trust_profiles"][memory_id]["positive_events"] == 1

        for event_id, formatted_text, accepted_text in examples[1:]:
            client.post(
                "/api/v1/observations/correction",
                json={
                    "event_id": event_id,
                    "formatted_text": formatted_text,
                    "accepted_text": accepted_text,
                },
            )

        memory = client.get(f"/api/v1/memories/{memory_id}").json()
        assert memory["state"] == "confirmed"
        assert memory["trust_profile"]["posterior_mean"] == 0.875
        assert memory["trust_profile"]["positive_events"] == 3
        assert memory["trust_profile"]["distinct_contexts"] == 3
        assert memory["trust_profile"]["reason_code"] == "STABLE"
        history = client.get(f"/api/v1/memories/{memory_id}/history").json()
        assert history[-1]["action"] == "memory_auto_confirmed"


def test_explicit_teach_event_is_idempotent(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        payload = {
            "event_id": "teach-kivi-1",
            "canonical_form": "Kivi",
            "variants": ["Kiwi"],
            "scope_mode": "global",
        }
        first = client.post("/api/v1/observations/explicit", json=payload).json()
        second = client.post("/api/v1/observations/explicit", json=payload).json()
        assert second["id"] == first["id"]
        assert second["trust_profile"]["positive_events"] == 1
        history = client.get(f"/api/v1/memories/{first['id']}/history").json()
        assert len(history) == 1


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


def test_shadow_policy_compares_decisions_without_changing_active_output(tmp_path: Path) -> None:
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
            json={
                "formatted_text": "Message Adithya before lunch.",
                "shadow_policy": {
                    "policy_id": "calibration-candidate-085",
                    "apply_threshold": 0.85,
                },
            },
        )
        assert response.status_code == 200
        result = response.json()
        assert result["action"] == "suggest"
        assert result["memory_aware_text"] == "Message Adithya before lunch."
        assert result["shadow"]["action"] == "apply"
        assert result["shadow"]["memory_aware_text"] == "Message Aaditya before lunch."
        assert result["shadow"]["action_changed"] is True
        assert result["counterfactual"]["reason_code"] == "BELOW_APPLY_THRESHOLD"


def test_counterfactual_names_safety_blocker_for_non_intervention(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        teach(client)
        response = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Discuss the Kiwi calendar tomorrow."},
        )
        assert response.status_code == 200
        result = response.json()
        assert result["memory_aware_text"] == "Discuss the Kiwi calendar tomorrow."
        assert result["counterfactual"]["reason_code"] == "CONTEXT_EVIDENCE_INSUFFICIENT"
        assert result["counterfactual"]["score_gap_to_apply"] >= 0
        assert "clear blocker" in result["counterfactual"]["minimum_change"]


def test_shadow_policy_validation_rejects_inverted_thresholds(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        response = client.post(
            "/api/v1/infer",
            json={
                "formatted_text": "Message Aditya.",
                "shadow_policy": {
                    "apply_threshold": 0.60,
                    "suggest_threshold": 0.70,
                },
            },
        )
        assert response.status_code == 422


def test_competing_memories_abstain_then_learn_a_contextual_winner(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        kivi = teach(
            client,
            canonical_form="Kivi",
            variants=["Kiwi"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )
        teach(
            client,
            canonical_form="Kiwi Labs",
            variants=["Kiwi"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )

        conflicts = client.get("/api/v1/conflicts").json()
        assert any(
            {member["canonical_form"] for member in conflict["members"]} == {"Kivi", "Kiwi Labs"}
            for conflict in conflicts
        )

        unresolved = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Review the Kiwi deployment."},
        ).json()
        assert unresolved["action"] == "suggest"
        assert unresolved["memory_aware_text"] == "Review the Kiwi deployment."
        assert all(
            "INSUFFICIENT_WINNER_MARGIN" in candidate["blockers"]
            for candidate in unresolved["candidates"][:2]
        )

        feedback = client.post(
            f"/api/v1/decisions/{unresolved['trace_id']}/feedback",
            json={
                "verdict": "correct",
                "candidate_memory_id": kivi["id"],
                "candidate_start": unresolved["candidates"][0]["start"],
            },
        )
        assert feedback.status_code == 200

        resolved = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Inspect the Kiwi deployment."},
        ).json()
        assert resolved["action"] == "apply"
        assert resolved["memory_aware_text"] == "Inspect the Kivi deployment."
        assert "CONFLICT_RESOLVED_BY_CONTEXT" in resolved["changes"][0]["reason_codes"]


def test_conflict_results_are_independent_of_teaching_order(tmp_path: Path) -> None:
    def run(order: list[tuple[str, str]], database_name: str) -> tuple[str, list[str]]:
        database_path = tmp_path / database_name
        with make_client(database_path) as client:
            for canonical, variant in order:
                teach(
                    client,
                    canonical_form=canonical,
                    variants=[variant],
                    scope_mode="global",
                    positive_context=[],
                    negative_context=[],
                )
            result = client.post(
                "/api/v1/infer",
                json={"formatted_text": "Review the Kiwi account."},
            ).json()
            return result["action"], [
                candidate["canonical_form"] for candidate in result["candidates"][:2]
            ]

    first = run([("Kivi", "Kiwi"), ("Kiwi Labs", "Kiwi")], "first")
    second = run([("Kiwi Labs", "Kiwi"), ("Kivi", "Kiwi")], "second")
    assert first == second == ("suggest", ["Kivi", "Kiwi Labs"])


def test_multiple_non_overlapping_memories_apply_in_one_transcript(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        teach(
            client,
            canonical_form="Kivi",
            variants=["Kiwi"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )
        teach(
            client,
            canonical_form="Aaditya",
            variants=["Aditya"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )
        result = client.post(
            "/api/v1/infer",
            json={"formatted_text": "Ask Aditya to review the Kiwi deployment."},
        ).json()
        assert result["action"] == "apply"
        assert result["memory_aware_text"] == "Ask Aaditya to review the Kivi deployment."
        assert {change["canonical_form"] for change in result["changes"]} == {
            "Aaditya",
            "Kivi",
        }


def test_memory_merge_preserves_aliases_and_evidence(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        target = teach(
            client,
            canonical_form="Kivi",
            variants=["Kiwi"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )
        source = teach(
            client,
            canonical_form="Kiwi Labs",
            variants=["Kiwi"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )
        response = client.post(
            f"/api/v1/memories/{target['id']}/merge",
            json={"source_memory_id": source["id"], "reason": "Same intended company"},
        )
        assert response.status_code == 200, response.text
        merged = response.json()
        assert {variant["surface_form"] for variant in merged["variants"]} == {
            "Kiwi",
            "Kiwi Labs",
        }
        assert merged["trust_profile"]["positive_events"] == 2
        assert client.get(f"/api/v1/memories/{source['id']}").status_code == 404
        history = client.get(f"/api/v1/memories/{target['id']}/history").json()
        assert history[-1]["action"] == "memory_merged"


def test_portable_export_import_and_complete_user_deletion(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        teach(
            client,
            canonical_form="Kivi",
            variants=["Kiwi"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )
        bundle = client.get("/api/v1/users/demo-user/export").json()
        assert bundle["schema_version"] == "lexitrace-portable-memory-v1"
        assert len(bundle["memories"]) == 1

        imported = client.post(
            "/api/v1/users/restored-user/import",
            json={
                "bundle_id": bundle["bundle_id"],
                "mode": "merge",
                "memories": bundle["memories"],
            },
        )
        assert imported.status_code == 200, imported.text
        assert imported.json()["imported_memories"] == 1
        restored = client.get("/api/v1/memories", params={"user_id": "restored-user"}).json()
        assert restored[0]["canonical_form"] == "Kivi"

        repeated = client.post(
            "/api/v1/users/restored-user/import",
            json={
                "bundle_id": bundle["bundle_id"],
                "mode": "merge",
                "memories": bundle["memories"],
            },
        )
        assert repeated.json()["memory_ids"] == imported.json()["memory_ids"]
        deleted = client.delete("/api/v1/users/restored-user").json()
        assert deleted["deleted_memories"] == 1
        assert deleted["deleted_observations"] >= 1
        assert client.get("/api/v1/memories", params={"user_id": "restored-user"}).json() == []


def test_request_guard_structured_errors_and_metrics(tmp_path: Path) -> None:
    with make_client(tmp_path, max_request_bytes=1_024) as client:
        request_id = "review-request-1"
        healthy = client.get("/api/v1/health", headers={"X-Request-ID": request_id})
        assert healthy.headers["X-Request-ID"] == request_id

        invalid = client.post("/api/v1/infer", json={"formatted_text": ""})
        assert invalid.status_code == 422
        assert invalid.json()["error"]["code"] == "VALIDATION_ERROR"
        assert invalid.json()["error"]["request_id"]

        oversized = client.post(
            "/api/v1/infer",
            content='{"formatted_text":"' + ("x" * 2_000) + '"}',
            headers={"Content-Type": "application/json"},
        )
        assert oversized.status_code == 413
        assert oversized.json()["error"]["code"] == "REQUEST_TOO_LARGE"

        metrics = client.get("/api/v1/metrics").json()
        assert metrics["requests"] >= 3
        assert metrics["errors"] >= 2
        assert "GET /api/v1/health" in metrics["routes"]


def test_concurrent_inference_writes_are_unique_and_lock_safe(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        teach(
            client,
            canonical_form="Kivi",
            variants=["Kiwi"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
        )

        def run(index: int) -> tuple[int, str]:
            response = client.post(
                "/api/v1/infer",
                json={"formatted_text": f"Review Kiwi deployment {index}."},
            )
            return response.status_code, response.json().get("trace_id", "")

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(run, range(16)))
        assert {status for status, _ in results} == {200}
        assert len({trace_id for _, trace_id in results}) == 16


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
            "intervention_rejected_candidate",
        ]
        memory_after = client.get(f"/api/v1/memories/{memory['id']}").json()
        trust = memory_after["trust_profile"]
        assert trust["negative_events"] == 1
        assert trust["posterior_mean"] == 0.5556
        assert trust["reason_code"] == "AWAITING_POSTERIOR"


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
