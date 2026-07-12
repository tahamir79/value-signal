from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from scripts.build_search_index import bm25_search
from scripts.retrieval import diversify_results

INDEX_PATH = Path("public/data/search_index.json")


def _empty_index() -> dict[str, Any]:
    return {"documentCount": 0, "averageDocumentLength": 0, "documentLengths": [], "documents": [], "postings": {}}


def load_search_index(path: Path = INDEX_PATH, ticker: str | None = None) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        index = json.load(handle)
    if index.get("indexMode") == "per_ticker":
        if not ticker:
            return _empty_index()
        entry = (index.get("tickers") or {}).get(ticker.upper())
        if not entry:
            return _empty_index()
        with Path(entry["path"]).open(encoding="utf-8") as handle:
            return json.load(handle)
    return index


def _normalize(rows: list[dict[str, Any]]) -> dict[str, float]:
    values = [float(row.get("score", row.get("embeddingScore", 0))) for row in rows]
    if not values:
        return {}
    low, high = min(values), max(values)
    return {
        str(row.get("chunkId") or row.get("id")): (float(row.get("score", row.get("embeddingScore", 0))) - low) / (high - low) if high > low else 1.0
        for row in rows
    }


def retrieve(
    query: str, *, ticker: str | None = None, form_type: str | None = None,
    mode: str = "hybrid", top_k: int = 3, index: dict[str, Any] | None = None,
    embedding_search: Callable[..., list[dict[str, Any]]] | None = None,
) -> tuple[list[dict[str, Any]], list[str], str]:
    """Return ranked evidence, warnings, and the effective retrieval mode."""
    requested = mode.lower()
    if requested not in {"bm25", "embedding", "hybrid"}:
        raise ValueError("retrieval_mode must be bm25, embedding, or hybrid")
    if top_k < 1:
        raise ValueError("top_k must be greater than zero")
    index = index or load_search_index(ticker=ticker)
    candidate_k = max(top_k * 4, 12)
    lexical = bm25_search(index, query, ticker=ticker, form=form_type, limit=candidate_k)
    if requested == "bm25":
        return lexical[:top_k], [], "bm25"

    warnings: list[str] = []
    try:
        if embedding_search is None:
            from rag.config import RagConfig
            from rag.embedding_retriever import embedding_search as search_vectors
            from rag.embedding_store import load_store
            from rag.ollama_client import get_embedding
            config = RagConfig.from_env()
            chunks = index.get("documents", [])
            store = load_store(Path(".cache/rag/embeddings.json"))
            try:
                store.validate(corpus_hash=index.get("corpusHash", ""), model=config.embed_model, chunks=chunks)
                semantic_chunks = chunks
            except Exception:
                expected_ids = [str(row.get("chunkId") or row.get("id")) for row in chunks]
                if (store.corpus_hash != index.get("corpusHash", "") or store.model != config.embed_model
                        or store.chunk_ids != expected_ids[:len(store.chunk_ids)] or not store.vectors):
                    raise
                semantic_chunks = chunks[:len(store.vectors)]
                warnings.append(f"Semantic embedding cache is partial ({len(store.vectors)}/{len(chunks)} chunks). Results may be incomplete until the cache finishes.")
            semantic = search_vectors(store, semantic_chunks, query, embed=lambda text: get_embedding(text, config.embed_model),
                                      ticker=ticker, form_type=form_type, limit=candidate_k)
            semantic = [{**row, "score": row["embeddingScore"]} for row in semantic]
        else:
            semantic = embedding_search(query, index=index, ticker=ticker, form_type=form_type, top_k=candidate_k)
    except Exception:
        semantic = []
    if not semantic:
        warnings.append("Semantic embeddings unavailable. Using BM25 retrieval.")
        return lexical[:top_k], warnings, "bm25"
    if requested == "embedding":
        return semantic[:top_k], warnings, "embedding"

    bm_norm, em_norm = _normalize(lexical), _normalize(semantic)
    by_id: dict[str, dict[str, Any]] = {}
    for row in lexical + semantic:
        key = str(row.get("chunkId") or row.get("id"))
        by_id.setdefault(key, dict(row))
    ranked = []
    for key, row in by_id.items():
        row["bm25Score"] = bm_norm.get(key, 0.0)
        row["embeddingScore"] = em_norm.get(key, 0.0)
        row["score"] = round(.60 * row["bm25Score"] + .40 * row["embeddingScore"], 6)
        ranked.append(row)
    ranked.sort(key=lambda row: (-row["score"], str(row.get("chunkId") or row.get("id"))))
    return diversify_results(ranked, top_k), warnings, "hybrid"
