from __future__ import annotations

import os
from dataclasses import dataclass


def _positive_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}.") from exc
    if value < 1:
        raise ValueError(f"{name} must be greater than zero.")
    return value


@dataclass(frozen=True)
class RagConfig:
    ollama_base_url: str = "http://localhost:11434"
    embed_model: str = "nomic-embed-text"
    synth_model: str = "llama3.2:3b"
    top_k: int = 3
    max_context_chars: int = 6000

    @classmethod
    def from_env(cls) -> "RagConfig":
        return cls(
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", cls.ollama_base_url).rstrip("/"),
            embed_model=os.getenv("OLLAMA_EMBED_MODEL", cls.embed_model),
            synth_model=os.getenv("OLLAMA_SYNTH_MODEL", cls.synth_model),
            top_k=_positive_int("RAG_TOP_K", cls.top_k),
            max_context_chars=_positive_int("RAG_MAX_CONTEXT_CHARS", cls.max_context_chars),
        )

