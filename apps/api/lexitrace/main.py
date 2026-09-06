from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .config import Settings
from .database import build_engine, build_session_factory, get_session
from .engine import (
    apply_decision_feedback,
    apply_memory_state_override,
    infer,
    memory_to_dict,
    normalize,
    observe_correction,
    record_memory_version,
    replace_manual_context_evidence,
    teach_explicit,
)
from .models import (
    AsrOutcome,
    ContextEmbedding,
    ContextEvidence,
    Decision,
    Memory,
    MemoryVersion,
    Observation,
)
from .schemas import (
    CorrectionObservationRequest,
    CorrectionObservationResponse,
    DecisionFeedbackRequest,
    DecisionFeedbackResponse,
    ExplicitTeachRequest,
    InferenceRequest,
    InferenceResponse,
    MemoryResponse,
    MemoryUpdateRequest,
    MemoryVersionResponse,
    ResetResponse,
)
from .semantic import SemanticEncoder, build_semantic_encoder

DatabaseSession = Annotated[Session, Depends(get_session)]
UserIdQuery = Annotated[str, Query(min_length=1)]


def create_app(
    settings: Settings | None = None,
    semantic_encoder_override: SemanticEncoder | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    engine = build_engine(resolved_settings.database_url)
    session_factory = build_session_factory(engine)
    semantic_encoder = semantic_encoder_override or build_semantic_encoder(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        yield
        engine.dispose()

    app = FastAPI(
        title="LexiTrace API",
        version="0.9.0",
        description="Inspectable personal word memory for transcript formatting.",
        lifespan=lifespan,
    )
    app.state.session_factory = session_factory
    app.state.semantic_encoder = semantic_encoder
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/v1/health")
    def health() -> dict:
        return {
            "status": "ok",
            "version": "0.9.0",
            "semantic": semantic_encoder.status(),
        }

    @app.post(
        "/api/v1/observations/explicit",
        response_model=MemoryResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def explicit_teach(payload: ExplicitTeachRequest, session: DatabaseSession) -> dict:
        memory = teach_explicit(
            session,
            **payload.model_dump(),
            semantic_encoder=semantic_encoder,
        )
        return memory_to_dict(memory)

    @app.post(
        "/api/v1/observations/correction",
        response_model=CorrectionObservationResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def correction_observation(
        payload: CorrectionObservationRequest, session: DatabaseSession
    ) -> dict:
        observation_ids, memory_ids, rejected = observe_correction(
            session,
            **payload.model_dump(),
            semantic_encoder=semantic_encoder,
        )
        return {
            "observation_ids": observation_ids,
            "created_memory_ids": memory_ids,
            "rejected": rejected,
            "trust_profiles": {
                memory_id: memory_to_dict(session.get(Memory, memory_id))["trust_profile"]
                for memory_id in memory_ids
                if session.get(Memory, memory_id) is not None
            },
        }

    @app.post("/api/v1/infer", response_model=InferenceResponse)
    def run_inference(payload: InferenceRequest, session: DatabaseSession) -> dict:
        _, response = infer(
            session,
            **payload.model_dump(),
            semantic_encoder=semantic_encoder,
        )
        return response

    @app.get("/api/v1/memories", response_model=list[MemoryResponse])
    def list_memories(
        session: DatabaseSession,
        user_id: UserIdQuery = "demo-user",
    ) -> list[dict]:
        memories = session.scalars(
            select(Memory).where(Memory.user_id == user_id).order_by(Memory.updated_at.desc())
        ).all()
        return [memory_to_dict(memory) for memory in memories]

    @app.get("/api/v1/memories/{memory_id}", response_model=MemoryResponse)
    def get_memory(memory_id: str, session: DatabaseSession) -> dict:
        memory = session.get(Memory, memory_id)
        if memory is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        return memory_to_dict(memory)

    @app.patch("/api/v1/memories/{memory_id}", response_model=MemoryResponse)
    def update_memory(
        memory_id: str,
        payload: MemoryUpdateRequest,
        session: DatabaseSession,
    ) -> dict:
        memory = session.get(Memory, memory_id)
        if memory is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        changes = payload.model_dump(exclude_unset=True)
        reason = changes.pop("reason", "User updated memory")
        if "canonical_form" in changes:
            memory.canonical_form = changes["canonical_form"]
            memory.canonical_normalized = normalize(changes["canonical_form"])
        if "state" in changes:
            apply_memory_state_override(session, memory=memory, state=changes["state"])
        if "scope_mode" in changes:
            memory.scope_mode = changes["scope_mode"]
        if "positive_context" in changes:
            memory.positive_context_json = json.dumps(changes["positive_context"])
        if "negative_context" in changes:
            memory.negative_context_json = json.dumps(changes["negative_context"])
        replace_manual_context_evidence(
            session,
            memory=memory,
            positive_context=changes.get("positive_context"),
            negative_context=changes.get("negative_context"),
        )
        session.flush()
        session.expire(memory, ["context_evidence"])
        record_memory_version(
            session,
            memory,
            action="memory_updated",
            reason=reason,
            actor="user",
        )
        session.commit()
        session.refresh(memory)
        return memory_to_dict(memory)

    @app.get(
        "/api/v1/memories/{memory_id}/history",
        response_model=list[MemoryVersionResponse],
    )
    def memory_history(memory_id: str, session: DatabaseSession) -> list[dict]:
        memory = session.get(Memory, memory_id)
        if memory is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        versions = session.scalars(
            select(MemoryVersion)
            .where(MemoryVersion.memory_id == memory_id)
            .order_by(MemoryVersion.version_number)
        ).all()
        return [
            {
                "id": version.id,
                "memory_id": version.memory_id,
                "version_number": version.version_number,
                "action": version.action,
                "reason": version.reason,
                "actor": version.actor,
                "snapshot": json.loads(version.snapshot_json),
                "created_at": version.created_at,
            }
            for version in versions
        ]

    @app.get("/api/v1/memories/{memory_id}/context-evidence")
    def memory_context_evidence(memory_id: str, session: DatabaseSession) -> list[dict]:
        memory = session.get(Memory, memory_id)
        if memory is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        evidence = session.scalars(
            select(ContextEvidence)
            .where(ContextEvidence.memory_id == memory_id)
            .order_by(ContextEvidence.created_at, ContextEvidence.feature)
        ).all()
        return [
            {
                "id": item.id,
                "observation_id": item.observation_id,
                "polarity": item.polarity,
                "feature": item.feature,
                "feature_kind": item.feature_kind,
                "weight": item.weight,
                "source_type": item.source_type,
                "context_text": item.context_text,
                "created_at": item.created_at,
            }
            for item in evidence
        ]

    @app.get("/api/v1/memories/{memory_id}/semantic-evidence")
    def memory_semantic_evidence(memory_id: str, session: DatabaseSession) -> list[dict]:
        memory = session.get(Memory, memory_id)
        if memory is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        evidence = session.scalars(
            select(ContextEmbedding)
            .where(ContextEmbedding.memory_id == memory_id)
            .order_by(ContextEmbedding.created_at)
        ).all()
        return [
            {
                "id": item.id,
                "observation_id": item.observation_id,
                "polarity": item.polarity,
                "model_name": item.model_name,
                "dimension": item.dimension,
                "weight": item.weight,
                "source_type": item.source_type,
                "context_text": item.context_text,
                "created_at": item.created_at,
            }
            for item in evidence
        ]

    @app.get("/api/v1/memories/{memory_id}/asr-evidence")
    def memory_asr_evidence(memory_id: str, session: DatabaseSession) -> list[dict]:
        memory = session.get(Memory, memory_id)
        if memory is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        outcomes = session.scalars(
            select(AsrOutcome)
            .where(AsrOutcome.memory_id == memory_id)
            .order_by(AsrOutcome.created_at, AsrOutcome.id)
        ).all()
        return [
            {
                "id": item.id,
                "decision_id": item.decision_id,
                "observation_id": item.observation_id,
                "provider": item.provider,
                "model": item.model_name,
                "rank": item.rank,
                "source_form": item.source_form,
                "target_form": item.target_form,
                "provider_confidence": item.provider_confidence,
                "accepted": item.accepted,
                "reason_code": item.reason_code,
                "created_at": item.created_at,
            }
            for item in outcomes
        ]

    @app.delete("/api/v1/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_memory(memory_id: str, session: DatabaseSession) -> None:
        memory = session.get(Memory, memory_id)
        if memory is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        session.delete(memory)
        session.commit()

    @app.get("/api/v1/decisions/{trace_id}")
    def get_decision(trace_id: str, session: DatabaseSession) -> dict:
        decision = session.get(Decision, trace_id)
        if decision is None:
            raise HTTPException(status_code=404, detail="Decision not found")
        return {
            "trace_id": decision.id,
            "user_id": decision.user_id,
            "raw_asr_text": decision.raw_asr_text,
            "formatted_text": decision.formatted_text,
            "memory_aware_text": decision.memory_aware_text,
            "action": decision.action,
            "trace": json.loads(decision.trace_json),
            "total_latency_ms": decision.total_latency_ms,
            "engine_version": decision.engine_version,
            "created_at": decision.created_at,
        }

    @app.post(
        "/api/v1/decisions/{trace_id}/feedback",
        response_model=DecisionFeedbackResponse,
    )
    def decision_feedback(
        trace_id: str,
        payload: DecisionFeedbackRequest,
        session: DatabaseSession,
    ) -> dict:
        try:
            response = apply_decision_feedback(
                session,
                trace_id=trace_id,
                **payload.model_dump(),
                semantic_encoder=semantic_encoder,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if response is None:
            raise HTTPException(status_code=404, detail="Decision not found")
        return response

    @app.post("/api/v1/reset", response_model=ResetResponse)
    def reset(
        session: DatabaseSession,
        user_id: UserIdQuery = "demo-user",
    ) -> dict:
        deleted_decisions = session.scalar(
            select(func.count()).select_from(Decision).where(Decision.user_id == user_id)
        )
        deleted_observations = session.scalar(
            select(func.count()).select_from(Observation).where(Observation.user_id == user_id)
        )
        deleted_memories = session.scalar(
            select(func.count()).select_from(Memory).where(Memory.user_id == user_id)
        )
        session.execute(delete(Decision).where(Decision.user_id == user_id))
        session.execute(delete(Observation).where(Observation.user_id == user_id))
        session.execute(delete(Memory).where(Memory.user_id == user_id))
        session.commit()
        return {
            "deleted_memories": deleted_memories or 0,
            "deleted_observations": deleted_observations or 0,
            "deleted_decisions": deleted_decisions or 0,
        }

    return app


app = create_app()
