from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DecisionPolicy:
    version: str
    apply_threshold: float
    suggest_threshold: float
    minimum_winner_margin: float
    fuzzy_candidate_threshold: float
    minimum_positive_context_similarity: float
    negative_context_block_threshold: float
    semantic_similarity_floor: float
    lexical_weight: float
    memory_evidence_weight: float
    context_weight: float
    phonetic_weight: float
    asr_alternative_weight: float
    negative_context_weight: float
    learned_asr_weight: float
    asr_prior_alpha: float
    asr_prior_beta: float
    asr_minimum_outcomes: int


def load_policy() -> DecisionPolicy:
    override = os.getenv("LEXITRACE_POLICY_PATH")
    if override:
        raw = Path(override).read_bytes()
    else:
        raw = files("lexitrace").joinpath("policy.toml").read_bytes()
    data = tomllib.loads(raw.decode("utf-8"))
    thresholds = data["thresholds"]
    semantic = data["semantic"]
    weights = data["weights"]
    asr_learning = data["asr_learning"]
    return DecisionPolicy(
        version=data["version"],
        apply_threshold=thresholds["apply"],
        suggest_threshold=thresholds["suggest"],
        minimum_winner_margin=thresholds["minimum_winner_margin"],
        fuzzy_candidate_threshold=thresholds["fuzzy_candidate"],
        minimum_positive_context_similarity=thresholds["minimum_positive_context"],
        negative_context_block_threshold=thresholds["negative_context_block"],
        semantic_similarity_floor=semantic["similarity_floor"],
        lexical_weight=weights["lexical"],
        memory_evidence_weight=weights["memory_evidence"],
        context_weight=weights["context"],
        phonetic_weight=weights["phonetic"],
        asr_alternative_weight=weights["asr_alternative"],
        negative_context_weight=weights["negative_context"],
        learned_asr_weight=weights["learned_asr"],
        asr_prior_alpha=asr_learning["prior_alpha"],
        asr_prior_beta=asr_learning["prior_beta"],
        asr_minimum_outcomes=asr_learning["minimum_outcomes"],
    )
