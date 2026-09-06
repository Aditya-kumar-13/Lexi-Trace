from __future__ import annotations

import json
import re
import time
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher

import jellyfish
from rapidfuzz.fuzz import ratio
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .models import (
    ContextEvidence,
    Decision,
    Memory,
    MemoryVariant,
    MemoryVersion,
    Observation,
)

ENGINE_VERSION = "0.3.0"
APPLY_THRESHOLD = 0.93
SUGGEST_THRESHOLD = 0.72
MINIMUM_WINNER_MARGIN = 0.12
FUZZY_CANDIDATE_THRESHOLD = 0.76
MIN_POSITIVE_CONTEXT_SIMILARITY = 0.12
NEGATIVE_CONTEXT_BLOCK_THRESHOLD = 0.12
CONTEXT_WINDOW_TOKENS = 6
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
    return list(best_by_span.values())


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


def memory_snapshot(memory: Memory) -> dict:
    return {
        "canonical_form": memory.canonical_form,
        "state": memory.state,
        "scope_mode": memory.scope_mode,
        "evidence_confidence": round(memory.evidence_confidence, 4),
        "support_count": memory.support_count,
        "contradiction_count": memory.contradiction_count,
        "positive_context": json.loads(memory.positive_context_json),
        "negative_context": json.loads(memory.negative_context_json),
        "context_profile": aggregate_context_profile(memory),
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
        "evidence_confidence": memory.evidence_confidence,
        "support_count": memory.support_count,
        "contradiction_count": memory.contradiction_count,
        "positive_context": json.loads(memory.positive_context_json),
        "negative_context": json.loads(memory.negative_context_json),
        "context_evidence_count": len(memory.context_evidence),
        "context_profile": aggregate_context_profile(memory),
        "variants": [
            {
                "id": variant.id,
                "surface_form": variant.surface_form,
                "normalized_form": variant.normalized_form,
                "metaphone_key": variant.metaphone_key,
                "support_count": variant.support_count,
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
) -> Memory:
    normalized_canonical = normalize(canonical_form)
    memory = session.scalar(
        select(Memory).where(
            Memory.user_id == user_id,
            Memory.canonical_normalized == normalized_canonical,
        )
    )
    if memory is None:
        memory = Memory(
            user_id=user_id,
            canonical_form=canonical_form,
            canonical_normalized=normalized_canonical,
            state="confirmed",
            scope_mode=scope_mode,
            evidence_confidence=1.0,
            positive_context_json=json.dumps(positive_context),
            negative_context_json=json.dumps(negative_context),
        )
        session.add(memory)
        session.flush()
    else:
        memory.canonical_form = canonical_form
        memory.state = "confirmed"
        memory.scope_mode = scope_mode
        memory.evidence_confidence = 1.0
        memory.support_count += 1
        memory.positive_context_json = json.dumps(positive_context)
        memory.negative_context_json = json.dumps(negative_context)

    existing = {item.normalized_form: item for item in memory.variants}
    for variant_text in variants:
        normalized_variant = normalize(variant_text)
        if normalized_variant in existing:
            existing[normalized_variant].support_count += 1
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
) -> tuple[list[str], list[str], list[dict[str, str]]]:
    matcher = SequenceMatcher(None, formatted_text.split(), accepted_text.split(), autojunk=False)
    observation_ids: list[str] = []
    memory_ids: list[str] = []
    rejected: list[dict[str, str]] = []

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
        if memory is None:
            memory = Memory(
                user_id=user_id,
                canonical_form=target_span,
                canonical_normalized=normalized_target,
                state="confirmed" if confirm_candidates else "candidate",
                scope_mode="contextual",
                evidence_confidence=1.0 if confirm_candidates else 0.7,
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
            memory.support_count += 1
            memory.evidence_confidence = min(0.95, memory.evidence_confidence + 0.1)
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
                existing_variant.support_count += 1

        observation = Observation(
            user_id=user_id,
            memory=memory,
            evidence_type="accepted_correction",
            raw_asr_text=raw_asr_text,
            formatted_text=formatted_text,
            accepted_text=accepted_text,
            source_span=source_span,
            target_span=target_span,
            reliability=0.7,
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
        record_memory_version(
            session,
            memory,
            action="correction_observed",
            reason="Accepted transcript contained a supported word-level correction",
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
) -> tuple[float, list[str], list[str], dict[str, float | str | bool]]:
    current = extract_context_features(
        input_text,
        input_span,
        source_type="inference",
        start=start,
        end=end,
    )
    positive_similarity, positive_matches = context_similarity(memory, current, "positive")
    negative_similarity, negative_matches = context_similarity(memory, current, "negative")
    has_positive_profile = any(
        evidence.polarity == "positive" for evidence in memory.context_evidence
    )
    string_similarity = ratio(normalize(input_span), variant.normalized_form) / 100
    phonetic_match = metaphone(input_span) == variant.metaphone_key
    reasons: list[str] = [f"{match_method.upper()}_CANDIDATE"]
    blockers: list[str] = []

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

    context_signal = (
        1.0 if memory.scope_mode == "global" else min(1.0, (positive_similarity**0.35) * 1.2)
    )
    score = (
        0.72 * string_similarity
        + 0.14 * memory.evidence_confidence
        + 0.10 * context_signal
        + (0.10 if phonetic_match else 0.0)
        - 0.65 * negative_similarity
    )
    score = max(0.0, min(1.0, score))
    reasons.extend(blockers)
    features: dict[str, float | str | bool] = {
        "string_similarity": round(string_similarity, 4),
        "phonetic_match": phonetic_match,
        "evidence_confidence": round(memory.evidence_confidence, 4),
        "positive_context_similarity": round(positive_similarity, 4),
        "negative_context_similarity": round(negative_similarity, 4),
        "positive_evidence_matches": ", ".join(positive_matches),
        "negative_evidence_matches": ", ".join(negative_matches),
        "context_evidence_count": len(memory.context_evidence),
        "memory_state": memory.state,
        "scope_mode": memory.scope_mode,
        "match_method": match_method,
    }
    return score, reasons, blockers, features


def infer(
    session: Session, *, user_id: str, raw_asr_text: str, formatted_text: str
) -> tuple[Decision, dict]:
    started = time.perf_counter()
    memories = session.scalars(
        select(Memory).where(Memory.user_id == user_id, Memory.state != "suppressed")
    ).all()
    candidates_by_key: dict[tuple[str, int, int], TraceCandidate] = {}

    for memory in memories:
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
        "thresholds": {
            "apply": APPLY_THRESHOLD,
            "suggest": SUGGEST_THRESHOLD,
            "minimum_winner_margin": MINIMUM_WINNER_MARGIN,
            "minimum_positive_context_similarity": MIN_POSITIVE_CONTEXT_SIMILARITY,
            "negative_context_block_threshold": NEGATIVE_CONTEXT_BLOCK_THRESHOLD,
        },
        "candidates": [asdict(candidate) for candidate in candidates],
        "changes": [asdict(candidate) for candidate in winners],
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
    }
    return decision, response


def apply_decision_feedback(
    session: Session,
    *,
    trace_id: str,
    verdict: str,
    corrected_text: str | None,
    suppress_memories: bool,
) -> dict | None:
    decision = session.get(Decision, trace_id)
    if decision is None:
        return None
    trace = json.loads(decision.trace_json)
    memory_ids = list(dict.fromkeys(change["memory_id"] for change in trace["changes"]))
    resulting_states: dict[str, str] = {}
    for memory_id in memory_ids:
        memory = session.get(Memory, memory_id)
        if memory is None:
            continue
        change = next(change for change in trace["changes"] if change["memory_id"] == memory_id)
        if verdict == "correct":
            memory.support_count += 1
            memory.evidence_confidence = min(1.0, memory.evidence_confidence + 0.02)
            action = "intervention_confirmed"
            reason = "User confirmed the memory-aware intervention"
            reliability = 1.0
        else:
            memory.contradiction_count += 1
            memory.evidence_confidence = max(0.0, memory.evidence_confidence - 0.25)
            if suppress_memories:
                memory.state = "suppressed"
            elif memory.evidence_confidence <= 0.75:
                memory.state = "candidate"
            action = "intervention_rejected"
            reason = "User rejected the memory-aware intervention"
            reliability = -1.0
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
        )
        session.add(observation)
        session.flush()
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
        record_memory_version(
            session,
            memory,
            action=action,
            reason=reason,
            actor="user",
        )
        resulting_states[memory.id] = memory.state
    session.commit()
    return {
        "trace_id": trace_id,
        "verdict": verdict,
        "affected_memory_ids": memory_ids,
        "resulting_states": resulting_states,
    }
