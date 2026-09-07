from __future__ import annotations

import json
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .config import Settings
from .database import build_engine, build_session_factory, get_session
from .engine import (
    POLICY,
    apply_decision_feedback,
    apply_memory_state_override,
    build_formatter_context,
    discover_memory_conflicts,
    infer,
    memory_to_dict,
    merge_memories,
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
from .observability import RequestMetrics
from .schemas import (
    CorrectionObservationRequest,
    CorrectionObservationResponse,
    DecisionFeedbackRequest,
    DecisionFeedbackResponse,
    ExplicitTeachRequest,
    FormatterContextRequest,
    FormatterContextResponse,
    InferenceRequest,
    InferenceResponse,
    MemoryImportRequest,
    MemoryMergeRequest,
    MemoryResponse,
    MemoryUpdateRequest,
    MemoryVersionResponse,
    ResetResponse,
)
from .semantic import SemanticEncoder, build_semantic_encoder

DatabaseSession = Annotated[Session, Depends(get_session)]
UserIdQuery = Annotated[str, Query(min_length=1)]


def delete_user_state(session: Session, user_id: str) -> dict[str, int]:
    counts = {
        "deleted_memories": session.scalar(
            select(func.count()).select_from(Memory).where(Memory.user_id == user_id)
        )
        or 0,
        "deleted_observations": session.scalar(
            select(func.count()).select_from(Observation).where(Observation.user_id == user_id)
        )
        or 0,
        "deleted_decisions": session.scalar(
            select(func.count()).select_from(Decision).where(Decision.user_id == user_id)
        )
        or 0,
    }
    session.execute(delete(Decision).where(Decision.user_id == user_id))
    session.execute(delete(Observation).where(Observation.user_id == user_id))
    session.execute(delete(Memory).where(Memory.user_id == user_id))
    session.commit()
    return counts


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
        version="1.2.0",
        description="Inspectable personal word memory for transcript formatting.",
        lifespan=lifespan,
    )
    app.state.session_factory = session_factory
    app.state.semantic_encoder = semantic_encoder
    app.state.request_metrics = RequestMetrics()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved_settings.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_safety_and_metrics(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        content_length = request.headers.get("content-length")
        try:
            request_too_large = (
                content_length is not None
                and int(content_length) > resolved_settings.max_request_bytes
            )
        except ValueError:
            request_too_large = True
        if request_too_large:
            response = JSONResponse(
                status_code=413,
                content={
                    "error": {
                        "code": "REQUEST_TOO_LARGE",
                        "message": (f"Request exceeds {resolved_settings.max_request_bytes} bytes"),
                        "request_id": request_id,
                    }
                },
            )
        else:
            response = await call_next(request)
        latency_ms = (time.perf_counter() - started) * 1000
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        app.state.request_metrics.record(
            f"{request.method} {route_path}", response.status_code, latency_ms
        )
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content={
                "error": {
                    "code": f"HTTP_{error.status_code}",
                    "message": str(error.detail),
                    "request_id": request.state.request_id,
                }
            },
            headers=error.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "request_id": request.state.request_id,
                    "issues": [
                        {
                            "location": ".".join(str(item) for item in issue["loc"]),
                            "message": issue["msg"],
                            "type": issue["type"],
                        }
                        for issue in error.errors()
                    ],
                }
            },
        )

    @app.get("/api/v1/health")
    def health() -> dict:
        return {
            "status": "ok",
            "version": "1.2.0",
            "semantic": semantic_encoder.status(),
            "policy_version": POLICY.version,
        }

    @app.get("/api/v1/metrics")
    def metrics() -> dict:
        return app.state.request_metrics.snapshot()

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
            semantic_evidence_cap=POLICY.semantic_evidence_cap,
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
            semantic_evidence_cap=POLICY.semantic_evidence_cap,
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

    @app.post("/api/v1/formatter-context", response_model=FormatterContextResponse)
    def formatter_context(payload: FormatterContextRequest, session: DatabaseSession) -> dict:
        return build_formatter_context(session, **payload.model_dump())

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

    @app.get("/api/v1/conflicts")
    def list_conflicts(
        session: DatabaseSession,
        user_id: UserIdQuery = "demo-user",
    ) -> list[dict]:
        memories = session.scalars(select(Memory).where(Memory.user_id == user_id)).all()
        return discover_memory_conflicts(list(memories))

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

    @app.post("/api/v1/memories/{memory_id}/merge", response_model=MemoryResponse)
    def merge_memory(
        memory_id: str,
        payload: MemoryMergeRequest,
        session: DatabaseSession,
    ) -> dict:
        target = session.get(Memory, memory_id)
        source = session.get(Memory, payload.source_memory_id)
        if target is None or source is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        try:
            merged = merge_memories(
                session,
                target=target,
                source=source,
                reason=payload.reason,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        return memory_to_dict(merged)

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
                semantic_evidence_cap=POLICY.semantic_evidence_cap,
            )
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if response is None:
            raise HTTPException(status_code=404, detail="Decision not found")
        return response

    @app.get("/api/v1/users/{user_id}/export")
    def export_memories(user_id: str, session: DatabaseSession) -> dict:
        memories = session.scalars(
            select(Memory).where(Memory.user_id == user_id).order_by(Memory.canonical_normalized)
        ).all()
        return {
            "schema_version": "lexitrace-portable-memory-v1",
            "bundle_id": str(uuid.uuid4()),
            "user_id": user_id,
            "exported_at": datetime.now(UTC).isoformat(),
            "memories": [
                {
                    "canonical_form": memory.canonical_form,
                    "variants": [variant.surface_form for variant in memory.variants],
                    "state": memory.state,
                    "scope_mode": memory.scope_mode,
                    "positive_context": json.loads(memory.positive_context_json),
                    "negative_context": json.loads(memory.negative_context_json),
                }
                for memory in memories
            ],
            "note": "Portable definitions exclude transcript and decision history by design.",
        }

    @app.post("/api/v1/users/{user_id}/import")
    def import_memories(
        user_id: str,
        payload: MemoryImportRequest,
        session: DatabaseSession,
    ) -> dict:
        deleted = (
            delete_user_state(session, user_id)
            if payload.mode == "replace"
            else {
                "deleted_memories": 0,
                "deleted_observations": 0,
                "deleted_decisions": 0,
            }
        )
        imported_ids: list[str] = []
        for index, item in enumerate(payload.memories):
            import_event_id = f"import:{payload.bundle_id}:{index}"
            existing = session.scalar(
                select(Observation).where(
                    Observation.user_id == user_id,
                    Observation.source_event_id == import_event_id,
                )
            )
            if existing is not None and existing.memory_id is not None:
                imported_ids.append(existing.memory_id)
                continue
            memory = teach_explicit(
                session,
                user_id=user_id,
                canonical_form=item.canonical_form,
                variants=item.variants,
                scope_mode=item.scope_mode,
                positive_context=item.positive_context,
                negative_context=item.negative_context,
                event_id=import_event_id,
                semantic_encoder=semantic_encoder,
            )
            memory.state = item.state
            record_memory_version(
                session,
                memory,
                action="memory_imported",
                reason=f"Portable bundle {payload.bundle_id}",
                actor="user",
            )
            session.commit()
            imported_ids.append(memory.id)
        return {
            "bundle_id": payload.bundle_id,
            "mode": payload.mode,
            "imported_memories": len(imported_ids),
            "memory_ids": imported_ids,
            **deleted,
        }

    @app.delete("/api/v1/users/{user_id}")
    def delete_user(user_id: str, session: DatabaseSession) -> dict:
        return delete_user_state(session, user_id)

    @app.post("/api/v1/reset", response_model=ResetResponse)
    def reset(
        session: DatabaseSession,
        user_id: UserIdQuery = "demo-user",
    ) -> dict:
        return delete_user_state(session, user_id)

    return app


app = create_app()
