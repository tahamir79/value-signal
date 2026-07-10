# Local Ollama RAG

ValueSignal's optional RAG layer explains—not changes—the deterministic stock signal. It uses only ticker-filtered SEC chunks and remains independent of Vercel and the scheduled ETL workflow.

## Setup

```powershell
pip install -r requirements-rag.txt
ollama pull nomic-embed-text
ollama pull llama3.2:3b
python scripts/build_rag_embeddings.py
python scripts/run_rag.py "What risks could make this company a value trap?" --ticker AAPL
```

Configuration defaults are listed in `.env.example`. Embeddings are cached at `.cache/rag/embeddings.json` and are reused only when corpus hash, model, dimensions, chunk IDs, and ordering match. A stale/missing cache or unavailable Ollama service visibly falls back to BM25 evidence. Use `--mode bm25 --no-synthesize` for guaranteed retrieval-only operation.

## Contracts

- Modes: `bm25`, `embedding`, and default `hybrid` (60% normalized BM25 plus 40% normalized cosine similarity).
- Default context: three diversified chunks, at most 6,000 prompt characters.
- Synthesis: local `llama3.2:3b`; embeddings: local `nomic-embed-text`; no paid or browser APIs.
- Answers must cite retrieved chunk IDs, use only supplied evidence, disclose insufficiency, avoid price predictions/advice, and never relabel the scoring signal.
- `python -m rag.evaluate_rag --ticker AAPL` evaluates retrieval-only behavior. Add `--synthesize` when local Ollama and a populated filing index are available.

The checked-in search index may be empty before its first live SEC refresh. Build embeddings only after `public/data/search_index.json` contains chunks.
