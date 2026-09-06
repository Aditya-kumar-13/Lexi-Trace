from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
import uuid
from collections import defaultdict
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher

import jellyfish
from rapidfuzz.fuzz import ratio
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .models import (
    AsrOutcome,
    ContextEmbedding,
    ContextEvidence,
    Decision,
    Memory,
    MemoryVariant,
    MemoryVersion,
    Observation,
)
from .policy import load_policy
from .semantic import SemanticEncoder

ENGINE_VERSION = "0.8.0"
POLICY = load_policy()
APPLY_THRESHOLD = POLICY.apply_threshold
SUGGEST_THRESHOLD = POLICY.suggest_threshold
MINIMUM_WINNER_MARGIN = POLICY.minimum_winner_margin
FUZZY_CANDIDATE_THRESHOLD = POLICY.fuzzy_candidate_threshold
MIN_POSITIVE_CONTEXT_SIMILARITY = POLICY.minimum_positive_context_similarity
NEGATIVE_CONTEXT_BLOCK_THRESHOLD = POLICY.negative_context_block_threshold
CONTEXT_WINDOW_TOKENS = 6
SEMANTIC_SIMILARITY_FLOOR = POLICY.semantic_similarity_floor
ASR_PRIOR_ALPHA = POLICY.asr_prior_alpha
ASR_PRIOR_BETA = POLICY.asr_prior_beta
ASR_MINIMUM_OUTCOMES = POLICY.asr_minimum_outcomes
TOKEN_PATTERN = re.compile(r"\w+(?:['’-]\w+)*", re.UNICODE)
STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "but",
    "by",
    "for",
    "from",
    "had",
    "has",
    "have",
    "he",
    "her",
    "his",
    "i",
    "in",
    "is",
    "it",
    "its",
    "me",
    "my",
    "of",
    "on",
    "or",
    "our",
    "she",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "to",
    "was",
    "we",
    "were",
    "will",
    "with",
    "you",
    "your",
}


def normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def context_tokens(values: list[str] | str) -> set[str]:
    if isinstance(values, str):
        values = [values]
    return {
        normalize(match.group(0))
        for value in values
        for match in TOKEN_PATTERN.finditer(value)
        if len(normalize(match.group(0))) > 1
    }


def metaphone(value: str) -> str:
    return jellyfish.metaphone(normalize(value))


def find_phrase_spans(text: str, phrase: str) -> list[tuple[int, int, str]]:
    escaped = re.escape(phrase).replace(r"\ ", r"\s+")
    pattern = re.compile(rf"(?<!\w){escaped}(?!\w)", re.IGNORECASE | re.UNICODE)
    return [(match.start(), match.end(), match.group(0)) for match in pattern.finditer(text)]


ContextFeatureMap = dict[str, tuple[str, float, str]]


def extract_context_features(
    text: str,
    source_span: str,
    *,
    source_type: str,
    start: int | None = None,
    end: int | None = None,
) -> ContextFeatureMap:
    """Extract a bounded, explainable context fingerprint around a corrected span."""
    tokens = list(TOKEN_PATTERN.finditer(text))
    if not tokens:
        return {}
    if start is None or end is None:
        located = find_phrase_spans(text, source_span)
        if located:
            start, end, _ = located[0]
    source_indexes = [
        index
        for index, token in enumerate(tokens)
        if start is not None and end is not None and token.start() < end and start < token.end()
    ]
    if source_indexes:
        left = max(0, source_indexes[0] - CONTEXT_WINDOW_TOKENS)
        right = min(len(tokens), source_indexes[-1] + CONTEXT_WINDOW_TOKENS + 1)
        selected_indexes = [
            index for index in range(left, right) if index not in set(source_indexes)
        ]
    else:
        source_terms = context_tokens(source_span)
        selected_indexes = [
            index
            for index, token in enumerate(tokens)
            if normalize(token.group(0)) not in source_terms
        ]

    useful: list[tuple[int, str, float]] = []
    for index in selected_indexes:
        term = normalize(tokens[index].group(0))
        if len(term) <= 1 or term in STOPWORDS or term.isdigit():
            continue
        if source_indexes:
            distance = min(abs(index - source_index) for source_index in source_indexes)
            weight = max(0.55, 1.0 - 0.08 * max(0, distance - 1))
        else:
            weight = 0.7
        useful.append((index, term, weight))

    features: ContextFeatureMap = {
        f"token:{term}": ("token", weight, source_type) for _, term, weight in useful
    }
    for (left_index, left_term, left_weight), (
        right_index,
        right_term,
        right_weight,
    ) in zip(useful, useful[1:], strict=False):
        if right_index - left_index <= 2:
            features[f"bigram:{left_term} {right_term}"] = (
                "bigram",
                1.25 * min(left_weight, right_weight),
                source_type,
            )
    return features


def manual_context_features(
    phrases: list[str], *, source_type: str = "manual_override"
) -> ContextFeatureMap:
    """Convert optional advanced overrides into explicit, auditable evidence."""
    features: ContextFeatureMap = {}
    for phrase in phrases:
        terms = [
            normalize(match.group(0))
            for match in TOKEN_PATTERN.finditer(phrase)
            if normalize(match.group(0)) not in STOPWORDS
        ]
        for term in terms:
            features[f"token:{term}"] = ("token", 1.0, source_type)
        for left, right in zip(terms, terms[1:], strict=False):
            features[f"bigram:{left} {right}"] = ("bigram", 1.25, source_type)
    return features


def merge_context_features(*groups: ContextFeatureMap) -> ContextFeatureMap:
    merged: ContextFeatureMap = {}
    for group in groups:
        for feature, details in group.items():
            if feature not in merged or details[1] > merged[feature][1]:
                merged[feature] = details
    return merged


def store_context_evidence(
    session: Session,
    *,
    memory: Memory,
    observation: Observation,
    polarity: str,
    context_text: str,
    features: ContextFeatureMap,
    reliability: float,
) -> None:
    for feature, (feature_kind, weight, source_type) in features.items():
        session.add(
            ContextEvidence(
                memory=memory,
                observation=observation,
                polarity=polarity,
                feature=feature,
                feature_kind=feature_kind,
                weight=round(weight * abs(reliability), 4),
                source_type=source_type,
                context_text=context_text,
            )
        )


def semantic_context_text(
    text: str,
    source_span: str,
    *,
    start: int | None = None,
    end: int | None = None,
) -> str:
    """Mask the remembered surface form so semantics come from its surroundings."""
    if start is None or end is None:
        located = find_phrase_spans(text, source_span)
        if located:
            start, end, _ = located[0]
    if start is not None and end is not None:
        return " ".join((text[:start] + " [TERM] " + text[end:]).split())
    return " ".join(text.split())


def context_fingerprint(
    text: str,
    source_span: str,
    *,
    start: int | None = None,
    end: int | None = None,
) -> str | None:
    if not text.strip():
        return None
    masked = normalize(semantic_context_text(text, source_span, start=start, end=end))
    return hashlib.sha256(masked.encode("utf-8")).hexdigest()


def store_semantic_evidence(
    session: Session,
    *,
    memory: Memory,
    observation: Observation,
    polarity: str,
    context_text: str,
    source_span: str,
    source_type: str,
    reliability: float,
    semantic_encoder: SemanticEncoder | None,
    start: int | None = None,
    end: int | None = None,
) -> bool:
    if semantic_encoder is None or not semantic_encoder.enabled or not context_text:
        return False
    masked_context = semantic_context_text(
        context_text,
        source_span,
        start=start,
        end=end,
    )
    vector = semantic_encoder.encode(masked_context)
    if vector is None:
        return False
    session.add(
        ContextEmbedding(
            memory=memory,
            observation=observation,
            polarity=polarity,
            model_name=semantic_encoder.model_name,
            dimension=len(vector),
            vector_json=json.dumps(vector, separators=(",", ":")),
            weight=abs(reliability),
            source_type=source_type,
            context_text=masked_context,
        )
    )
    return True


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return 0.0
    left_norm = sum(value * value for value in left) ** 0.5
    right_norm = sum(value * value for value in right) ** 0.5
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right, strict=True)) / (left_norm * right_norm)


def semantic_context_similarity(
    memory: Memory,
    current_vector: list[float] | None,
    polarity: str,
    model_name: str,
) -> tuple[float, int]:
    if current_vector is None:
        return 0.0, 0
    vectors: list[tuple[list[float], float]] = []
    for evidence in memory.semantic_evidence:
        if evidence.polarity != polarity or evidence.model_name != model_name:
            continue
        vector = json.loads(evidence.vector_json)
        if len(vector) == len(current_vector):
            vectors.append((vector, evidence.weight))
    if not vectors:
        return 0.0, 0
    total_weight = sum(weight for _, weight in vectors)
    centroid = [
        sum(vector[index] * weight for vector, weight in vectors) / total_weight
        for index in range(len(current_vector))
    ]
    return max(-1.0, min(1.0, _cosine(current_vector, centroid))), len(vectors)


def aggregate_semantic_profile(memory: Memory) -> dict:
    grouped: dict[tuple[str, str], list[list[float]]] = defaultdict(list)
    for evidence in memory.semantic_evidence:
        grouped[(evidence.model_name, evidence.polarity)].append(json.loads(evidence.vector_json))
    models: dict[str, dict[str, float | int]] = {}
    for (model_name, polarity), vectors in grouped.items():
        dimension = len(vectors[0])
        centroid = [
            sum(vector[index] for vector in vectors) / len(vectors) for index in range(dimension)
        ]
        coherence = sum(_cosine(vector, centroid) for vector in vectors) / len(vectors)
        model_profile = models.setdefault(model_name, {})
        model_profile[f"{polarity}_observations"] = len(vectors)
        model_profile[f"{polarity}_coherence"] = round(coherence, 4)
    return {"models": models}


def aggregate_context_profile(memory: Memory) -> dict:
    weights: dict[str, dict[str, float]] = {
        "positive": defaultdict(float),
        "negative": defaultdict(float),
    }
    counts: dict[str, dict[str, int]] = {
        "positive": defaultdict(int),
        "negative": defaultdict(int),
    }
    observations: dict[str, set[str]] = {"positive": set(), "negative": set()}
    sources: dict[str, set[str]] = {"positive": set(), "negative": set()}
    feature_observations: dict[str, dict[str, set[str]]] = {
        "positive": defaultdict(set),
        "negative": defaultdict(set),
    }
    feature_sources: dict[str, dict[str, set[str]]] = {
        "positive": defaultdict(set),
        "negative": defaultdict(set),
    }
    kinds: dict[str, str] = {}
    for evidence in memory.context_evidence:
        weights[evidence.polarity][evidence.feature] += evidence.weight
        counts[evidence.polarity][evidence.feature] += 1
        observations[evidence.polarity].add(evidence.observation_id)
        sources[evidence.polarity].add(evidence.source_type)
        feature_observations[evidence.polarity][evidence.feature].add(evidence.observation_id)
        feature_sources[evidence.polarity][evidence.feature].add(evidence.source_type)
        kinds[evidence.feature] = evidence.feature_kind

    profile: dict[str, object] = {}
    for polarity in ("positive", "negative"):
        ranked = sorted(weights[polarity].items(), key=lambda item: (-item[1], item[0]))
        profile[polarity] = [
            {
                "feature": feature,
                "kind": kinds[feature],
                "weight": round(weight, 4),
                "evidence_count": counts[polarity][feature],
                "observation_ids": sorted(feature_observations[polarity][feature]),
                "sources": sorted(feature_sources[polarity][feature]),
            }
            for feature, weight in ranked[:20]
        ]
        profile[f"{polarity}_observations"] = len(observations[polarity])
        profile[f"{polarity}_sources"] = sorted(sources[polarity])
    return profile


def context_similarity(
    memory: Memory, current_features: ContextFeatureMap, polarity: str
) -> tuple[float, list[str]]:
    profile: dict[str, float] = defaultdict(float)
    for evidence in memory.context_evidence:
        if evidence.polarity == polarity:
            profile[evidence.feature] += evidence.weight
    if not profile or not current_features:
        return 0.0, []
    current = {feature: details[1] for feature, details in current_features.items()}
    shared = set(profile) & set(current)
    dot_product = sum(profile[feature] * current[feature] for feature in shared)
    profile_norm = sum(weight * weight for weight in profile.values()) ** 0.5
    current_norm = sum(weight * weight for weight in current.values()) ** 0.5
    similarity = dot_product / max(0.0001, profile_norm * current_norm)
    matched = sorted(shared, key=lambda feature: profile[feature], reverse=True)
    return min(1.0, similarity), matched[:5]


def generate_candidate_spans(text: str, variant: MemoryVariant) -> list[tuple[int, int, str, str]]:
    """Return safe exact, fuzzy, and phonetic spans for one learned variant."""
    results: list[tuple[int, int, str, str]] = [
        (start, end, surface, "exact")
        for start, end, surface in find_phrase_spans(text, variant.surface_form)
    ]
    tokens = list(TOKEN_PATTERN.finditer(text))
    target_token_count = max(1, len(list(TOKEN_PATTERN.finditer(variant.surface_form))))
    allowed_lengths = {
        length
        for length in (target_token_count - 1, target_token_count, target_token_count + 1)
        if 1 <= length <= 4
    }
    for start_index in range(len(tokens)):
        for token_count in allowed_lengths:
            end_index = start_index + token_count
            if end_index > len(tokens):
                continue
            selected = tokens[start_index:end_index]
            separators = [
                text[left.end() : right.start()]
                for left, right in zip(selected, selected[1:], strict=False)
            ]
            if any(separator.strip(" -‐‑–—") for separator in separators):
                continue
            start, end = selected[0].start(), selected[-1].end()
            surface = text[start:end]
            normalized_surface = normalize(surface)
            similarity = ratio(normalized_surface, variant.normalized_form) / 100
            surface_key = metaphone(surface)
            phonetic_equal = bool(surface_key and surface_key == variant.metaphone_key)
            exact = normalized_surface == variant.normalized_form
            compact_length = min(
                len(normalized_surface.replace(" ", "")),
                len(variant.normalized_form.replace(" ", "")),
            )

            if exact:
                method = "exact"
            elif compact_length <= 4:
                if not (phonetic_equal and similarity >= 0.90):
                    continue
                method = "phonetic_fuzzy"
            elif phonetic_equal and similarity >= FUZZY_CANDIDATE_THRESHOLD:
                method = "phonetic_fuzzy"
            elif phonetic_equal:
                method = "phonetic"
            elif similarity >= FUZZY_CANDIDATE_THRESHOLD:
                method = "fuzzy"
            else:
                continue
            results.append((start, end, surface, method))

    method_priority = {"exact": 4, "phonetic_fuzzy": 3, "phonetic": 2, "fuzzy": 1}
    best_by_span: dict[tuple[int, int], tuple[int, int, str, str]] = {}
    for result in results:
        key = (result[0], result[1])
        previous = best_by_span.get(key)
        if previous is None or method_priority[result[3]] > method_priority[previous[3]]:
            best_by_span[key] = result
    selected = list(best_by_span.values())
    exact_spans = [(start, end) for start, end, _, method in selected if method == "exact"]
    return [
        result
        for result in selected
        if result[3] == "exact"
        or not any(left < result[1] and result[0] < right for left, right in exact_spans)
    ]


def generate_asr_alternative_spans(
    formatted_text: str,
    alternative_text: str,
    variant: MemoryVariant,
) -> list[tuple[int, int, str]]:
    """Align variant evidence in an ASR alternative back to an editable formatted span."""
    formatted_tokens = list(TOKEN_PATTERN.finditer(formatted_text))
    alternative_tokens = list(TOKEN_PATTERN.finditer(alternative_text))
    if not formatted_tokens or not alternative_tokens:
        return []
    matcher = SequenceMatcher(
        None,
        [normalize(token.group(0)) for token in formatted_tokens],
        [normalize(token.group(0)) for token in alternative_tokens],
        autojunk=False,
    )
    opcodes = matcher.get_opcodes()
    aligned: list[tuple[int, int, str]] = []
    for alt_start, alt_end, _, _ in generate_candidate_spans(alternative_text, variant):
        alternative_indexes = [
            index
            for index, token in enumerate(alternative_tokens)
            if token.start() < alt_end and alt_start < token.end()
        ]
        formatted_indexes: set[int] = set()
        for alternative_index in alternative_indexes:
            for tag, left_start, left_end, right_start, right_end in opcodes:
                if not (right_start <= alternative_index < right_end):
                    continue
                if tag == "equal":
                    formatted_indexes.add(left_start + alternative_index - right_start)
                elif tag == "replace":
                    formatted_indexes.update(range(left_start, left_end))
                break
        if not formatted_indexes or len(formatted_indexes) > 4:
            continue
        ordered = sorted(formatted_indexes)
        if ordered != list(range(ordered[0], ordered[-1] + 1)):
            continue
        start = formatted_tokens[ordered[0]].start()
        end = formatted_tokens[ordered[-1]].end()
        aligned.append((start, end, formatted_text[start:end]))
    return list(dict.fromkeys(aligned))


@dataclass(slots=True)
class TraceCandidate:
    memory_id: str
    canonical_form: str
    input_span: str
    output_span: str
    start: int
    end: int
    score: float
    action: str
    reason_codes: list[str]
    blockers: list[str]
    features: dict[str, float | str | bool]


def _asr_reliability(
    memory: Memory,
    *,
    provider: str,
    model_name: str,
    rank: int,
    source_form: str,
) -> dict[str, float | int | str | bool]:
    """Estimate one exact confusion route from immutable outcomes and a skeptical prior."""
    provider_key = normalize(provider)
    model_key = normalize(model_name)
    source_key = normalize(source_form)
    matches = [
        outcome
        for outcome in memory.asr_outcomes
        if normalize(outcome.provider) == provider_key
        and normalize(outcome.model_name) == model_key
        and outcome.rank == rank
        and outcome.source_normalized == source_key
        and outcome.target_normalized == memory.canonical_normalized
    ]
    accepted = sum(outcome.accepted for outcome in matches)
    rejected = len(matches) - accepted
    posterior = (ASR_PRIOR_ALPHA + accepted) / (ASR_PRIOR_ALPHA + ASR_PRIOR_BETA + len(matches))
    active = len(matches) >= ASR_MINIMUM_OUTCOMES
    return {
        "state": "active" if active else "cold_start",
        "active": active,
        "observations": len(matches),
        "accepted": accepted,
        "rejected": rejected,
        "posterior_mean": round(posterior, 4),
    }


def aggregate_asr_profile(memory: Memory) -> dict:
    groups: dict[tuple[str, str, int, str, str], list[AsrOutcome]] = defaultdict(list)
    for outcome in memory.asr_outcomes:
        key = (
            outcome.provider,
            outcome.model_name,
            outcome.rank,
            outcome.source_normalized,
            outcome.target_normalized,
        )
        groups[key].append(outcome)
    summaries = []
    for (provider, model_name, rank, source, target), outcomes in sorted(groups.items()):
        accepted = sum(outcome.accepted for outcome in outcomes)
        posterior = (ASR_PRIOR_ALPHA + accepted) / (
            ASR_PRIOR_ALPHA + ASR_PRIOR_BETA + len(outcomes)
        )
        summaries.append(
            {
                "provider": provider,
                "model": model_name,
                "rank": rank,
                "source": source,
                "target": target,
                "observations": len(outcomes),
                "accepted": accepted,
                "rejected": len(outcomes) - accepted,
                "posterior_mean": round(posterior, 4),
                "state": "active" if len(outcomes) >= ASR_MINIMUM_OUTCOMES else "cold_start",
            }
        )
    return {
        "prior": {"alpha": ASR_PRIOR_ALPHA, "beta": ASR_PRIOR_BETA},
        "minimum_outcomes": ASR_MINIMUM_OUTCOMES,
        "groups": summaries,
    }


def memory_trust_profile(memory: Memory) -> dict:
    """Derive memory trust entirely from observation events under the versioned policy."""
    alpha = POLICY.trust_prior_alpha
    beta = POLICY.trust_prior_beta
    positive_events = 0
    negative_events = 0
    weighted_positive = 0.0
    weighted_negative = 0.0
    contexts: set[str] = set()
    sources: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"events": 0, "positive_weight": 0.0, "negative_weight": 0.0}
    )
    weights = {
        "explicit_teach": POLICY.trust_explicit_weight,
        "state_override_confirmed": POLICY.trust_explicit_weight,
        "accepted_correction": POLICY.trust_correction_weight,
        "intervention_feedback": POLICY.trust_confirmation_weight,
    }
    for observation in memory.observations:
        if observation.evidence_type not in weights:
            continue
        if observation.evidence_type == "intervention_feedback" and not observation.accepted:
            weight = POLICY.trust_rejection_weight
            beta += weight
            weighted_negative += weight
            negative_events += 1
            source = sources["rejected_intervention"]
            source["events"] = int(source["events"]) + 1
            source["negative_weight"] = float(source["negative_weight"]) + weight
            continue
        if not observation.accepted:
            continue
        weight = weights[observation.evidence_type]
        alpha += weight
        weighted_positive += weight
        positive_events += 1
        source = sources[observation.evidence_type]
        source["events"] = int(source["events"]) + 1
        source["positive_weight"] = float(source["positive_weight"]) + weight
        fingerprint = observation.context_fingerprint or context_fingerprint(
            observation.formatted_text,
            observation.source_span,
        )
        if fingerprint:
            contexts.add(fingerprint)

    posterior = alpha / (alpha + beta)
    confirmation_gates = {
        "posterior": posterior >= POLICY.trust_auto_confirm_threshold,
        "positive_events": positive_events >= POLICY.trust_minimum_positive_events,
        "distinct_contexts": len(contexts) >= POLICY.trust_minimum_distinct_contexts,
    }
    if memory.state == "suppressed":
        recommendation = "hold_suppressed"
        reason_code = "EXPLICITLY_SUPPRESSED"
    elif memory.state == "candidate" and all(confirmation_gates.values()):
        recommendation = "confirm"
        reason_code = "AUTO_CONFIRM_EVIDENCE_SATISFIED"
    elif (
        memory.state == "confirmed"
        and negative_events > 0
        and posterior < POLICY.trust_demote_threshold
    ):
        recommendation = "demote"
        reason_code = "POSTERIOR_BELOW_DEMOTION_THRESHOLD"
    else:
        recommendation = "hold"
        failed_gate = next(
            (name for name, passed in confirmation_gates.items() if not passed), None
        )
        reason_code = (
            f"AWAITING_{failed_gate.upper()}"
            if memory.state == "candidate" and failed_gate
            else "STABLE"
        )
    return {
        "method": "weighted_beta_posterior",
        "policy_version": POLICY.version,
        "posterior_mean": round(posterior, 4),
        "alpha": round(alpha, 4),
        "beta": round(beta, 4),
        "positive_events": positive_events,
        "negative_events": negative_events,
        "weighted_positive": round(weighted_positive, 4),
        "weighted_negative": round(weighted_negative, 4),
        "distinct_contexts": len(contexts),
        "confirmation_gates": confirmation_gates,
        "recommendation": recommendation,
        "reason_code": reason_code,
        "sources": dict(sorted(sources.items())),
    }


def reconcile_memory_state(memory: Memory, *, force_confirm: bool = False) -> dict:
    previous = memory.state
    before = memory_trust_profile(memory)
    if force_confirm and memory.state != "suppressed":
        memory.state = "confirmed"
        transition_reason = "EXPLICIT_CONFIRMATION"
    elif before["recommendation"] == "confirm":
        memory.state = "confirmed"
        transition_reason = str(before["reason_code"])
    elif before["recommendation"] == "demote":
        memory.state = "candidate"
        transition_reason = str(before["reason_code"])
    else:
        transition_reason = str(before["reason_code"])
    return {
        "previous_state": previous,
        "new_state": memory.state,
        "changed": previous != memory.state,
        "reason_code": transition_reason,
        "trust": memory_trust_profile(memory),
    }


def memory_snapshot(memory: Memory) -> dict:
    return {
        "canonical_form": memory.canonical_form,
        "state": memory.state,
        "scope_mode": memory.scope_mode,
        "trust_profile": memory_trust_profile(memory),
        "positive_context": json.loads(memory.positive_context_json),
        "negative_context": json.loads(memory.negative_context_json),
        "context_profile": aggregate_context_profile(memory),
        "semantic_profile": aggregate_semantic_profile(memory),
        "asr_profile": aggregate_asr_profile(memory),
        "variants": sorted(variant.surface_form for variant in memory.variants),
    }


def record_memory_version(
    session: Session,
    memory: Memory,
    *,
    action: str,
    reason: str,
    actor: str = "system",
) -> MemoryVersion:
    session.flush()
    session.refresh(memory, attribute_names=["variants"])
    latest = session.scalar(
        select(func.max(MemoryVersion.version_number)).where(MemoryVersion.memory_id == memory.id)
    )
    version = MemoryVersion(
        memory_id=memory.id,
        version_number=(latest or 0) + 1,
        action=action,
        reason=reason,
        actor=actor,
        snapshot_json=json.dumps(memory_snapshot(memory), sort_keys=True),
    )
    session.add(version)
    return version


def memory_to_dict(memory: Memory) -> dict:
    return {
        "id": memory.id,
        "user_id": memory.user_id,
        "canonical_form": memory.canonical_form,
        "state": memory.state,
        "scope_mode": memory.scope_mode,
        "trust_profile": memory_trust_profile(memory),
        "positive_context": json.loads(memory.positive_context_json),
        "negative_context": json.loads(memory.negative_context_json),
        "context_evidence_count": len(memory.context_evidence),
        "context_profile": aggregate_context_profile(memory),
        "semantic_evidence_count": len(memory.semantic_evidence),
        "semantic_profile": aggregate_semantic_profile(memory),
        "asr_evidence_count": len(memory.asr_outcomes),
        "asr_profile": aggregate_asr_profile(memory),
        "variants": [
            {
                "id": variant.id,
                "surface_form": variant.surface_form,
                "normalized_form": variant.normalized_form,
                "metaphone_key": variant.metaphone_key,
            }
            for variant in memory.variants
        ],
        "created_at": memory.created_at,
        "updated_at": memory.updated_at,
    }


def replace_manual_context_evidence(
    session: Session,
    *,
    memory: Memory,
    positive_context: list[str] | None,
    negative_context: list[str] | None,
) -> None:
    """Keep optional advanced overrides synchronized with auditable evidence rows."""
    selected = {
        "positive": positive_context,
        "negative": negative_context,
    }
    if all(phrases is None for phrases in selected.values()):
        return
    for polarity, phrases in selected.items():
        if phrases is None:
            continue
        session.execute(
            delete(ContextEvidence).where(
                ContextEvidence.memory_id == memory.id,
                ContextEvidence.polarity == polarity,
                ContextEvidence.source_type == "manual_override",
            )
        )
    observation = Observation(
        user_id=memory.user_id,
        memory=memory,
        evidence_type="manual_context_update",
        source_span="",
        target_span=memory.canonical_form,
        reliability=1.0,
        reason_code="USER_OVERRIDE",
    )
    session.add(observation)
    session.flush()
    for polarity, phrases in selected.items():
        if phrases is None:
            continue
        store_context_evidence(
            session,
            memory=memory,
            observation=observation,
            polarity=polarity,
            context_text=" | ".join(phrases),
            features=manual_context_features(phrases),
            reliability=1.0,
        )


def apply_memory_state_override(session: Session, *, memory: Memory, state: str) -> None:
    """Apply an explicit user state decision and preserve its provenance."""
    memory.state = state
    observation = Observation(
        user_id=memory.user_id,
        memory=memory,
        evidence_type=("state_override_confirmed" if state == "confirmed" else "state_override"),
        target_span=memory.canonical_form,
        reliability=1.0,
        accepted=state == "confirmed",
        reason_code=f"USER_SET_{state.upper()}",
        source_event_id=f"state:{uuid.uuid4()}",
    )
    session.add(observation)


def teach_explicit(
    session: Session,
    *,
    user_id: str,
    canonical_form: str,
    variants: list[str],
    scope_mode: str,
    positive_context: list[str],
    negative_context: list[str],
    raw_asr_text: str = "",
    formatted_text: str = "",
    accepted_text: str = "",
    event_id: str | None = None,
    semantic_encoder: SemanticEncoder | None = None,
) -> Memory:
    normalized_canonical = normalize(canonical_form)
    memory = session.scalar(
        select(Memory).where(
            Memory.user_id == user_id,
            Memory.canonical_normalized == normalized_canonical,
        )
    )
    if memory is not None and event_id:
        existing_observation = session.scalar(
            select(Observation).where(
                Observation.user_id == user_id,
                Observation.memory_id == memory.id,
                Observation.source_event_id == event_id,
            )
        )
        if existing_observation is not None:
            return memory
    if memory is None:
        memory = Memory(
            user_id=user_id,
            canonical_form=canonical_form,
            canonical_normalized=normalized_canonical,
            state="confirmed",
            scope_mode=scope_mode,
            positive_context_json=json.dumps(positive_context),
            negative_context_json=json.dumps(negative_context),
        )
        session.add(memory)
        session.flush()
    else:
        memory.canonical_form = canonical_form
        memory.state = "confirmed"
        memory.scope_mode = scope_mode
        memory.positive_context_json = json.dumps(positive_context)
        memory.negative_context_json = json.dumps(negative_context)

    existing = {item.normalized_form: item for item in memory.variants}
    for variant_text in variants:
        normalized_variant = normalize(variant_text)
        if normalized_variant in existing:
            continue
        session.add(
            MemoryVariant(
                memory_id=memory.id,
                surface_form=variant_text,
                normalized_form=normalized_variant,
                metaphone_key=metaphone(variant_text),
            )
        )

    observation = Observation(
        user_id=user_id,
        memory=memory,
        evidence_type="explicit_teach",
        raw_asr_text=raw_asr_text,
        formatted_text=formatted_text,
        accepted_text=accepted_text,
        source_span=", ".join(variants),
        target_span=canonical_form,
        reliability=1.0,
        source_event_id=event_id or f"explicit:{uuid.uuid4()}",
        context_fingerprint=context_fingerprint(
            formatted_text or accepted_text or raw_asr_text,
            variants[0],
        ),
    )
    session.add(observation)
    session.flush()

    context_text = formatted_text or accepted_text or raw_asr_text
    context_span = variants[0] if formatted_text or raw_asr_text else canonical_form
    learned_positive = (
        extract_context_features(
            context_text,
            context_span,
            source_type="explicit_example",
        )
        if context_text
        else {}
    )
    positive_features = merge_context_features(
        learned_positive,
        manual_context_features(positive_context),
    )
    negative_features = manual_context_features(negative_context)
    store_context_evidence(
        session,
        memory=memory,
        observation=observation,
        polarity="positive",
        context_text=context_text or " | ".join(positive_context),
        features=positive_features,
        reliability=1.0,
    )
    store_context_evidence(
        session,
        memory=memory,
        observation=observation,
        polarity="negative",
        context_text=" | ".join(negative_context),
        features=negative_features,
        reliability=1.0,
    )
    if context_text:
        store_semantic_evidence(
            session,
            memory=memory,
            observation=observation,
            polarity="positive",
            context_text=context_text,
            source_span=context_span,
            source_type="explicit_example",
            reliability=1.0,
            semantic_encoder=semantic_encoder,
        )
    record_memory_version(
        session,
        memory,
        action="explicit_teach",
        reason="User explicitly taught or reinforced this memory",
        actor="user",
    )
    session.commit()
    session.refresh(memory)
    return memory


def observe_correction(
    session: Session,
    *,
    user_id: str,
    raw_asr_text: str,
    formatted_text: str,
    accepted_text: str,
    confirm_candidates: bool,
    event_id: str | None = None,
    semantic_encoder: SemanticEncoder | None = None,
    enable_auto_lifecycle: bool = True,
) -> tuple[list[str], list[str], list[dict[str, str]]]:
    matcher = SequenceMatcher(None, formatted_text.split(), accepted_text.split(), autojunk=False)
    observation_ids: list[str] = []
    memory_ids: list[str] = []
    rejected: list[dict[str, str]] = []
    source_event_id = event_id or f"correction:{uuid.uuid4()}"

    for tag, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        if tag == "equal":
            continue
        source_tokens = formatted_text.split()[left_start:left_end]
        target_tokens = accepted_text.split()[right_start:right_end]
        source_span = " ".join(source_tokens).strip('.,!?;:"()[]{}')
        target_span = " ".join(target_tokens).strip('.,!?;:"()[]{}')
        if tag != "replace" or not source_span or not target_span:
            rejected.append(
                {"source": source_span, "target": target_span, "reason": "NON_REPLACEMENT_EDIT"}
            )
            continue
        if len(source_tokens) > 4 or len(target_tokens) > 4:
            rejected.append(
                {"source": source_span, "target": target_span, "reason": "SPAN_TOO_LARGE"}
            )
            continue
        if normalize(source_span) == normalize(target_span):
            rejected.append(
                {"source": source_span, "target": target_span, "reason": "LOW_INFORMATION"}
            )
            continue

        normalized_target = normalize(target_span)
        memory = session.scalar(
            select(Memory).where(
                Memory.user_id == user_id,
                Memory.canonical_normalized == normalized_target,
            )
        )
        if memory is not None:
            existing_observation = session.scalar(
                select(Observation).where(
                    Observation.user_id == user_id,
                    Observation.memory_id == memory.id,
                    Observation.source_event_id == source_event_id,
                )
            )
            if existing_observation is not None:
                observation_ids.append(existing_observation.id)
                memory_ids.append(memory.id)
                continue
        if memory is None:
            memory = Memory(
                user_id=user_id,
                canonical_form=target_span,
                canonical_normalized=normalized_target,
                state="confirmed" if confirm_candidates else "candidate",
                scope_mode="contextual",
            )
            session.add(memory)
            session.flush()
            session.add(
                MemoryVariant(
                    memory_id=memory.id,
                    surface_form=source_span,
                    normalized_form=normalize(source_span),
                    metaphone_key=metaphone(source_span),
                )
            )
        else:
            if confirm_candidates:
                memory.state = "confirmed"
            existing_variant = next(
                (
                    variant
                    for variant in memory.variants
                    if variant.normalized_form == normalize(source_span)
                ),
                None,
            )
            if existing_variant is None:
                session.add(
                    MemoryVariant(
                        memory_id=memory.id,
                        surface_form=source_span,
                        normalized_form=normalize(source_span),
                        metaphone_key=metaphone(source_span),
                    )
                )
            else:
                pass

        observation = Observation(
            user_id=user_id,
            memory=memory,
            evidence_type="accepted_correction",
            raw_asr_text=raw_asr_text,
            formatted_text=formatted_text,
            accepted_text=accepted_text,
            source_span=source_span,
            target_span=target_span,
            reliability=1.0,
            source_event_id=source_event_id,
            context_fingerprint=context_fingerprint(formatted_text, source_span),
        )
        session.add(observation)
        session.flush()
        store_context_evidence(
            session,
            memory=memory,
            observation=observation,
            polarity="positive",
            context_text=formatted_text,
            features=extract_context_features(
                formatted_text,
                source_span,
                source_type="accepted_correction",
            ),
            reliability=observation.reliability,
        )
        store_semantic_evidence(
            session,
            memory=memory,
            observation=observation,
            polarity="positive",
            context_text=formatted_text,
            source_span=source_span,
            source_type="accepted_correction",
            reliability=observation.reliability,
            semantic_encoder=semantic_encoder,
        )
        if enable_auto_lifecycle or confirm_candidates:
            transition = reconcile_memory_state(memory, force_confirm=confirm_candidates)
        else:
            transition = {
                "previous_state": memory.state,
                "new_state": memory.state,
                "changed": False,
                "reason_code": "AUTO_LIFECYCLE_DISABLED",
            }
        record_memory_version(
            session,
            memory,
            action=("memory_auto_confirmed" if transition["changed"] else "correction_observed"),
            reason=(
                "Accepted word-level correction; lifecycle "
                f"{transition['previous_state']} -> {transition['new_state']} "
                f"({transition['reason_code']})"
            ),
            actor="system",
        )
        observation_ids.append(observation.id)
        memory_ids.append(memory.id)

    session.commit()
    return observation_ids, list(dict.fromkeys(memory_ids)), rejected


def _score_candidate(
    *,
    memory: Memory,
    variant: MemoryVariant,
    input_text: str,
    input_span: str,
    match_method: str,
    start: int,
    end: int,
    semantic_encoder: SemanticEncoder | None,
    semantic_vector_cache: dict[str, list[float] | None],
    trust_profile: dict,
    asr_confidence: float = 0.0,
    asr_provider: str = "",
    asr_model: str = "",
    asr_rank: int = 1,
    provider_confidence: float | None = None,
    enable_learned_asr: bool = True,
) -> tuple[float, list[str], list[str], dict[str, float | str | bool]]:
    current = extract_context_features(
        input_text,
        input_span,
        source_type="inference",
        start=start,
        end=end,
    )
    memory_trust = float(trust_profile["posterior_mean"])
    memory_authorized = memory.state == "confirmed"
    sparse_positive, positive_matches = context_similarity(memory, current, "positive")
    sparse_negative, negative_matches = context_similarity(memory, current, "negative")
    has_sparse_positive = any(
        evidence.polarity == "positive" for evidence in memory.context_evidence
    )
    masked_context = semantic_context_text(
        input_text,
        input_span,
        start=start,
        end=end,
    )
    semantic_required = memory.scope_mode == "contextual" or bool(memory.semantic_evidence)
    semantic_model = (
        semantic_encoder.model_name
        if semantic_required and semantic_encoder is not None and semantic_encoder.enabled
        else "not_required"
        if not semantic_required
        else "disabled"
    )
    if semantic_required and masked_context not in semantic_vector_cache:
        semantic_vector_cache[masked_context] = (
            semantic_encoder.encode(masked_context)
            if semantic_encoder is not None and semantic_encoder.enabled
            else None
        )
    current_vector = semantic_vector_cache.get(masked_context)
    semantic_positive, semantic_positive_count = semantic_context_similarity(
        memory,
        current_vector,
        "positive",
        semantic_model,
    )
    semantic_negative, semantic_negative_count = semantic_context_similarity(
        memory,
        current_vector,
        "negative",
        semantic_model,
    )
    normalized_semantic_positive = max(
        0.0,
        (semantic_positive - SEMANTIC_SIMILARITY_FLOOR) / (1.0 - SEMANTIC_SIMILARITY_FLOOR),
    )
    normalized_semantic_negative = max(
        0.0,
        (semantic_negative - SEMANTIC_SIMILARITY_FLOOR) / (1.0 - SEMANTIC_SIMILARITY_FLOOR),
    )
    positive_similarity = max(sparse_positive, normalized_semantic_positive)
    negative_similarity = max(sparse_negative, normalized_semantic_negative)
    has_positive_profile = has_sparse_positive or semantic_positive_count > 0
    string_similarity = ratio(normalize(input_span), variant.normalized_form) / 100
    lexical_signal = max(string_similarity, 0.96 * asr_confidence)
    phonetic_match = metaphone(input_span) == variant.metaphone_key
    reasons: list[str] = [f"{match_method.upper()}_CANDIDATE"]
    blockers: list[str] = []
    asr_reliability = (
        _asr_reliability(
            memory,
            provider=asr_provider,
            model_name=asr_model,
            rank=asr_rank,
            source_form=input_span,
        )
        if asr_provider
        else {
            "state": "not_supplied",
            "active": False,
            "observations": 0,
            "accepted": 0,
            "rejected": 0,
            "posterior_mean": 0.0,
        }
    )

    if memory.state != "confirmed":
        blockers.append("MEMORY_NOT_CONFIRMED")
    if memory.scope_mode == "contextual":
        if not has_positive_profile:
            blockers.append("CONTEXT_PROFILE_COLD_START")
        elif positive_similarity < MIN_POSITIVE_CONTEXT_SIMILARITY:
            blockers.append("CONTEXT_EVIDENCE_INSUFFICIENT")
    if positive_similarity >= MIN_POSITIVE_CONTEXT_SIMILARITY:
        reasons.append("POSITIVE_CONTEXT_EVIDENCE")
    if (
        negative_similarity >= NEGATIVE_CONTEXT_BLOCK_THRESHOLD
        and negative_similarity >= positive_similarity
    ):
        blockers.append("NEGATIVE_CONTEXT_EVIDENCE")
    if phonetic_match:
        reasons.append("PHONETIC_MATCH")
    if asr_confidence > 0:
        reasons.append("ASR_ALTERNATIVE_SUPPORT")
    if asr_provider and asr_reliability["active"] and enable_learned_asr:
        reasons.append("LEARNED_ASR_RELIABILITY")
    elif asr_provider and asr_reliability["active"]:
        reasons.append("LEARNED_ASR_DISABLED")
    elif asr_provider:
        reasons.append("ASR_RELIABILITY_COLD_START")
    if memory.semantic_evidence and current_vector is None:
        reasons.append("SEMANTIC_ENCODER_UNAVAILABLE")
    if semantic_positive_count:
        reasons.append("SEMANTIC_CONTEXT_PROFILE")

    context_signal = (
        1.0 if memory.scope_mode == "global" else min(1.0, (positive_similarity**0.35) * 1.2)
    )
    score = (
        POLICY.lexical_weight * lexical_signal
        + POLICY.memory_authorization_weight * memory_authorized
        + POLICY.context_weight * context_signal
        + (POLICY.phonetic_weight if phonetic_match else 0.0)
        + POLICY.asr_alternative_weight * asr_confidence
        + POLICY.learned_asr_weight
        * float(asr_reliability["posterior_mean"])
        * bool(asr_reliability["active"])
        * enable_learned_asr
        - POLICY.negative_context_weight * negative_similarity
    )
    score = max(0.0, min(1.0, score))
    reasons.extend(blockers)
    features: dict[str, float | str | bool] = {
        "string_similarity": round(string_similarity, 4),
        "lexical_signal": round(lexical_signal, 4),
        "phonetic_match": phonetic_match,
        "asr_alternative_confidence": round(asr_confidence, 4),
        "asr_provider": asr_provider,
        "asr_model": asr_model,
        "asr_rank": asr_rank,
        "asr_provider_confidence": (
            round(provider_confidence, 4) if provider_confidence is not None else "not_supplied"
        ),
        "asr_reliability_state": str(asr_reliability["state"]),
        "asr_reliability_observations": int(asr_reliability["observations"]),
        "asr_reliability_accepted": int(asr_reliability["accepted"]),
        "asr_reliability_rejected": int(asr_reliability["rejected"]),
        "asr_reliability_posterior": float(asr_reliability["posterior_mean"]),
        "asr_reliability_contribution": round(
            POLICY.learned_asr_weight
            * float(asr_reliability["posterior_mean"])
            * bool(asr_reliability["active"])
            * enable_learned_asr,
            4,
        ),
        "memory_trust_posterior": memory_trust,
        "memory_authorized": memory_authorized,
        "memory_trust_positive_events": int(trust_profile["positive_events"]),
        "memory_trust_negative_events": int(trust_profile["negative_events"]),
        "memory_trust_reason": str(trust_profile["reason_code"]),
        "positive_context_similarity": round(positive_similarity, 4),
        "negative_context_similarity": round(negative_similarity, 4),
        "sparse_positive_similarity": round(sparse_positive, 4),
        "sparse_negative_similarity": round(sparse_negative, 4),
        "semantic_positive_similarity": round(semantic_positive, 4),
        "semantic_negative_similarity": round(semantic_negative, 4),
        "semantic_margin": round(semantic_positive - semantic_negative, 4),
        "semantic_positive_observations": semantic_positive_count,
        "semantic_negative_observations": semantic_negative_count,
        "semantic_model": semantic_model,
        "positive_evidence_matches": ", ".join(positive_matches),
        "negative_evidence_matches": ", ".join(negative_matches),
        "context_evidence_count": len(memory.context_evidence),
        "memory_state": memory.state,
        "scope_mode": memory.scope_mode,
        "match_method": match_method,
    }
    return score, reasons, blockers, features


def infer(
    session: Session,
    *,
    user_id: str,
    raw_asr_text: str,
    formatted_text: str,
    alternatives: list[dict] | None = None,
    asr: dict | None = None,
    enable_learned_asr: bool = True,
    semantic_encoder: SemanticEncoder | None = None,
) -> tuple[Decision, dict]:
    started = time.perf_counter()
    memories = session.scalars(
        select(Memory).where(Memory.user_id == user_id, Memory.state != "suppressed")
    ).all()
    candidates_by_key: dict[tuple[str, int, int], TraceCandidate] = {}
    semantic_vector_cache: dict[str, list[float] | None] = {}

    for memory in memories:
        trust_profile = memory_trust_profile(memory)
        for variant in memory.variants:
            for start, end, matched, match_method in generate_candidate_spans(
                formatted_text, variant
            ):
                if normalize(matched) == memory.canonical_normalized:
                    continue
                score, reasons, blockers, features = _score_candidate(
                    memory=memory,
                    variant=variant,
                    input_text=formatted_text,
                    input_span=matched,
                    match_method=match_method,
                    start=start,
                    end=end,
                    semantic_encoder=semantic_encoder,
                    semantic_vector_cache=semantic_vector_cache,
                    trust_profile=trust_profile,
                    asr_provider=str(asr["provider"]) if asr else "",
                    asr_model=str(asr.get("model", "unknown")) if asr else "",
                    asr_rank=1,
                    provider_confidence=(
                        float(asr["confidence"])
                        if asr and asr.get("confidence") is not None
                        else None
                    ),
                    enable_learned_asr=enable_learned_asr,
                )
                action = (
                    "apply"
                    if score >= APPLY_THRESHOLD and not blockers
                    else "abstain"
                    if "NEGATIVE_CONTEXT_EVIDENCE" in blockers
                    else "suggest"
                    if score >= SUGGEST_THRESHOLD
                    else "abstain"
                )
                candidate = TraceCandidate(
                    memory_id=memory.id,
                    canonical_form=memory.canonical_form,
                    input_span=matched,
                    output_span=memory.canonical_form,
                    start=start,
                    end=end,
                    score=round(score, 4),
                    action=action,
                    reason_codes=reasons,
                    blockers=blockers,
                    features=features,
                )
                key = (memory.id, start, end)
                previous = candidates_by_key.get(key)
                if previous is None or candidate.score > previous.score:
                    candidates_by_key[key] = candidate

        for alternative_index, alternative in enumerate(alternatives or [], 1):
            confidence = float(alternative["confidence"])
            provider = str(alternative.get("provider", "unknown"))
            model_name = str(alternative.get("model", "unknown"))
            rank = int(alternative.get("rank") or alternative_index)
            alternative_text = str(alternative["text"])
            for variant in memory.variants:
                for start, end, matched in generate_asr_alternative_spans(
                    formatted_text,
                    alternative_text,
                    variant,
                ):
                    if normalize(matched) == memory.canonical_normalized:
                        continue
                    score, reasons, blockers, features = _score_candidate(
                        memory=memory,
                        variant=variant,
                        input_text=formatted_text,
                        input_span=matched,
                        match_method="asr_alternative",
                        start=start,
                        end=end,
                        semantic_encoder=semantic_encoder,
                        semantic_vector_cache=semantic_vector_cache,
                        trust_profile=trust_profile,
                        asr_confidence=confidence,
                        asr_provider=provider,
                        asr_model=model_name,
                        asr_rank=rank,
                        provider_confidence=confidence,
                        enable_learned_asr=enable_learned_asr,
                    )
                    action = (
                        "apply"
                        if score >= APPLY_THRESHOLD and not blockers
                        else "abstain"
                        if "NEGATIVE_CONTEXT_EVIDENCE" in blockers
                        else "suggest"
                        if score >= SUGGEST_THRESHOLD
                        else "abstain"
                    )
                    candidate = TraceCandidate(
                        memory_id=memory.id,
                        canonical_form=memory.canonical_form,
                        input_span=matched,
                        output_span=memory.canonical_form,
                        start=start,
                        end=end,
                        score=round(score, 4),
                        action=action,
                        reason_codes=reasons,
                        blockers=blockers,
                        features=features,
                    )
                    key = (memory.id, start, end)
                    previous = candidates_by_key.get(key)
                    if previous is None or candidate.score > previous.score:
                        candidates_by_key[key] = candidate

    candidates = list(candidates_by_key.values())
    candidates.sort(key=lambda item: (-item.score, item.start, -(item.end - item.start)))
    winners: list[TraceCandidate] = []
    occupied: list[tuple[int, int]] = []
    for candidate in candidates:
        if candidate.action != "apply":
            continue
        overlapping = [
            other
            for other in candidates
            if other is not candidate
            and other.start < candidate.end
            and candidate.start < other.end
        ]
        runner_up = max((other.score for other in overlapping), default=0.0)
        if overlapping and candidate.score - runner_up < MINIMUM_WINNER_MARGIN:
            candidate.action = "suggest"
            candidate.reason_codes.append("INSUFFICIENT_WINNER_MARGIN")
            candidate.blockers.append("INSUFFICIENT_WINNER_MARGIN")
            continue
        if any(left < candidate.end and candidate.start < right for left, right in occupied):
            candidate.action = "abstain"
            candidate.reason_codes.append("OVERLAPPING_WINNER")
            candidate.blockers.append("OVERLAPPING_WINNER")
            continue
        winners.append(candidate)
        occupied.append((candidate.start, candidate.end))

    output = formatted_text
    for winner in sorted(winners, key=lambda item: item.start, reverse=True):
        output = output[: winner.start] + winner.output_span + output[winner.end :]

    if winners:
        action = "apply"
    elif any(candidate.action == "suggest" for candidate in candidates):
        action = "suggest"
    else:
        action = "abstain"
    latency_ms = (time.perf_counter() - started) * 1000
    trace = {
        "policy_version": POLICY.version,
        "learned_asr_enabled": enable_learned_asr,
        "thresholds": {
            "apply": APPLY_THRESHOLD,
            "suggest": SUGGEST_THRESHOLD,
            "minimum_winner_margin": MINIMUM_WINNER_MARGIN,
            "minimum_positive_context_similarity": MIN_POSITIVE_CONTEXT_SIMILARITY,
            "negative_context_block_threshold": NEGATIVE_CONTEXT_BLOCK_THRESHOLD,
            "asr_minimum_outcomes": ASR_MINIMUM_OUTCOMES,
        },
        "candidates": [asdict(candidate) for candidate in candidates],
        "changes": [asdict(candidate) for candidate in winners],
        "semantic": (
            semantic_encoder.status()
            if semantic_encoder is not None
            else {"enabled": False, "state": "not_configured"}
        ),
    }
    decision = Decision(
        user_id=user_id,
        raw_asr_text=raw_asr_text,
        formatted_text=formatted_text,
        memory_aware_text=output,
        action=action,
        trace_json=json.dumps(trace),
        total_latency_ms=latency_ms,
        engine_version=ENGINE_VERSION,
    )
    session.add(decision)
    session.commit()
    response = {
        "trace_id": decision.id,
        "raw_asr_text": raw_asr_text,
        "formatted_text": formatted_text,
        "memory_aware_text": output,
        "action": action,
        "changes": trace["changes"],
        "candidates": trace["candidates"],
        "total_latency_ms": round(latency_ms, 3),
        "engine_version": ENGINE_VERSION,
        "policy_version": POLICY.version,
        "semantic": trace["semantic"],
    }
    return decision, response


def apply_decision_feedback(
    session: Session,
    *,
    trace_id: str,
    verdict: str,
    corrected_text: str | None,
    suppress_memories: bool,
    candidate_memory_id: str | None = None,
    candidate_start: int | None = None,
    semantic_encoder: SemanticEncoder | None = None,
    enable_auto_lifecycle: bool = True,
) -> dict | None:
    decision = session.get(Decision, trace_id)
    if decision is None:
        return None
    trace = json.loads(decision.trace_json)
    if candidate_memory_id:
        selected = [
            candidate
            for candidate in trace["candidates"]
            if candidate["memory_id"] == candidate_memory_id
            and (candidate_start is None or candidate["start"] == candidate_start)
        ]
        selected = sorted(selected, key=lambda candidate: candidate["score"], reverse=True)[:1]
    else:
        selected = trace["changes"]
    if not selected:
        raise ValueError("Feedback must identify an applied change or a visible candidate")
    memory_ids = list(dict.fromkeys(change["memory_id"] for change in selected))
    resulting_states: dict[str, str] = {}
    asr_outcome_ids: list[str] = []
    trust_profiles: dict[str, dict] = {}
    for memory_id in memory_ids:
        memory = session.get(Memory, memory_id)
        if memory is None:
            continue
        change = next(change for change in selected if change["memory_id"] == memory_id)
        features = change["features"]
        feedback_event_id = f"decision:{decision.id}:memory:{memory_id}:span:{change['start']}"
        existing_observation = session.scalar(
            select(Observation).where(
                Observation.user_id == decision.user_id,
                Observation.memory_id == memory_id,
                Observation.source_event_id == feedback_event_id,
            )
        )
        if existing_observation is not None:
            if existing_observation.accepted != (verdict == "correct"):
                raise ValueError("Conflicting feedback already exists for this candidate")
            existing_outcome = session.scalar(
                select(AsrOutcome).where(
                    AsrOutcome.observation_id == existing_observation.id,
                )
            )
            if existing_outcome is not None:
                asr_outcome_ids.append(existing_outcome.id)
            resulting_states[memory.id] = memory.state
            trust_profiles[memory.id] = memory_trust_profile(memory)
            continue
        reliability = 1.0 if verdict == "correct" else -1.0
        observation = Observation(
            user_id=decision.user_id,
            memory=memory,
            evidence_type="intervention_feedback",
            raw_asr_text=decision.raw_asr_text,
            formatted_text=decision.formatted_text,
            accepted_text=corrected_text or decision.formatted_text,
            source_span=change["input_span"],
            target_span=change["output_span"],
            reliability=reliability,
            accepted=verdict == "correct",
            reason_code="USER_CONFIRMED" if verdict == "correct" else "USER_REJECTED",
            source_event_id=feedback_event_id,
            context_fingerprint=context_fingerprint(
                decision.formatted_text,
                change["input_span"],
                start=change["start"],
                end=change["end"],
            ),
        )
        session.add(observation)
        session.flush()
        if features.get("asr_provider"):
            outcome = AsrOutcome(
                user_id=decision.user_id,
                memory=memory,
                decision_id=decision.id,
                observation_id=observation.id,
                provider=str(features["asr_provider"]),
                model_name=str(features.get("asr_model", "unknown")),
                rank=int(features.get("asr_rank", 1)),
                source_form=change["input_span"],
                source_normalized=normalize(change["input_span"]),
                target_form=change["output_span"],
                target_normalized=normalize(change["output_span"]),
                provider_confidence=(
                    float(features["asr_provider_confidence"])
                    if isinstance(features.get("asr_provider_confidence"), (float, int))
                    else None
                ),
                accepted=verdict == "correct",
                reason_code=(
                    "USER_CONFIRMED_ASR_CONFUSION"
                    if verdict == "correct"
                    else "USER_REJECTED_ASR_CONFUSION"
                ),
            )
            session.add(outcome)
            session.flush()
            asr_outcome_ids.append(outcome.id)
        store_context_evidence(
            session,
            memory=memory,
            observation=observation,
            polarity="positive" if verdict == "correct" else "negative",
            context_text=decision.formatted_text,
            features=extract_context_features(
                decision.formatted_text,
                change["input_span"],
                source_type=(
                    "confirmed_intervention" if verdict == "correct" else "rejected_intervention"
                ),
                start=change["start"],
                end=change["end"],
            ),
            reliability=reliability,
        )
        store_semantic_evidence(
            session,
            memory=memory,
            observation=observation,
            polarity="positive" if verdict == "correct" else "negative",
            context_text=decision.formatted_text,
            source_span=change["input_span"],
            source_type=(
                "confirmed_intervention" if verdict == "correct" else "rejected_intervention"
            ),
            reliability=reliability,
            semantic_encoder=semantic_encoder,
            start=change["start"],
            end=change["end"],
        )
        if suppress_memories and verdict == "incorrect":
            previous_state = memory.state
            memory.state = "suppressed"
            transition = {
                "previous_state": previous_state,
                "new_state": memory.state,
                "changed": previous_state != memory.state,
                "reason_code": "EXPLICIT_USER_SUPPRESSION",
            }
        elif enable_auto_lifecycle:
            transition = reconcile_memory_state(memory)
        else:
            transition = {
                "previous_state": memory.state,
                "new_state": memory.state,
                "changed": False,
                "reason_code": "AUTO_LIFECYCLE_DISABLED",
            }
        event_name = "intervention_confirmed" if verdict == "correct" else "intervention_rejected"
        if transition["changed"]:
            event_name += f"_{transition['new_state']}"
        record_memory_version(
            session,
            memory,
            action=event_name,
            reason=(
                f"User {verdict} feedback; lifecycle "
                f"{transition['previous_state']} -> {transition['new_state']} "
                f"({transition['reason_code']})"
            ),
            actor="user",
        )
        resulting_states[memory.id] = memory.state
        trust_profiles[memory.id] = memory_trust_profile(memory)
    session.commit()
    return {
        "trace_id": trace_id,
        "verdict": verdict,
        "affected_memory_ids": memory_ids,
        "resulting_states": resulting_states,
        "asr_outcome_ids": asr_outcome_ids,
        "trust_profiles": trust_profiles,
    }
