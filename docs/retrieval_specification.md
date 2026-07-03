# ValueSignal SEC retrieval specification v1.0.0

Phase 07 implements retrieval and citations without an LLM. Retrieved filing language is source evidence, not generated analysis.

## Pipeline

1. Read recent 10-K and 10-Q metadata from SEC submissions.
2. Preserve ticker, CIK, accession, filing/report dates, form, primary document, and SEC Archives URL.
3. Fetch filing HTML with the identifying ValueSignal User-Agent.
4. Remove markup, scripts, table-of-contents markers, page-number lines, and repeated short headers.
5. Detect `Item` headings and create approximately 220-word chunks with 40-word boundary overlap.
6. Tokenize chunks, remove a compact stop-word set, and build an inverted term-frequency index.
7. Rank ticker-filtered passages with BM25 (`k1=1.5`, `b=0.75`).
8. Return source text with form, item, filing date, accession, matching terms, score, and direct citation URL.

## Retrieval contract

- Empty chunks are discarded.
- Filing metadata must survive every transformation.
- Search never invents a passage when no terms match.
- Citation URLs must point to `https://www.sec.gov/Archives/`.
- Retrieved source text must remain visually separate from quantitative summaries.
- Search terms are rankings, not semantic conclusions; users must inspect the linked filing.

The fixture evaluation set covers risk factors, supply chains, cybersecurity, liquidity/debt, and legal proceedings. The audit prints top token frequencies and BM25 term traces.
