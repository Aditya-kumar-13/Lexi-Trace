from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC)


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (
        UniqueConstraint("user_id", "canonical_normalized", name="uq_memory_user_canonical"),
        Index("ix_memories_user_state", "user_id", "state"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(100), index=True)
    canonical_form: Mapped[str] = mapped_column(String(250))
    canonical_normalized: Mapped[str] = mapped_column(String(250))
    state: Mapped[str] = mapped_column(String(30), default="candidate", index=True)
    scope_mode: Mapped[str] = mapped_column(String(20), default="global")
    # Kept only for migration compatibility with pre-0.8 databases. Decision code never reads
    # or mutates these legacy counters; trust is derived from immutable observations.
    legacy_evidence_confidence: Mapped[float] = mapped_column(
        "evidence_confidence", Float, default=0.0
    )
    legacy_support_count: Mapped[int] = mapped_column("support_count", Integer, default=0)
    legacy_contradiction_count: Mapped[int] = mapped_column(
        "contradiction_count", Integer, default=0
    )
    positive_context_json: Mapped[str] = mapped_column(Text, default="[]")
    negative_context_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    variants: Mapped[list[MemoryVariant]] = relationship(
        back_populates="memory", cascade="all, delete-orphan", lazy="selectin"
    )
    observations: Mapped[list[Observation]] = relationship(
        back_populates="memory", cascade="all, delete-orphan", lazy="selectin"
    )
    versions: Mapped[list[MemoryVersion]] = relationship(
        back_populates="memory",
        cascade="all, delete-orphan",
        order_by="MemoryVersion.version_number",
    )
    context_evidence: Mapped[list[ContextEvidence]] = relationship(
        back_populates="memory",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    semantic_evidence: Mapped[list[ContextEmbedding]] = relationship(
        back_populates="memory",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    asr_outcomes: Mapped[list[AsrOutcome]] = relationship(
        back_populates="memory",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class MemoryVariant(Base):
    __tablename__ = "memory_variants"
    __table_args__ = (
        UniqueConstraint("memory_id", "normalized_form", name="uq_variant_memory_normalized"),
        Index("ix_variants_normalized", "normalized_form"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    memory_id: Mapped[str] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), index=True
    )
    surface_form: Mapped[str] = mapped_column(String(250))
    normalized_form: Mapped[str] = mapped_column(String(250))
    metaphone_key: Mapped[str] = mapped_column(String(250), default="")
    support_count: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    memory: Mapped[Memory] = relationship(back_populates="variants")


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        Index("ix_observations_user_created", "user_id", "created_at"),
        Index(
            "uq_observation_user_event_memory",
            "user_id",
            "source_event_id",
            "memory_id",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(100), index=True)
    memory_id: Mapped[str | None] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), nullable=True, index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(40))
    raw_asr_text: Mapped[str] = mapped_column(Text, default="")
    formatted_text: Mapped[str] = mapped_column(Text, default="")
    accepted_text: Mapped[str] = mapped_column(Text, default="")
    source_span: Mapped[str] = mapped_column(String(250), default="")
    target_span: Mapped[str] = mapped_column(String(250), default="")
    reliability: Mapped[float] = mapped_column(Float)
    accepted: Mapped[bool] = mapped_column(Boolean, default=True)
    reason_code: Mapped[str] = mapped_column(String(80), default="ACCEPTED")
    source_event_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    context_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    memory: Mapped[Memory | None] = relationship(back_populates="observations")
    context_evidence: Mapped[list[ContextEvidence]] = relationship(
        back_populates="observation",
        cascade="all, delete-orphan",
    )
    semantic_evidence: Mapped[list[ContextEmbedding]] = relationship(
        back_populates="observation",
        cascade="all, delete-orphan",
    )


class ContextEvidence(Base):
    __tablename__ = "context_evidence"
    __table_args__ = (
        UniqueConstraint(
            "observation_id",
            "polarity",
            "feature",
            name="uq_context_evidence_observation_feature",
        ),
        Index("ix_context_evidence_memory_polarity", "memory_id", "polarity"),
        Index("ix_context_evidence_feature", "feature"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    memory_id: Mapped[str] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), index=True
    )
    observation_id: Mapped[str] = mapped_column(
        ForeignKey("observations.id", ondelete="CASCADE"), index=True
    )
    polarity: Mapped[str] = mapped_column(String(10))
    feature: Mapped[str] = mapped_column(String(250))
    feature_kind: Mapped[str] = mapped_column(String(20), default="token")
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    source_type: Mapped[str] = mapped_column(String(40))
    context_text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    memory: Mapped[Memory] = relationship(back_populates="context_evidence")
    observation: Mapped[Observation] = relationship(back_populates="context_evidence")


class ContextEmbedding(Base):
    __tablename__ = "context_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "observation_id",
            "polarity",
            "model_name",
            name="uq_context_embedding_observation_model",
        ),
        Index("ix_context_embeddings_memory_polarity", "memory_id", "polarity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    memory_id: Mapped[str] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), index=True
    )
    observation_id: Mapped[str] = mapped_column(
        ForeignKey("observations.id", ondelete="CASCADE"), index=True
    )
    polarity: Mapped[str] = mapped_column(String(10))
    model_name: Mapped[str] = mapped_column(String(250))
    dimension: Mapped[int] = mapped_column(Integer)
    vector_json: Mapped[str] = mapped_column(Text)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    source_type: Mapped[str] = mapped_column(String(40))
    context_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    memory: Mapped[Memory] = relationship(back_populates="semantic_evidence")
    observation: Mapped[Observation] = relationship(back_populates="semantic_evidence")


class Decision(Base):
    __tablename__ = "decisions"
    __table_args__ = (Index("ix_decisions_user_created", "user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(100), index=True)
    raw_asr_text: Mapped[str] = mapped_column(Text, default="")
    formatted_text: Mapped[str] = mapped_column(Text)
    memory_aware_text: Mapped[str] = mapped_column(Text)
    action: Mapped[str] = mapped_column(String(20))
    trace_json: Mapped[str] = mapped_column(Text)
    total_latency_ms: Mapped[float] = mapped_column(Float)
    engine_version: Mapped[str] = mapped_column(String(30), default="0.9.0")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class AsrOutcome(Base):
    """Immutable user outcome for one provider/model confusion candidate."""

    __tablename__ = "asr_outcomes"
    __table_args__ = (
        UniqueConstraint(
            "decision_id",
            "memory_id",
            "source_normalized",
            name="uq_asr_outcome_decision_memory_source",
        ),
        Index(
            "ix_asr_outcomes_reliability_key",
            "user_id",
            "memory_id",
            "provider",
            "model_name",
            "rank",
            "source_normalized",
            "target_normalized",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(String(100), index=True)
    memory_id: Mapped[str] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), index=True
    )
    decision_id: Mapped[str] = mapped_column(
        ForeignKey("decisions.id", ondelete="CASCADE"), index=True
    )
    observation_id: Mapped[str] = mapped_column(
        ForeignKey("observations.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(100))
    model_name: Mapped[str] = mapped_column(String(150))
    rank: Mapped[int] = mapped_column(Integer, default=1)
    source_form: Mapped[str] = mapped_column(String(250))
    source_normalized: Mapped[str] = mapped_column(String(250))
    target_form: Mapped[str] = mapped_column(String(250))
    target_normalized: Mapped[str] = mapped_column(String(250))
    provider_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    accepted: Mapped[bool] = mapped_column(Boolean)
    reason_code: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    memory: Mapped[Memory] = relationship(back_populates="asr_outcomes")


class MemoryVersion(Base):
    __tablename__ = "memory_versions"
    __table_args__ = (
        UniqueConstraint("memory_id", "version_number", name="uq_memory_version_number"),
        Index("ix_memory_versions_memory_created", "memory_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    memory_id: Mapped[str] = mapped_column(
        ForeignKey("memories.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(40))
    reason: Mapped[str] = mapped_column(String(250))
    actor: Mapped[str] = mapped_column(String(40), default="system")
    snapshot_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    memory: Mapped[Memory] = relationship(back_populates="versions")
