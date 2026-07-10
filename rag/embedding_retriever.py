from __future__ import annotations

from typing import Any, Callable, Sequence

import numpy as np

from rag.embedding_store import EmbeddingStore


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("Query and cached embedding dimensions differ.")
    a, b = np.asarray(left, dtype=np.float32), np.asarray(right, dtype=np.float32)
    denominator = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float(np.dot(a, b) / denominator) if denominator else 0.0


def embedding_search(store: EmbeddingStore, chunks: Sequence[dict[str, Any]], query: str, *,
                     embed: Callable[[str], list[float]], ticker: str | None = None,
                     form_type: str | None = None, limit: int = 3) -> list[dict[str, Any]]:
    if limit < 1: return []
    query_vector = embed(query)
    if len(query_vector) != store.dimensions:
        raise ValueError("Query and cached embedding dimensions differ.")
    ranked = []
    for chunk, vector in zip(chunks, store.vectors):
        if ticker and chunk.get("ticker") != ticker: continue
        form = chunk.get("formType") or chunk.get("form")
        if form_type and form != form_type: continue
        ranked.append({**chunk, "embeddingScore": round(cosine_similarity(query_vector, vector), 8)})
    ranked.sort(key=lambda row: (-row["embeddingScore"], str(row.get("chunkId") or row.get("id"))))
    return ranked[:limit]
