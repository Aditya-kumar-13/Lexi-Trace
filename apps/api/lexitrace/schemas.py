from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ExplicitTeachRequest(BaseModel):
    user_id: str = Field(default="demo-user", min_length=1, max_length=100)
    canonical_form: str = Field(min_length=1, max_length=250)
    variants: list[str] = Field(min_length=1, max_length=20)
    scope_mode: Literal["global", "contextual"] = "global"
    positive_context: list[str] = Field(default_factory=list, max_length=30)
    negative_context: list[str] = Field(default_factory=list, max_length=30)
    raw_asr_text: str = Field(default="", max_length=20_000)
    formatted_text: str = Field(default="", max_length=20_000)
    accepted_text: str = Field(default="", max_length=20_000)
    event_id: str | None = Field(default=None, min_length=1, max_length=150)

    @field_validator("canonical_form")
    @classmethod
    def canonical_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("canonical_form must contain visible characters")
        return value

    @field_validator("variants")
    @classmethod
    def variants_not_blank(cls, values: list[str]) -> list[str]:
        cleaned = [value.strip() for value in values if value.strip()]
        if not cleaned:
            raise ValueError("at least one non-empty variant is required")
        return list(dict.fromkeys(cleaned))


class CorrectionObservationRequest(BaseModel):
    user_id: str = Field(default="demo-user", min_length=1, max_length=100)
    raw_asr_text: str = Field(default="", max_length=20_000)
    formatted_text: str = Field(min_length=1, max_length=20_000)
    accepted_text: str = Field(min_length=1, max_length=20_000)
    confirm_candidates: bool = False
    event_id: str | None = Field(default=None, min_length=1, max_length=150)


class AsrAlternative(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    confidence: float = Field(ge=0.0, le=1.0)
    provider: str = Field(default="unknown", min_length=1, max_length=100)
    model: str = Field(default="unknown", min_length=1, max_length=150)
    rank: int | None = Field(default=None, ge=1, le=10)


class AsrMetadata(BaseModel):
    provider: str = Field(min_length=1, max_length=100)
    model: str = Field(default="unknown", min_length=1, max_length=150)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class InferenceRequest(BaseModel):
    user_id: str = Field(default="demo-user", min_length=1, max_length=100)
    raw_asr_text: str = Field(default="", max_length=20_000)
    formatted_text: str = Field(min_length=1, max_length=20_000)
    alternatives: list[AsrAlternative] = Field(default_factory=list, max_length=10)
    asr: AsrMetadata | None = None


class MemoryUpdateRequest(BaseModel):
    state: Literal["candidate", "confirmed", "suppressed"] | None = None
    canonical_form: str | None = Field(default=None, min_length=1, max_length=250)
    scope_mode: Literal["global", "contextual"] | None = None
    positive_context: list[str] | None = Field(default=None, max_length=30)
    negative_context: list[str] | None = Field(default=None, max_length=30)
    reason: str = Field(default="User updated memory", min_length=1, max_length=250)


class VariantResponse(BaseModel):
    id: str
    surface_form: str
    normalized_form: str
    metaphone_key: str


class MemoryResponse(BaseModel):
    id: str
    user_id: str
    canonical_form: str
    state: str
    scope_mode: str
    trust_profile: dict
    positive_context: list[str]
    negative_context: list[str]
    context_evidence_count: int
    context_profile: dict
    semantic_evidence_count: int
    semantic_profile: dict
    asr_evidence_count: int
    asr_profile: dict
    variants: list[VariantResponse]
    created_at: datetime
    updated_at: datetime


class MemoryVersionResponse(BaseModel):
    id: str
    memory_id: str
    version_number: int
    action: str
    reason: str
    actor: str
    snapshot: dict
    created_at: datetime


class DecisionFeedbackRequest(BaseModel):
    verdict: Literal["correct", "incorrect"]
    corrected_text: str | None = Field(default=None, max_length=20_000)
    suppress_memories: bool = False
    candidate_memory_id: str | None = Field(default=None, max_length=36)
    candidate_start: int | None = Field(default=None, ge=0)


class DecisionFeedbackResponse(BaseModel):
    trace_id: str
    verdict: str
    affected_memory_ids: list[str]
    resulting_states: dict[str, str]
    asr_outcome_ids: list[str]
    trust_profiles: dict[str, dict]


class CandidateTrace(BaseModel):
    memory_id: str
    canonical_form: str
    input_span: str
    output_span: str
    start: int
    end: int
    score: float
    action: Literal["apply", "suggest", "abstain"]
    reason_codes: list[str]
    blockers: list[str]
    features: dict[str, float | str | bool]


class InferenceResponse(BaseModel):
    trace_id: str
    raw_asr_text: str
    formatted_text: str
    memory_aware_text: str
    action: Literal["apply", "suggest", "abstain"]
    changes: list[CandidateTrace]
    candidates: list[CandidateTrace]
    total_latency_ms: float
    engine_version: str
    policy_version: str
    semantic: dict


class CorrectionObservationResponse(BaseModel):
    observation_ids: list[str]
    created_memory_ids: list[str]
    rejected: list[dict[str, str]]
    trust_profiles: dict[str, dict]


class ResetResponse(BaseModel):
    deleted_memories: int
    deleted_observations: int
    deleted_decisions: int
