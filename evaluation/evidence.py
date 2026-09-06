from __future__ import annotations

from typing import Any

from lexitrace.models import (
    AsrOutcome,
    ContextEmbedding,
    ContextEvidence,
    Decision,
    Memory,
    MemoryVariant,
    MemoryVersion,
    Observation,
)
from sqlalchemy import func, select, text

TABLE_MODELS = {
    "memories": Memory,
    "memory_variants": MemoryVariant,
    "observations": Observation,
    "context_evidence": ContextEvidence,
    "context_embeddings": ContextEmbedding,
    "decisions": Decision,
    "memory_versions": MemoryVersion,
    "asr_outcomes": AsrOutcome,
}


def database_snapshot(session) -> dict[str, Any]:
    """Return allocated SQLite size and logical row counts without reading private vectors."""
    rows = {
        name: session.scalar(select(func.count()).select_from(model)) or 0
        for name, model in TABLE_MODELS.items()
    }
    page_count = int(session.execute(text("PRAGMA page_count")).scalar_one())
    page_size = int(session.execute(text("PRAGMA page_size")).scalar_one())
    vector_payload_bytes = int(
        session.scalar(
            select(func.coalesce(func.sum(func.length(ContextEmbedding.vector_json)), 0))
        )
        or 0
    )
    trace_payload_bytes = int(
        session.scalar(select(func.coalesce(func.sum(func.length(Decision.trace_json)), 0))) or 0
    )
    return {
        "allocated_bytes": page_count * page_size,
        "page_count": page_count,
        "page_size": page_size,
        "vector_payload_bytes": vector_payload_bytes,
        "trace_payload_bytes": trace_payload_bytes,
        "rows": rows,
    }


def memory_state_snapshot(session) -> list[dict[str, Any]]:
    """Capture the state and provenance needed to audit an evaluation decision."""
    memories = session.scalars(select(Memory).order_by(Memory.canonical_form, Memory.id)).all()
    return [
        {
            "memory_id": memory.id,
            "canonical_form": memory.canonical_form,
            "state": memory.state,
            "scope_mode": memory.scope_mode,
            "evidence_confidence": round(memory.evidence_confidence, 4),
            "support_count": memory.support_count,
            "contradiction_count": memory.contradiction_count,
            "variants": sorted(variant.surface_form for variant in memory.variants),
            "observations": [
                {
                    "observation_id": observation.id,
                    "evidence_type": observation.evidence_type,
                    "source_span": observation.source_span,
                    "target_span": observation.target_span,
                    "reliability": observation.reliability,
                    "accepted": observation.accepted,
                    "reason_code": observation.reason_code,
                }
                for observation in sorted(
                    memory.observations,
                    key=lambda item: (item.created_at.isoformat(), item.id),
                )
            ],
            "context_evidence": {
                "positive": sum(item.polarity == "positive" for item in memory.context_evidence),
                "negative": sum(item.polarity == "negative" for item in memory.context_evidence),
                "sources": sorted({item.source_type for item in memory.context_evidence}),
            },
            "semantic_evidence": {
                "positive": sum(item.polarity == "positive" for item in memory.semantic_evidence),
                "negative": sum(item.polarity == "negative" for item in memory.semantic_evidence),
                "models": sorted({item.model_name for item in memory.semantic_evidence}),
            },
            "asr_evidence": {
                "outcomes": len(memory.asr_outcomes),
                "accepted": sum(item.accepted for item in memory.asr_outcomes),
                "providers": sorted({item.provider for item in memory.asr_outcomes}),
                "models": sorted({item.model_name for item in memory.asr_outcomes}),
            },
        }
        for memory in memories
    ]


class CountingSemanticEncoder:
    """Decorate an encoder so benchmark model use is measured rather than estimated."""

    def __init__(self, encoder) -> None:
        self.encoder = encoder
        self.calls = 0
        self.input_characters = 0
        self.failures = 0

    @property
    def enabled(self) -> bool:
        return self.encoder.enabled

    @property
    def model_name(self) -> str:
        return self.encoder.model_name

    def encode(self, value: str) -> list[float] | None:
        self.calls += 1
        self.input_characters += len(value)
        result = self.encoder.encode(value)
        if result is None:
            self.failures += 1
        return result

    def status(self) -> dict[str, Any]:
        return self.encoder.status()

    def usage(self) -> dict[str, Any]:
        return {
            "execution": "local" if self.enabled else "disabled",
            "model": self.model_name,
            "embedding_calls": self.calls,
            "input_characters": self.input_characters,
            "failed_calls": self.failures,
            "hosted_requests": 0,
            "estimated_api_cost_usd": 0.0,
        }
