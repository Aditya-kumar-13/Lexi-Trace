from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from lexitrace.config import Settings  # noqa: E402
from lexitrace.database import Base, build_engine  # noqa: E402
from lexitrace.main import create_app  # noqa: E402
from lexitrace.semantic import DisabledSemanticEncoder  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="lexitrace-review-") as temp_dir:
        database_url = f"sqlite:///{(Path(temp_dir) / 'review.db').as_posix()}"
        engine = build_engine(database_url)
        Base.metadata.create_all(engine)
        engine.dispose()
        app = create_app(
            Settings(database_url=database_url, cors_origins=()),
            semantic_encoder_override=DisabledSemanticEncoder(),
        )
        with TestClient(app) as client:
            memory = client.post(
                "/api/v1/observations/explicit",
                json={
                    "canonical_form": "Kivi",
                    "variants": ["Kiwi"],
                    "scope_mode": "contextual",
                    "positive_context": ["service deployment"],
                    "negative_context": ["fruit shopping"],
                },
            )
            positive = client.post(
                "/api/v1/infer",
                json={"formatted_text": "Review the Kiwi service deployment."},
            )
            negative = client.post(
                "/api/v1/infer",
                json={"formatted_text": "Buy kiwi fruit while shopping."},
            )
            feedback = client.post(
                f"/api/v1/decisions/{positive.json()['trace_id']}/feedback",
                json={"verdict": "correct", "feedback_scope": "auto"},
            )
            first_aditya = client.post(
                "/api/v1/observations/explicit",
                json={
                    "canonical_form": "Aaditya",
                    "variants": ["Aditya"],
                    "scope_mode": "contextual",
                    "positive_context": ["finance budget approval"],
                },
            )
            second_aditya = client.post(
                "/api/v1/observations/explicit",
                json={
                    "canonical_form": "Adithya",
                    "variants": ["Aditya"],
                    "scope_mode": "contextual",
                    "positive_context": ["design prototype review"],
                },
            )
            ambiguous = client.post(
                "/api/v1/infer",
                json={"formatted_text": "Ask Aditya to join the call."},
            )
            inspected = client.get(f"/api/v1/memories/{memory.json()['id']}")
            exported = client.get("/api/v1/users/demo-user/export")
            metrics = client.get("/api/v1/metrics")
            reset = client.post("/api/v1/reset", json={"user_id": "demo-user"})
            responses = [
                memory,
                positive,
                negative,
                feedback,
                first_aditya,
                second_aditya,
                ambiguous,
                inspected,
                exported,
                metrics,
                reset,
            ]
            if any(response.status_code >= 400 for response in responses):
                raise RuntimeError([response.text for response in responses])
            result = {
                "teach": {
                    "canonical_form": memory.json()["canonical_form"],
                    "state": memory.json()["state"],
                },
                "positive": {
                    "output": positive.json()["memory_aware_text"],
                    "action": positive.json()["action"],
                    "reason": positive.json()["counterfactual"]["reason_code"],
                },
                "negative": {
                    "output": negative.json()["memory_aware_text"],
                    "action": negative.json()["action"],
                    "reason": negative.json()["counterfactual"]["reason_code"],
                },
                "feedback": {
                    "verdict": feedback.json()["verdict"],
                    "resolved_scopes": feedback.json()["resolved_feedback_scopes"],
                },
                "two_adityas": {
                    "output": ambiguous.json()["memory_aware_text"],
                    "action": ambiguous.json()["action"],
                    "candidates": len(ambiguous.json()["candidates"]),
                },
                "inspection": {
                    "canonical_form": inspected.json()["canonical_form"],
                    "context_evidence_count": inspected.json()["context_evidence_count"],
                },
                "portable_memories": len(exported.json()["memories"]),
                "request_metrics": metrics.json(),
                "reset": reset.json(),
            }
            if result["positive"]["output"] != "Review the Kivi service deployment.":
                raise RuntimeError("Positive memory did not apply")
            if result["negative"]["output"] != "Buy kiwi fruit while shopping.":
                raise RuntimeError("Negative context safety failed")
            if result["two_adityas"]["output"] != "Ask Aditya to join the call.":
                raise RuntimeError("Ambiguous people should not be auto-corrected")
            print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
