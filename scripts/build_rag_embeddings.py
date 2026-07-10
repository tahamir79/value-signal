from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag.config import RagConfig
from rag.embedding_store import StaleEmbeddingStore, load_store, make_store, save_store
from rag.ollama_client import get_embeddings


def _load_resume(output: Path, *, corpus_hash: str, model: str, chunk_ids: list[str]) -> list[list[float]]:
    if not output.exists():
        return []
    try:
        raw = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if raw.get("corpusHash") != corpus_hash or raw.get("model") != model:
        return []
    cached_ids = [str(value) for value in raw.get("chunkIds", [])]
    if cached_ids != chunk_ids[:len(cached_ids)]:
        return []
    vectors = raw.get("vectors", [])
    if not isinstance(vectors, list) or len(vectors) != len(cached_ids):
        return []
    try:
        return [[float(value) for value in row] for row in vectors]
    except (TypeError, ValueError):
        return []


def _save_partial(output: Path, *, corpus_hash: str, model: str, chunk_ids: list[str], vectors: list[list[float]]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    dimensions = len(vectors[0]) if vectors else 0
    payload = {"schemaVersion": "1.0.0", "status": "partial", "corpusHash": corpus_hash, "model": model,
               "dimensions": dimensions, "chunkIds": chunk_ids[:len(vectors)], "chunkOrdering": chunk_ids[:len(vectors)],
               "vectors": vectors}
    output.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")


def _embedding_text(chunk: dict, max_chars: int) -> str:
    text = str(chunk.get("text") or "")
    heading = " ".join(str(chunk.get(key) or "") for key in ("ticker", "formType", "sectionKey", "sectionTitle"))
    return f"{heading}\n{text[:max_chars]}".strip()


def build_embeddings(index_path: Path, output: Path, *, force: bool = False, batch_size: int = 64,
                     max_chars: int = 1200) -> str:
    index = json.loads(index_path.read_text(encoding="utf-8"))
    chunks = index.get("documents", [])
    corpus_hash = index.get("corpusHash")
    if not chunks or not corpus_hash:
        raise ValueError("The SEC search index is empty or missing its corpus hash. Refresh it first.")
    config = RagConfig.from_env()
    chunk_ids = [str(chunk.get("chunkId") or chunk.get("id")) for chunk in chunks]
    if output.exists() and not force:
        try:
            load_store(output).validate(corpus_hash=corpus_hash, model=config.embed_model, chunks=chunks)
            return "Embedding cache is current; reused existing vectors."
        except StaleEmbeddingStore:
            pass
    if batch_size < 1:
        raise ValueError("batch_size must be greater than zero.")
    if max_chars < 100:
        raise ValueError("max_chars must be at least 100.")
    vectors = [] if force else _load_resume(output, corpus_hash=corpus_hash, model=config.embed_model, chunk_ids=chunk_ids)
    if vectors:
        print(f"Resuming embedding cache at {len(vectors)}/{len(chunks)} chunks.", file=sys.stderr)
    for start in range(len(vectors), len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        vectors.extend(get_embeddings([_embedding_text(chunk, max_chars) for chunk in batch], config.embed_model))
        _save_partial(output, corpus_hash=corpus_hash, model=config.embed_model, chunk_ids=chunk_ids, vectors=vectors)
        print(f"Embedded {len(vectors)}/{len(chunks)} chunks.", file=sys.stderr)
    save_store(output, make_store(corpus_hash, config.embed_model, chunks, vectors))
    return f"Built {len(vectors)} cached embeddings at {output}."


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the local ValueSignal Ollama embedding cache")
    parser.add_argument("--index", type=Path, default=Path("public/data/search_index.json"))
    parser.add_argument("--output", type=Path, default=Path(".cache/rag/embeddings.json"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--max-chars", type=int, default=1200)
    args = parser.parse_args()
    try:
        print(build_embeddings(args.index, args.output, force=args.force, batch_size=args.batch_size, max_chars=args.max_chars))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
