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
    evidence_confidence: Mapped[float] = mapped_column(Float, default=0.7)
    support_count: Mapped[int] = mapped_column(Integer, default=1)
    contradiction_count: Mapped[int] = mapped_column(Integer, default=0)
    positive_context_json: Mapped[str] = mapped_column(Text, default="[]")
    negative_context_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)

    variants: Mapped[list[MemoryVariant]] = relationship(
        back_populates="memory", cascade="all, delete-orphan", lazy="selectin"
    )
    observations: Mapped[list[Observation]] = relationship(
        back_populates="memory", cascade="all, delete-orphan"
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
    __table_args__ = (Index("ix_observations_user_created", "user_id", "created_at"),)

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
    created_at: Mapped[datetime] = mapped_column(default=utc_now)

    memory: Mapped[Memory | None] = relationship(back_populates="observations")
    context_evidence: Mapped[list[ContextEvidence]] = relationship(
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
    engine_version: Mapped[str] = mapped_column(String(30), default="0.3.0")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


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
