from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DecisionPolicy:
    version: str
    semantic_retrieval_mode: str
    semantic_evidence_cap: int
    feedback_scope: str
    asr_confidence_mode: str
    asr_reliability_mode: str
    authorization_score_mode: str
    context_transform: str
    apply_threshold: float
    suggest_threshold: float
    minimum_winner_margin: float
    minimum_conflict_context_advantage: float
    minimum_conflict_positive_context: float
    fuzzy_candidate_threshold: float
    minimum_positive_context_similarity: float
    negative_context_block_threshold: float
    semantic_similarity_floor: float
    lexical_weight: float
    memory_authorization_weight: float
    context_weight: float
    phonetic_weight: float
    asr_alternative_weight: float
    negative_context_weight: float
    learned_asr_weight: float
    asr_prior_alpha: float
    asr_prior_beta: float
    asr_minimum_outcomes: int
    trust_prior_alpha: float
    trust_prior_beta: float
    trust_explicit_weight: float
    trust_correction_weight: float
    trust_confirmation_weight: float
    trust_rejection_weight: float
    trust_auto_confirm_threshold: float
    trust_demote_threshold: float
    trust_minimum_positive_events: int
    trust_minimum_distinct_contexts: int


def load_policy() -> DecisionPolicy:
    override = os.getenv("LEXITRACE_POLICY_PATH")
    if override:
        raw = Path(override).read_bytes()
    else:
        raw = files("lexitrace").joinpath("policy.toml").read_bytes()
    data = tomllib.loads(raw.decode("utf-8"))
    structure = data["structure"]
    thresholds = data["thresholds"]
    semantic = data["semantic"]
    weights = data["weights"]
    asr_learning = data["asr_learning"]
    lifecycle = data["memory_lifecycle"]
    return DecisionPolicy(
        version=data["version"],
        semantic_retrieval_mode=structure["semantic_retrieval_mode"],
        semantic_evidence_cap=structure["semantic_evidence_cap"],
        feedback_scope=structure["feedback_scope"],
        asr_confidence_mode=structure["asr_confidence_mode"],
        asr_reliability_mode=structure["asr_reliability_mode"],
        authorization_score_mode=structure["authorization_score_mode"],
        context_transform=structure["context_transform"],
        apply_threshold=thresholds["apply"],
        suggest_threshold=thresholds["suggest"],
        minimum_winner_margin=thresholds["minimum_winner_margin"],
        minimum_conflict_context_advantage=thresholds["minimum_conflict_context_advantage"],
        minimum_conflict_positive_context=thresholds["minimum_conflict_positive_context"],
        fuzzy_candidate_threshold=thresholds["fuzzy_candidate"],
        minimum_positive_context_similarity=thresholds["minimum_positive_context"],
        negative_context_block_threshold=thresholds["negative_context_block"],
        semantic_similarity_floor=semantic["similarity_floor"],
        lexical_weight=weights["lexical"],
        memory_authorization_weight=weights["memory_authorization"],
        context_weight=weights["context"],
        phonetic_weight=weights["phonetic"],
        asr_alternative_weight=weights["asr_alternative"],
        negative_context_weight=weights["negative_context"],
        learned_asr_weight=weights["learned_asr"],
        asr_prior_alpha=asr_learning["prior_alpha"],
        asr_prior_beta=asr_learning["prior_beta"],
        asr_minimum_outcomes=asr_learning["minimum_outcomes"],
        trust_prior_alpha=lifecycle["prior_alpha"],
        trust_prior_beta=lifecycle["prior_beta"],
        trust_explicit_weight=lifecycle["explicit_teach_weight"],
        trust_correction_weight=lifecycle["accepted_correction_weight"],
        trust_confirmation_weight=lifecycle["confirmed_intervention_weight"],
        trust_rejection_weight=lifecycle["rejected_intervention_weight"],
        trust_auto_confirm_threshold=lifecycle["auto_confirm_threshold"],
        trust_demote_threshold=lifecycle["demote_threshold"],
        trust_minimum_positive_events=lifecycle["minimum_positive_events"],
        trust_minimum_distinct_contexts=lifecycle["minimum_distinct_contexts"],
    )
