from __future__ import annotations

import math
from pathlib import Path
from typing import Protocol

from .config import Settings


class SemanticEncoder(Protocol):
    enabled: bool
    model_name: str

    def encode(self, text: str) -> list[float] | None: ...

    def status(self) -> dict[str, str | bool | None]: ...


class DisabledSemanticEncoder:
    enabled = False
    model_name = "disabled"

    def encode(self, text: str) -> list[float] | None:
        return None

    def status(self) -> dict[str, str | bool | None]:
        return {
            "enabled": False,
            "model": self.model_name,
            "state": "disabled",
            "error": None,
        }


class FastEmbedSemanticEncoder:
    enabled = True

    def __init__(self, model_name: str, cache_dir: str) -> None:
        self.model_name = model_name
        self.cache_dir = str(Path(cache_dir).resolve())
        self._model = None
        self._error: str | None = None

    def _load(self):
        if self._model is not None:
            return self._model
        try:
            from fastembed import TextEmbedding

            self._model = TextEmbedding(
                model_name=self.model_name,
                cache_dir=self.cache_dir,
                lazy_load=True,
            )
            self._error = None
        except Exception as error:  # pragma: no cover - environment dependent
            self._error = f"{type(error).__name__}: {error}"
            return None
        return self._model

    def encode(self, text: str) -> list[float] | None:
        model = self._load()
        if model is None:
            return None
        try:
            vector = [float(value) for value in next(iter(model.embed([text])))]
        except Exception as error:  # pragma: no cover - model/runtime dependent
            self._error = f"{type(error).__name__}: {error}"
            return None
        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            self._error = "Model returned a zero-length vector"
            return None
        self._error = None
        return [value / norm for value in vector]

    def status(self) -> dict[str, str | bool | None]:
        state = "error" if self._error else "ready" if self._model is not None else "lazy"
        return {
            "enabled": True,
            "model": self.model_name,
            "state": state,
            "error": self._error,
        }


def build_semantic_encoder(settings: Settings) -> SemanticEncoder:
    if not settings.semantic_enabled:
        return DisabledSemanticEncoder()
    return FastEmbedSemanticEncoder(
        model_name=settings.semantic_model,
        cache_dir=settings.semantic_cache_dir,
    )
