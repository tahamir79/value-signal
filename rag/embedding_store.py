from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


class StaleEmbeddingStore(ValueError):
    """The cached vectors do not describe the current corpus exactly."""


def chunk_id(chunk: dict[str, Any]) -> str:
    value = chunk.get("chunkId") or chunk.get("id")
    if not value:
        raise ValueError("Every embedding source chunk must have a chunkId or id.")
    return str(value)


@dataclass(frozen=True)
class EmbeddingStore:
    corpus_hash: str
    model: str
    dimensions: int
    chunk_ids: list[str]
    vectors: list[list[float]]
    model_version: str | None = None

    def validate(self, *, corpus_hash: str, model: str, chunks: Sequence[dict[str, Any]]) -> None:
        expected_ids = [chunk_id(row) for row in chunks]
        reasons = []
        if self.corpus_hash != corpus_hash: reasons.append("corpus hash changed")
        if self.model != model: reasons.append("embedding model changed")
        if self.chunk_ids != expected_ids: reasons.append("chunk IDs or ordering changed")
        if len(self.vectors) != len(expected_ids): reasons.append("vector count differs")
        if any(len(vector) != self.dimensions for vector in self.vectors): reasons.append("vector dimensions differ")
        if reasons:
            raise StaleEmbeddingStore("Stale embedding cache: " + "; ".join(reasons) + ".")

    def to_dict(self) -> dict[str, Any]:
        return {"schemaVersion": "1.0.0", "corpusHash": self.corpus_hash, "model": self.model,
                "modelVersion": self.model_version, "dimensions": self.dimensions,
                "chunkIds": self.chunk_ids, "chunkOrdering": self.chunk_ids, "vectors": self.vectors}


def save_store(path: Path, store: EmbeddingStore) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store.to_dict(), separators=(",", ":")), encoding="utf-8")


def load_store(path: Path) -> EmbeddingStore:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return EmbeddingStore(str(raw["corpusHash"]), str(raw["model"]), int(raw["dimensions"]),
                              [str(value) for value in raw["chunkIds"]],
                              [[float(value) for value in row] for row in raw["vectors"]], raw.get("modelVersion"))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise StaleEmbeddingStore(f"Embedding cache is unreadable or invalid: {path}.") from exc


def make_store(corpus_hash: str, model: str, chunks: Sequence[dict[str, Any]], vectors: Sequence[Sequence[float]],
               model_version: str | None = None) -> EmbeddingStore:
    converted = [[float(value) for value in vector] for vector in vectors]
    dimensions = len(converted[0]) if converted else 0
    if not converted or dimensions < 1 or len(converted) != len(chunks) or any(len(row) != dimensions for row in converted):
        raise ValueError("Embedding vectors must be non-empty, equal-dimensional, and match the chunk count.")
    return EmbeddingStore(corpus_hash, model, dimensions, [chunk_id(row) for row in chunks], converted, model_version)

