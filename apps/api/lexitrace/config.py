from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    cors_origins: tuple[str, ...]

    @classmethod
    def from_env(cls) -> Settings:
        origins = os.getenv(
            "LEXITRACE_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        )
        return cls(
            database_url=os.getenv("LEXITRACE_DATABASE_URL", "sqlite:///./data/lexitrace.db"),
            cors_origins=tuple(item.strip() for item in origins.split(",") if item.strip()),
        )
