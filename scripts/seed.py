import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from lexitrace.config import Settings  # noqa: E402
from lexitrace.database import build_engine, build_session_factory  # noqa: E402
from lexitrace.engine import observe_correction, teach_explicit  # noqa: E402
from lexitrace.semantic import build_semantic_encoder  # noqa: E402


def main() -> None:
    settings = Settings.from_env()
    engine = build_engine(settings.database_url)
    semantic_encoder = build_semantic_encoder(settings)
    session_factory = build_session_factory(engine)
    with session_factory() as session:
        teach_explicit(
            session,
            user_id="demo-user",
            canonical_form="Kivi",
            variants=["Kiwi"],
            scope_mode="contextual",
            positive_context=[],
            negative_context=[],
            formatted_text="Review the Kiwi service dashboard.",
            accepted_text="Review the Kivi service dashboard.",
            semantic_encoder=semantic_encoder,
        )
        observe_correction(
            session,
            user_id="demo-user",
            raw_asr_text="",
            formatted_text="Open the Kiwi integration settings.",
            accepted_text="Open the Kivi integration settings.",
            confirm_candidates=True,
            semantic_encoder=semantic_encoder,
        )
        teach_explicit(
            session,
            user_id="demo-user",
            canonical_form="Aaditya",
            variants=["Aditya"],
            scope_mode="global",
            positive_context=[],
            negative_context=[],
            formatted_text="Ask Aditya to review this.",
            accepted_text="Ask Aaditya to review this.",
            semantic_encoder=semantic_encoder,
        )
    print("Seeded demo-user with Kivi and Aaditya memories.")


if __name__ == "__main__":
    main()
