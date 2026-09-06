import hashlib
from pathlib import Path

from lexitrace.database import Base, build_engine, build_session_factory
from lexitrace.engine import store_semantic_evidence
from lexitrace.models import ContextEmbedding, Memory, Observation
from sqlalchemy import select


class StableEncoder:
    enabled = True

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.calls = 0

    def encode(self, text: str) -> list[float]:
        self.calls += 1
        digest = hashlib.sha256(text.encode()).digest()
        return [value / 255 for value in digest[:8]]


def add_example(session, memory: Memory, encoder: StableEncoder, index: int, text: str) -> bool:
    observation = Observation(
        user_id=memory.user_id,
        memory=memory,
        evidence_type="accepted_correction",
        formatted_text=text,
        accepted_text=text.replace("Kiwi", "Kivi"),
        source_span="Kiwi",
        target_span="Kivi",
        reliability=1.0,
        source_event_id=f"event-{encoder.model_name}-{index}",
    )
    session.add(observation)
    session.flush()
    stored = store_semantic_evidence(
        session,
        memory=memory,
        observation=observation,
        polarity="positive",
        context_text=text,
        source_span="Kiwi",
        source_type="accepted_correction",
        reliability=1.0,
        semantic_encoder=encoder,
        evidence_cap=12,
    )
    session.commit()
    return stored


def make_memory(session, user_id: str) -> Memory:
    memory = Memory(
        user_id=user_id,
        canonical_form="Kivi",
        canonical_normalized="kivi",
        state="confirmed",
        scope_mode="contextual",
    )
    session.add(memory)
    session.commit()
    return memory


def retained_contexts(session, memory: Memory) -> set[str]:
    return {
        item.context_text
        for item in session.scalars(
            select(ContextEmbedding).where(ContextEmbedding.memory_id == memory.id)
        )
    }


def test_semantic_retention_caps_deduplicates_and_replays_deterministically(
    tmp_path: Path,
) -> None:
    engine = build_engine(f"sqlite:///{(tmp_path / 'retention.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    contexts = [f"Review domain {index} in the Kiwi workspace." for index in range(16)]
    with factory() as session:
        first = make_memory(session, "first-user")
        second = make_memory(session, "second-user")
        encoder = StableEncoder("model-v1")
        for index, context in enumerate(contexts):
            assert add_example(session, first, encoder, index, context)
            assert add_example(session, second, encoder, index, context)

        first_contexts = retained_contexts(session, first)
        second_contexts = retained_contexts(session, second)
        assert len(first_contexts) == 12
        assert first_contexts == second_contexts
        calls_before_duplicate = encoder.calls
        assert not add_example(session, first, encoder, 99, contexts[0])
        assert encoder.calls == calls_before_duplicate
        assert retained_contexts(session, first) == first_contexts
    engine.dispose()


def test_new_model_evidence_displaces_old_model_within_the_same_cap(tmp_path: Path) -> None:
    engine = build_engine(f"sqlite:///{(tmp_path / 'model-rollover.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = build_session_factory(engine)
    with factory() as session:
        memory = make_memory(session, "rollover-user")
        old_encoder = StableEncoder("model-v1")
        new_encoder = StableEncoder("model-v2")
        for index in range(12):
            add_example(session, memory, old_encoder, index, f"Old domain {index} uses Kiwi.")
        for index in range(3):
            add_example(session, memory, new_encoder, index, f"New domain {index} uses Kiwi.")

        evidence = list(
            session.scalars(select(ContextEmbedding).where(ContextEmbedding.memory_id == memory.id))
        )
        assert len(evidence) == 12
        assert sum(item.model_name == "model-v2" for item in evidence) == 3
        assert sum(item.model_name == "model-v1" for item in evidence) == 9
    engine.dispose()
