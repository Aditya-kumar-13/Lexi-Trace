from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    cors_origins: tuple[str, ...]
    semantic_enabled: bool = False
    semantic_model: str = "BAAI/bge-small-en-v1.5"
    semantic_cache_dir: str = "./data/models"
    semantic_threads: int = 1
    max_request_bytes: int = 65_536

    @classmethod
    def from_env(cls) -> Settings:
        origins = os.getenv(
            "LEXITRACE_CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        )
        return cls(
            database_url=os.getenv("LEXITRACE_DATABASE_URL", "sqlite:///./data/lexitrace.db"),
            cors_origins=tuple(item.strip() for item in origins.split(",") if item.strip()),
            semantic_enabled=os.getenv("LEXITRACE_SEMANTIC_ENABLED", "true").lower()
            in {"1", "true", "yes", "on"},
            semantic_model=os.getenv("LEXITRACE_SEMANTIC_MODEL", "BAAI/bge-small-en-v1.5"),
            semantic_cache_dir=os.getenv("LEXITRACE_SEMANTIC_CACHE_DIR", "./data/models"),
            semantic_threads=max(1, int(os.getenv("LEXITRACE_SEMANTIC_THREADS", "1"))),
            max_request_bytes=max(1_024, int(os.getenv("LEXITRACE_MAX_REQUEST_BYTES", "65536"))),
        )
