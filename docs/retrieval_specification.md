# ValueSignal SEC retrieval specification v3.0.0

This layer retrieves cited filing evidence without an LLM. BM25 remains the production source of truth (`k1=1.5`, `b=0.75`); retrieved language is evidence, not investment advice.

## Corpus pipeline

1. Fetch recent 10-K/10-Q documents with an identifying SEC User-Agent.
2. Remove scripts, hidden/XBRL payloads, page markers, TOC markers, and short lines repeated four or more times. Preserve paragraph breaks and flatten tables in source row/cell order.
3. Detect Part and Item headings. A substantive Part I / Item 1 occurrence anchors the filing body; earlier TOC occurrences are discarded. Canonical 10-K mappings and validated 10-Q Part/Item pairs prevent transient navigation headings from corrupting metadata.
4. Build chunks inside one section only: target 300 words, maximum 450, one-sentence overlap capped at 60 words. Oversized paragraphs split at sentences; oversized sentences use 300-word windows with 40-word overlap. Empty/Reserved sections are omitted and meaningful short sections are retained.
5. Derive stable IDs from accession, canonical section key, and normalized-content hash. Preserve section, paragraph/sentence ranges, source offsets, adjacent IDs, filing metadata, and direct SEC citation.
6. Build the token index and rank with BM25. Ticker and form filters are applied during scoring.
7. Diversify after ranking: retain the top hit, prefer another section at 25% or more of its score, suppress token-Jaccard similarity above 0.70, then fill remaining slots deterministically.

The parser fails closed when structure is unreliable: `SIGNATURES` and exhibit-index headings terminate searchable body text, malformed preambles and implausibly large Item 16 summaries are omitted, and a section owning over 75% of a filing with at least ten chunks is excluded rather than mislabeled.

## Compatibility and citations

Schema 3 consumers use `sectionKey` and fall back to legacy `item`. Legacy `id`, `item`, `form`, `url`, dates, accession, and word offsets remain present. Evidence cards expose section/title, sequence, boundary, ranges, score, chunk ID, accession, and source URL.

The index includes a `corpusHash` derived from ordered chunk IDs. Any future semantic overlay must reject vectors when this hash, dimensions, chunk order, or chunk IDs differ, and must fall back to BM25. Vector generation is optional and cannot block publication.

## Validation

`python scripts/audit_search.py` checks schema/citations, unique IDs, offsets, chunk sizes, fallback/front-matter counts, metadata gaps, canonical form/Part/Item compatibility, structural contamination, section monopolies, per-filing/ticker/form/section coverage, and near duplicates. It reports raw and diversified precision@3 and reciprocal rank against canonical section keys. COST-specific assertions are a TODO until COST enters the universe.

No Ollama, embedding generation, synthesis model, browser WebLLM, paid API, chatbot, or stock-signal mutation belongs in this phase.
