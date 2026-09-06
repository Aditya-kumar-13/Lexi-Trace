import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from lexitrace.config import Settings  # noqa: E402
from lexitrace.database import Base, build_engine, build_session_factory  # noqa: E402
from lexitrace.engine import teach_explicit  # noqa: E402


def main() -> None:
    settings = Settings.from_env()
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)
    session_factory = build_session_factory(engine)
    with session_factory() as session:
        teach_explicit(
            session,
            user_id="demo-user",
            canonical_form="Kivi",
            variants=["Kiwi"],
            scope_mode="contextual",
            positive_context=["Sarvam", "service", "dictation"],
            negative_context=["fruit", "food", "shopping"],
            formatted_text="Review the Sarvam Kiwi service.",
            accepted_text="Review the Sarvam Kivi service.",
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
        )
    print("Seeded demo-user with Kivi and Aaditya memories.")


if __name__ == "__main__":
    main()
