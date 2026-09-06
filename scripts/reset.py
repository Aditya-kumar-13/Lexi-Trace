import sys
from pathlib import Path

from sqlalchemy import delete

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from lexitrace.config import Settings  # noqa: E402
from lexitrace.database import build_engine, build_session_factory  # noqa: E402
from lexitrace.models import Decision, Memory, Observation  # noqa: E402


def main() -> None:
    engine = build_engine(Settings.from_env().database_url)
    session_factory = build_session_factory(engine)
    with session_factory() as session:
        session.execute(delete(Decision))
        session.execute(delete(Observation))
        session.execute(delete(Memory))
        session.commit()
    print("Reset all LexiTrace memory, evidence, and decisions.")


if __name__ == "__main__":
    main()
