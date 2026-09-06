from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from lexitrace.config import Settings  # noqa: E402
from lexitrace.database import build_engine, build_session_factory  # noqa: E402
from lexitrace.engine import store_semantic_evidence  # noqa: E402
from lexitrace.models import ContextEmbedding, Observation  # noqa: E402
from lexitrace.semantic import build_semantic_encoder  # noqa: E402


def main() -> None:
    settings = Settings.from_env()
    encoder = build_semantic_encoder(settings)
    if not encoder.enabled:
        raise SystemExit("Semantic encoding is disabled. Set LEXITRACE_SEMANTIC_ENABLED=true.")

    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    created = 0
    skipped = 0
    with session_factory() as session:
        observations = session.scalars(
            select(Observation).where(Observation.memory_id.is_not(None))
        ).all()
        existing = set(
            session.execute(
                select(ContextEmbedding.observation_id, ContextEmbedding.polarity).where(
                    ContextEmbedding.model_name == encoder.model_name
                )
            ).all()
        )
        for observation in observations:
            context_text = observation.formatted_text or observation.raw_asr_text
            if not context_text or observation.memory is None:
                skipped += 1
                continue
            polarity = "positive" if observation.accepted else "negative"
            if (observation.id, polarity) in existing:
                skipped += 1
                continue
            stored = store_semantic_evidence(
                session,
                memory=observation.memory,
                observation=observation,
                polarity=polarity,
                context_text=context_text,
                source_span=observation.source_span,
                source_type=f"backfill:{observation.evidence_type}",
                reliability=observation.reliability,
                semantic_encoder=encoder,
            )
            created += int(stored)
            skipped += int(not stored)
        session.commit()
    engine.dispose()
    print(f"Created {created} semantic observations; skipped {skipped}.")
    print(encoder.status())


if __name__ == "__main__":
    main()
