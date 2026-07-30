# ValueSignal Lite Project Blueprint and Session Handoff

**Version:** 1.0
**Date:** 2026-07-05
**Purpose:** Preserve full project context between Codex/GPT sessions so the implementation does not drift when context refreshes.

---

## 1. Executive Summary

**ValueSignal Lite** is a financial research platform that identifies potentially undervalued public companies for further research using valuation signals, business-quality metrics, risk indicators, historical backtesting, and public filing evidence.

The website is not a stock-picking bot and does not provide buy/sell advice. Its job is to classify stocks into transparent research signals and then help the user inspect the evidence behind those signals.

The evidence layer is based on SEC filings first. The RAG layer should come later, after retrieval/chunking is stable. The final RAG system should run locally using Ollama, not browser WebLLM and not paid APIs.

**Core project sentence:**

> ValueSignal Lite is a financial research platform that uses valuation scoring, quality metrics, risk gates, SEC filing retrieval, and local RAG synthesis to surface and explain potentially undervalued stocks for further research.

---

## 2. Current Reset Point

The project is being reset to a phase **before unstable RAG features were implemented**.

The immediate goal is **not** to build LLM synthesis yet.

The current development order is:

1. Fix SEC retrieval and chunking.
2. Stabilize BM25 evidence retrieval.
3. Add rich evidence metadata and citations.
4. Add retrieval evaluation.
5. Commit this as a stable retrieval foundation.
6. Only then add local Ollama RAG.

The retrieval/chunking upgrade reportedly passed. If that remains true in the codebase, the next phase is local Ollama RAG using the improved chunks.

---

## 3. Main Product Mission

The main mission of the website is:

```text
Find potentially undervalued public companies for further research using valuation signals, quality metrics, risk indicators, backtesting, and public filing evidence.
```

The value-trap question is only one possible user question. The broader workflow is:

```text
Stock screener finds a research candidate
  -> stock receives a primary signal
  -> user opens stock detail page
  -> user asks evidence questions
  -> retrieval system returns filing evidence
  -> local RAG synthesizes only retrieved evidence
```

---

## 4. Official Signal Taxonomy

Each stock should receive exactly one primary research signal. These are not investment recommendations.

- Potentially undervalued: Value evidence is comparatively strong and major risk gates have not been triggered. The stock is researchable as a possible undervaluation candidate.
- Quality watchlist: Business-quality evidence is strong, but the valuation case needs patience or more support. Strong business, but valuation support is not yet decisive.
- Value trap risk: A low valuation is accompanied by weakening quality or elevated balance-sheet concerns. Cheapness may be explained by risk.
- Momentum risk: Recent price behavior adds uncertainty to an otherwise researchable company. Price action, volatility, or drawdown complicates the case.
- Neutral: The current evidence is mixed and does not support a stronger research classification. No strong research signal at this time.
- Insufficient evidence: Required observations are missing or too stale for a responsible classification. Do not force a classification.

### Signal Ownership

The deterministic scoring engine assigns the signal.

The RAG system explains, supports, weakens, or complicates the signal. It must not automatically relabel the stock.

Possible RAG evidence assessments:

```text
Supports signal
Weakens signal
Mixed evidence
Insufficient evidence
Possible reclassification candidate
```

---

## 5. Target Product Layers

ValueSignal Lite should be built as layered software:

```text
1. Stock universe and ETL
2. Financial feature engineering
3. Scoring and signal engine
4. Dashboard and stock detail pages
5. SEC filing ingestion and retrieval
6. Evidence cards and citations
7. Retrieval evaluation
8. Local Ollama RAG synthesis
9. Analyst brief generation
10. Deployment and demo documentation
```

The RAG layer should not replace the screener. It explains the screener's evidence.

---

## 6. Retrieval Foundation Scope

The retrieval/chunking upgrade is the foundation of the entire project. The LLM will only be useful if retrieved chunks are coherent, cited, and metadata-rich.

### Required retrieval pipeline

```text
SEC filing HTML / text
  -> clean filing text
  -> detect SEC Part / Item sections
  -> create section-aware chunks
  -> preserve metadata and offsets
  -> build BM25 search index
  -> retrieve evidence chunks
  -> show citations and metadata
  -> run retrieval evaluation
```

### Required BM25 behavior

Preserve existing BM25 behavior unless there is a proven bug:

```text
BM25 tokenization
k1 = 1.5
b = 0.75
ticker filters
form filters
citations
existing retrieval interface
```

---

## 7. Filing-Aware SEC Chunking Rules

Replace naive fixed-size chunking with deterministic SEC-aware chunking.

Target chunk behavior:

```text
target chunk size: approximately 300 words
maximum chunk size: 450 words
overlap: one sentence
overlap cap: 60 words
never cross SEC item boundaries
```

### Cleaning requirements

The cleaner should:

- preserve paragraph breaks;
- remove scripts;
- remove oversized XBRL payloads;
- remove page numbers;
- remove table-of-contents markers;
- remove boilerplate headers and footers;
- remove normalized short lines repeated at least four times;
- flatten tables in original row and cell order;
- exclude generic front matter;
- preserve substantive preambles such as Forward-Looking Statements when they contain at least 100 words.

### SEC section detection

Parse Part and Item headings into canonical keys:

```text
part-i:item-1
part-i:item-1a
part-i:item-2
part-ii:item-7
part-ii:item-7a
part-ii:item-8
```

For 10-Q filings, distinguish repeated Part I and Part II item numbers.

### Chunking rules

Within each SEC item section:

1. Accumulate complete paragraphs toward about 300 words.
2. Start a new chunk before exceeding 450 words.
3. Split oversized paragraphs at sentence boundaries.
4. If one sentence exceeds 450 words, use 300-word fixed windows with 40-word overlap.
5. Merge short tails when possible.
6. Preserve meaningful short sections such as "None" or "Not applicable."
7. Omit empty or Reserved sections.
8. Never cross SEC item boundaries.

### Stable chunk IDs

Generate IDs from:

```text
accession number
canonical section key
normalized chunk-content hash
```

Identical source content should keep the same ID even if earlier filing text moves.

---

## 8. Search Schema 3.0.0

Bump the search schema to:

```text
3.0.0
```

Retain existing fields required by current consumers and add:

```text
CIK
primary document
Part
item number
canonical sectionKey
section title
chunk sequence
boundary type
paragraph range
sentence range
section-relative word offsets
cleaned-document word offsets
cleaned-document character offsets
previous chunk ID
next chunk ID
```

Keep legacy fields available:

```text
item
text
id
chunkId
URLs
dates
accession
existing word offsets
```

### Minimum chunk object

```ts
type FilingChunk = {
  schemaVersion: "3.0.0";
  id: string;
  chunkId: string;
  ticker: string;
  companyName: string;
  cik: string | null;
  formType: "10-K" | "10-Q" | "8-K" | string;
  filingDate: string;
  accession: string;
  primaryDocument: string | null;
  part: string | null;
  itemNumber: string | null;
  sectionKey: string | null;
  sectionTitle: string | null;
  item: string | null;
  chunkSequence: number;
  boundaryType: string;
  paragraphRange: [number, number] | null;
  sentenceRange: [number, number] | null;
  sectionWordStart: number | null;
  sectionWordEnd: number | null;
  documentWordStart: number | null;
  documentWordEnd: number | null;
  documentCharStart: number | null;
  documentCharEnd: number | null;
  previousChunkId: string | null;
  nextChunkId: string | null;
  sourcePath: string | null;
  sourceUrl: string | null;
  text: string;
};
```

---

## 9. Post-Ranking Diversification

Keep BM25 scoring unchanged. Apply deterministic diversification after ranking:

1. Retain the highest-scoring result.
2. Prefer another section when its score is at least 25 percent of the top score.
3. Suppress candidates with token Jaccard similarity above 0.70.
4. Fill remaining slots with non-overlapping chunks from the same section only if needed.

Apply identical diversification in:

- Python retrieval;
- browser retrieval, if applicable;
- stock-page search endpoint.

---

## 10. Evidence Cards

Evidence cards should display:

- canonical Part / Item;
- section title;
- chunk sequence;
- paragraph range;
- sentence range;
- boundary type;
- filing date;
- accession or source URL;
- retrieval score;
- chunk ID;
- exact text excerpt.

The user should always be able to inspect the exact evidence behind any answer.

---

## 11. Retrieval Evaluation

Use frozen retrieval queries before changing ranking logic.

Metrics:

```text
BM25 precision@3
reciprocal rank
citation validity
section diversity
unique chunk IDs
metadata survival
```

Test queries should include:

```text
margin pressure
inventory risk
liquidity risk
supply chain disruption
competition risk
material weakness
value trap risk
demand weakness
```


```text
value-trap question returns coherent Item 1A or MD&A passages
margin question returns coherent margin or MD&A passages
demand question returns coherent demand / operations passages
liquidity question returns coherent liquidity / capital resources passages
```

---

## 12. Future Local Ollama RAG Scope

Only after retrieval/chunking passes, add local RAG.

Local models:

```text
Embedding: nomic-embed-text
Synthesis: llama3.2:3b
Ollama base URL: http://localhost:11434
```

Recommended environment:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_SYNTH_MODEL=llama3.2:3b
RAG_TOP_K=3
RAG_MAX_CONTEXT_CHARS=6000
```

### RAG flow

```text
User question
  -> ticker filter
  -> retrieval over improved SEC chunks
  -> BM25 retrieval
  -> optional embedding retrieval with nomic-embed-text
  -> hybrid ranking
  -> top 3 evidence chunks
  -> compact prompt
  -> local llama3.2:3b through Ollama
  -> cautious cited analyst answer
```

### RAG files

```text
rag/
  config.py
  ollama_client.py
  embedding_store.py
  embedding_retriever.py
  hybrid_retriever.py
  prompt_builder.py
  synthesize.py
  rag_pipeline.py
  evaluate_rag.py
```

Do not require browser WebLLM. Browser inference was tested and caused instability. Keep browser LLM out of the MVP.

---

## 13. Local RAG Prompt

The local Llama prompt should be cautious and evidence-bound:

```text
You are a cautious financial research assistant.

Use only the retrieved SEC filing evidence provided below.
Do not use outside knowledge.
Do not invent facts.
Do not give buy, sell, or hold advice.
Do not predict stock prices.
Cite chunk IDs for every major claim.
If the retrieved evidence is weak or incomplete, say that the evidence is insufficient.
Separate evidence from interpretation.
Use cautious financial research language.

Your job is to explain whether the retrieved evidence supports, weakens, or complicates the stock's research signal.

Required structure:

Summary:
Evidence Supporting the Signal:
Risk Evidence:
Counterpoints or Missing Evidence:
Interpretation:
What To Research Next:
Limitations:
Citations:
```

The model must never receive full filings. It should only receive top retrieved chunks with metadata.

---

## 14. Current Events and Catalyst Layer - Later Phase

The LLM should not invent current events. If current events are needed, build a separate current-events/catalyst corpus.

Potential future sources:

- 8-K filings;
- 8-K exhibits;
- company press releases;
- investor relations announcements;
- earnings release text;
- product launch announcements;
- management commentary;
- manually curated event files.

The current-events layer should be indexed like the SEC corpus:

```text
event source
  -> clean text
  -> chunk with metadata
  -> add to retrieval corpus
  -> retrieve event evidence
  -> synthesize with filing evidence
```

Do not rely on the LLM or browser to scrape arbitrary websites.

---

## 15. Non-Goals and Guardrails

Do not implement in the stable MVP:

- browser WebLLM synthesis;
- paid OpenAI/Claude/Anthropic APIs;
- generic chatbot behavior;
- LLM-generated stock ratings;
- LLM relabeling of stock signals;
- buy/sell/hold advice;
- price predictions;
- OpenVINO/Ollama-OV backend changes.

OpenVINO/Ollama-OV can be benchmarked later after normal Ollama RAG works.

---

## 16. Project Commands - Verified From Actual Repo

Run from `C:\Users\stahm\Projects\Decision Scientist`:

```powershell
git status
npm ci
npm run dev
npm run typecheck
npm run test:brief
npm run build
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/run_etl.py
python scripts/build_search_index.py
python scripts/audit_features.py
python scripts/audit_scoring.py
python scripts/audit_backtest.py
python scripts/audit_search.py
python scripts/build_rag_embeddings.py
python scripts/run_rag.py "What risks could make this company a value trap?" --ticker AAPL
python -m rag.evaluate_rag --ticker AAPL
```

`VS_USER_AGENT` must contain an identifying contact email for SEC commands. Local RAG dependencies are installed with `pip install -r requirements-rag.txt`; Ollama must expose `nomic-embed-text` and `llama3.2:3b` at `http://localhost:11434`.

---

## 17. GPT-5.5 / Codex Implementation Context Update Protocol

This section is the most important part for minimizing context loss.

At the start of every new coding session, GPT-5.5/Codex must update this Markdown file with the actual implementation context from the repository.

### Instruction to GPT-5.5/Codex

**Before writing new code, inspect the repository and update this blueprint with the code implementation context. Do not rely on memory. Do not assume old architecture is still true.**

Run or inspect:

```bash
pwd
git branch --show-current
git status
git log -1 --oneline
ls
find . -maxdepth 3 -type f | sort
cat package.json
```

Also inspect the relevant source files for:

```text
app routes
stock dashboard
stock detail page
SEC filing ingestion scripts
chunking scripts
search index generation
BM25 retrieval
search endpoint
search audit
retrieval evaluation
evidence card components
RAG-related files, if any
```

### Required implementation context block

GPT-5.5/Codex should append or update a section called:

```text
## 18. Live Implementation Context - Updated by GPT-5.5/Codex
```

It must include:

```text
Repository path:
Git branch:
Last commit:
Deployment target:
Framework:
Main routes:
Data directories:
Search index files:
Chunking files:
Retrieval files:
Evidence UI files:
Scoring files:
Current schema version:
Known working commands:
Known failing commands:
Current implementation status:
Open bugs:
Next recommended task:
Files changed in this session:
Important architectural decisions:
```

### Session update rule

At the end of every meaningful development session, GPT-5.5/Codex should update:

```text
What changed
What passed
What failed
What is still unknown
What should be done next
```

The goal is to make this Markdown file the durable context source between sessions.

---

## 18. Live Implementation Context - Updated by GPT-5.5/Codex

**Historical note:** this 2026-07-06 block is preserved for provenance. For the current implementation context, use Section 25, "Live Implementation Context - Conservative Scenario and Pipeline Health Update."

**Updated:** 2026-07-06 (America/Chicago)

- **Repository path:** `C:\Users\stahm\Projects\Decision Scientist`
- **Git branch:** `improvedsecRetreival` (feature branch; no upstream configured)
- **Last local commit:** `19580bc feat: upgrade SEC filing retrieval foundation`
- **Product remote:** `value-signal -> https://github.com/tahamir79/value-signal.git`; default branch `main`. Do not push ValueSignal work to the build-console `origin` remote.
- **Deployment target:** Vercel, redeployed from commits pushed to the ValueSignal repository.
- **Framework:** Next.js 15 App Router, React 19, TypeScript 5.8; Python 3 ETL/research pipeline.
- **Main routes:** `/`, `/dashboard`, `/backtest`, `/methodology`, `/stock/[ticker]`, and dynamic `/api/search`.
- **Data directories:** generated artifacts in `public/data/`; ignored local RAG vectors in `.cache/rag/`.
- **Search index:** `public/data/search_index.json`; generated by `scripts/build_search_index.py`; audited by `scripts/audit_search.py`.
- **Chunking/cleaning:** `scripts/chunk_filings.py`, `scripts/text_cleaning.py`, and `scripts/providers/sec_filings.py`.
- **Retrieval:** Python BM25 in `scripts/build_search_index.py`, diversification in `scripts/retrieval.py`, server retrieval in `src/lib/search.ts`, local RAG modules under `rag/`.
- **Evidence UI:** `src/components/FilingEvidencePanel.tsx`; stock page integration in `src/app/stock/[ticker]/page.tsx`.
- **Scoring:** `scripts/features.py`, `scripts/scoring.py`, `docs/feature_dictionary.md`, and `docs/scoring_specification.md`.
- **Current search schema:** local feature branch `3.0.0`; remote `value-signal/main` still has schema `1.0.0` until the retrieval upgrade is merged.
- **Known working commands:** commands in Section 16; 48 Python tests, 5 TypeScript brief tests, all publication audits, type-check, and the production build passed on 2026-07-06. Local RAG remains outside the deployment commit.
- **Known failing/blocked commands:** full local embedding-cache generation exceeded the 20-minute execution window twice (first per chunk, then batched); no incomplete cache is published. BM25 fallback remains operational.
- **Current implementation status:** Phases 1â€“8 exist; schema-3 retrieval is committed locally; local Ollama RAG is implemented but not committed; `nomic-embed-text` and `llama3.2:3b` are installed and responsive. The live local ETL/index refresh completed on 2026-07-05.
- **Automation:** `.github/workflows/refresh-data.yml` runs at `23:25 UTC` Mondayâ€“Friday. The latest scheduled run on `value-signal/main` succeeded on 2026-07-04 UTC (Friday evening Chicago time); no weekend run is expected.
- **Open bugs:** fixed and live-validated — schema-3 builder incorrectly referenced `security.name` instead of `security.company_name`; TOC/body anchoring, terminal signatures, malformed preambles, Item 16 overflow, and section-monopoly failures were corrected. Remaining local-only issue: embedding-cache generation needs resumable checkpointing or faster local hardware.
- **Next recommended task:** commit only the retrieval/code/artifact/blueprint changes, merge/push explicitly to `value-signal/main`, and manually dispatch/verify the workflow. Keep local RAG uncommitted.
- **Files changed this session:** this blueprint, `scripts/build_search_index.py`, `tests/test_retrieval.py`, all refreshed `public/data/*.json` artifacts, and the pre-existing local RAG implementation/documentation.
- **Architectural decisions:** BM25 remains authoritative and always available; semantic retrieval is optional; Ollama is local-only and never required by Vercel/GitHub Actions; generated `public/data/*.json` is not hand-maintained source.

### Session handoff

- **What changed:** repository context was reconciled with the blueprint; product remote and workflow schedule were verified; the schema-3 company-name bug was fixed; live artifacts were refreshed.
- **What passed:** ETL 10/10; upgraded schema-3 index 1,996 chunks/10,389 terms; structural/schema/citation audit; raw BM25 precision@3 `0.7500`, MRR `0.8750`; diversified precision@3 `0.5833`, MRR `0.8750`; 48 Python tests; 5 TypeScript tests; type-check; production Next.js build; GitHub's latest scheduled run was successful.
- **What failed:** local vector-cache generation exceeded 20 minutes. Two intermediate strengthened audits correctly blocked malformed sections before the final live corpus passed. Nothing failed in the scheduler; the apparent two-day gap is the expected weekend pause.
- **Still unknown:** end-to-end hybrid RAG over the full live corpus and the next online workflow result after schema 3 is pushed.
- **Next:** push only to the `value-signal` remote, manually dispatch/verify the workflow, then address retrieval relevance and resumable embeddings.

---

## 19. First Prompt To Use In Next Codex Session

Paste this into Codex at the start of the next session:

```text
Please read ValueSignal_Project_Blueprint.md first.

Before writing code, inspect the actual repository and update the section "Live Implementation Context - Updated by GPT-5.5/Codex" with the current implementation details.

Do not assume any previous architecture is still correct.

Run or inspect: pwd, git branch, git status, git log -1, package.json, routes, scripts, search index generation, chunking code, retrieval code, evidence UI, and tests.

After updating the blueprint, summarize the current state and propose the smallest safe next step.
```

---

## 20. Portfolio Positioning

Use this final project framing:

```text
Built ValueSignal Lite, a financial research platform that classifies public companies into transparent research signals and uses SEC-aware filing retrieval, BM25 search, metadata-rich evidence cards, and local Ollama RAG to explain potentially undervalued stocks with citations.
```

Stronger resume version after RAG works:

```text
Built a local financial RAG pipeline using SEC-aware filing chunks, BM25 retrieval, nomic-embed-text embeddings, hybrid ranking, and local Llama 3.2 synthesis through Ollama to explain public-company research signals with citations.
```

---

## 21. Scaling Architecture - Broad Universe Foundation

The scaling phase is a separate data-engineering track. It must scale ValueSignal Lite safely from the starter universe toward broader U.S.-listed public-company coverage without fetching every ticker at once.

Current scaling direction:

```text
universe builder first
  -> SEC-safe request/cache layer
  -> staged filing discovery and ingestion
  -> SEC-aware chunking per ticker
  -> BM25 index manifests
  -> scoring/data-quality reports
  -> frontend search/filter/lazy evidence
```

Universe modes:

```text
starter
watchlist
sp500_or_largecap
sec_listed_core
sec_listed_all
custom
```

Core files:

```text
scripts/universe/build_universe.py
scripts/universe/normalize_symbols.py
scripts/universe/universe_filters.py
scripts/universe/universe_manifest.py
scripts/sec/sec_client.py
scripts/filings/ingest_filings.py
scripts/pipeline/run_scaled_pipeline.py
tests/test_scaled_universe.py
tests/test_scaled_filings.py
```

Generated local artifacts:

```text
data/universe/universe.json
data/universe/universe_manifest.json
data/reports/pipeline_report.json
data/reports/failures.json
data/filings/filing_metadata.json
data/cache/sec/filings/raw_html/
data/cache/sec/filings/clean_text/
data/cache/sec/filings/chunks/
```

Scaling commands:

```powershell
python scripts/universe/build_universe.py --mode starter
python scripts/universe/build_universe.py --mode sec_listed_core --limit 50
python scripts/pipeline/run_scaled_pipeline.py --mode starter
python scripts/pipeline/run_scaled_pipeline.py --mode sec_listed_core --limit 250 --resume
python scripts/filings/ingest_filings.py --universe data/universe/universe.json --forms 10-K 10-Q --limit 25
python scripts/pipeline/run_scaled_pipeline.py --mode starter --limit 10 --ingest-filings
python -m unittest tests.test_scaled_universe -v
python -m unittest tests.test_scaled_filings -v
```

Important guardrails:

- Do not fetch every ticker without an explicit limit.
- Do not exceed SEC fair-access guidance; default request pacing should stay at or below 5 requests per second.
- Do not require paid APIs, embeddings, or local Llama for online deployment.
- Keep unsupported/fund/warrant/unit/OTC-like rows marked, not silently deleted.
- Keep BM25 as the production fallback/source of truth.
- Keep local Ollama RAG separate from deployment unless explicitly enabled.

---

## 22. Balance-Sheet Scoring Handoff

- **Scoring v1 checkpoint:** `fa3c1ae`, with branch `checkpoint/scoring-v1-before-balance-sheet` and tag `scoring-v1-before-balance-sheet`.
- **Baseline tooling:** `data/reports/scoring_baseline_before_balance_sheet_integration.json`, `scripts/write_scoring_baseline.py`, and `scripts/compare_scoring_outputs.py`.
- **Balance-sheet scoring module:** `scripts/balance_sheet.py`; default mode is `BALANCE_SHEET_SCORING_MODE=official`.
- **Supported modes:** `off`, `shadow`, `experimental`, and `official`. Official mode blends balance-sheet risk penalty into the balance-sheet risk score, lightly blends balance-sheet quality into quality, preserves `balanceSheetScoringShadow`, and emits `balanceSheetOfficialChange`.
- **Frontend/RAG context:** stock detail pages can display balance-sheet health, and local RAG receives balance-sheet snapshot, metric, gate, and target-comparison context.
- **Methodology:** see `docs/balance_sheet_scoring.md`.

---

## 23. Scaled BM25 Handoff

- **Current BM25 layout:** `public/data/search_index.json` is a lightweight manifest with `indexMode: "per_ticker"`; ticker corpora live under `public/data/search/{TICKER}.json`.
- **Current indexed coverage:** 199 tickers, 51,742 SEC filing chunks, 38,915 terms.
- **Why modular:** a full-universe monolithic search index was about 477 MB and too slow/heavy; compact per-ticker files total about 209 MB and let frontend search/local RAG load only one ticker at a time.
- **Status backfill:** `scripts/build_search_index.py` updates `bm25Indexed`, filing chunk status, latest filing date, and coverage counts after index generation.
- **Loaders:** server search uses `src/lib/search.ts`; local RAG uses `rag/hybrid_retriever.py`.
- **Validation run:** retrieval/RAG unit tests passed; local BM25 smoke test for ticker `A` returned 3 cited liquidity/debt chunks from `part-ii:item-7`; `npm run typecheck` and `npm run build` passed.
- **Deployment caution:** do not revert to a monolithic `public/data/search_index.json`. If scheduled automation is expanded to scaled BM25, it should use `scripts/build_search_index.py --universe data/universe/universe.json --limit 250` and account for the longer runtime plus `public/data/search/` artifacts.
- **Scheduled refresh:** `.github/workflows/refresh-data.yml` now runs scaled ETL with `data/universe/universe.json`, limit `250`, balance-sheet scoring in `shadow` mode, rebuilds the per-ticker BM25 indexes, audits the fast manifest-aware search path, and commits `public/data/search/`, `public/data/stocks/`, aggregate JSON, ETL report, and coverage report.

---

## 24. Immediate Next Step

Current immediate workflow:

1. Finish validating the conservative historical scenario, saved-position projection math, stale artifact cleanup, and pipeline health report.
2. Review the generated artifact counts and validation results with the user.
3. Commit only after review.
4. Do not deploy this change automatically; the current instruction requires stopping for review before deployment.

Keep local RAG available only as a separate local/experimental system. Do not reintroduce browser WebLLM.

---

## 25. Live Implementation Context - Conservative Scenario and Pipeline Health Update

**Updated:** 2026-07-21 UTC
**Repository path:** `C:\Users\stahm\Projects\Decision Scientist`
**Git branch:** `scale-universe-foundation`
**Checkpoint commit before this work:** `6043820 checkpoint: before historical scenario and pipeline health cleanup`
**Deployment target:** Vercel production at `value-signal.vercel.app`, but this work is not deployed until reviewed.
**Framework:** Next.js 15 App Router, React 19, TypeScript, Python ETL/research pipeline.

### What changed in this session

- Added a separate `ValueSignal Conservative Historical Scenario v1` for saved-position 30/90-day projections.
- Preserved zero-return baseline as the selected 30-day and 90-day forecast model.
- Added explicit projection-source selection:
  - approved non-baseline forecast model;
  - conservative historical scenario;
  - unavailable with reason.
- Updated saved-stock UI labels so personal scenarios are clearly user-entered and separate from ValueSignal estimates.
- Fixed saved-stock layout overflow by allowing nested grid/flex children and form controls to shrink inside their containers.
- Added stale generated artifact cleanup:
  - ETL removes stale `public/data/stocks/{TICKER}.json`;
  - forecast pipeline reads current `stocks/summary.json` and removes stale `public/data/forecasts/{TICKER}.json`.
- Added `scripts/pipeline_health.py` with full internal and compact public health reports.
- Updated workflow to generate pipeline health during scheduled refresh.
- Updated technical/methodology docs:
  - `docs/ValueSignal_Technical_Map.md`;
  - `docs/forecast_methodology.md`;
  - `docs/saved_stock_projection_methodology.md`;
  - `docs/artifact_schemas.md`;
  - this blueprint.

### Current generated artifact counts

- Active stock summary records: 245.
- Stock detail files: 245.
- Forecast summary records: 245.
- Forecast detail files: 245.
- Conservative historical scenarios available: 203.
- Insufficient-history scenarios: 42.
- Stale scenarios: 0.
- Selected 30-day model: zero-return baseline.
- Selected 90-day model: zero-return baseline.
- Search index coverage: 199 indexed tickers.
- Pipeline health: partial_success, release readiness ready_with_known_limitations, with 0 critical failures.

### Current partial-success causes

- 5 ETL ticker failures from provider HTTP 404s:
  - `AAC`
  - `ADBT`
  - `ADIG`
  - `AIBZ`
  - `AIST`
- 42 forecast artifacts have insufficient sparse historical samples for the conservative scenario.
- Balance-sheet context is partial/unavailable for some companies because SEC companyfacts does not expose every target field.
- Health fixture fields currently separate:
  - critical failures: 0;
  - true noncritical failures: 47;
  - expected unavailable items: 246;
  - balance-sheet/data-quality warnings: 226.

### Expected unavailable states

- Scaled scheduled ETL intentionally skips full backtest generation.
- Analyst target provider is not configured.
- Local Ollama/RAG is not part of production deployment.

### Key files changed

Core pipeline:

```text
scripts/run_etl.py
scripts/forecast/pipeline.py
scripts/forecast/audit_forecasts.py
scripts/pipeline_health.py
scripts/backtest.py
scripts/build_search_index.py
.github/workflows/refresh-data.yml
```

Frontend:

```text
src/types/forecast.ts
src/lib/position-projections.ts
src/components/SavedStocksConsole.tsx
src/app/globals.css
```

Tests:

```text
tests/test_pipeline.py
tests/test_forecast_pipeline.py
tests/test_pipeline_health.py
tests/positionProjections.test.ts
package.json
```

Docs:

```text
docs/ValueSignal_Technical_Map.md
docs/forecast_methodology.md
docs/saved_stock_projection_methodology.md
docs/artifact_schemas.md
docs/ValueSignal_Project_Blueprint.md
```

### Example current AAPL scenario

- Current price: 326.59.
- Market data as of: 2026-07-20.
- 30-day return estimate: 1.999019%.
- 30-day estimated price: 333.1186.
- 30-day sparse samples: 25.
- 90-day return estimate: 3.757468%.
- 90-day estimated price: 338.8615.
- 90-day sparse samples: 23.

### Important architectural decisions

- The conservative scenario is display fallback only; it does not override model selection.
- Forecast challenger promotion is gated by `VS_ALLOW_EXPERIMENTAL_FORECAST_PROMOTION=true`.
- Current official selected forecast model remains zero-return baseline for both horizons.
- Analyst target fields stay unsupported/null until a legitimate data provider is added.
- Generated JSON artifacts are cleaned by scripts, not hand-edited.
- Partial success is allowed only when core artifacts exist and noncritical failures are explicitly reported.

### Validation commands for this state

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/audit_features.py
python scripts/audit_scoring.py
python scripts/audit_backtest.py
python scripts/audit_search.py
python scripts/forecast/audit_training_dataset.py
python scripts/forecast/evaluate_models.py
python scripts/forecast/audit_forecasts.py
python scripts/pipeline_health.py
npm run test:brief
npm run typecheck
npm run build
```

### Next recommended task

Run the full validation stack, review the final report with the user, then commit only if approved. Do not deploy until explicitly approved after review.

---

## 26. Live Implementation Context - Growth Spurt Detector

**Updated:** 2026-07-21 UTC
**Repository path:** `C:\Users\stahm\Projects\Decision Scientist`
**Git branch:** `scale-universe-foundation`
**Pre-change rollback anchors:** branch `checkpoint/pre-growth-spurt-detector`, tag `checkpoint-pre-growth-spurt-detector`, both pointing to `543be62`.

### What changed

- Added a deterministic, benchmark-backed Growth Spurt detector for recent historical price behavior.
- The detector is display-only in v1 and does not alter official ValueSignal scores, confidence, or signal classification.
- Added `GROWTH_SPURT_MODE=off|shadow|display|official`; default/display mode shows artifacts, while `official` remains reserved and inert.
- Added generated `growthSpurt` artifacts to:
  - `public/data/dashboard.json`
  - `public/data/stocks/summary.json`
  - `public/data/stocks/{TICKER}.json`
- Added point-in-time benchmark report:
  - `data/reports/growth_spurt_benchmark.json`
- Added dashboard Growth column, score sorting, and "Growth spurt detected" filter.
- Added stock-detail Recent Trend card with score, 63-day return, SPY excess return, trend consistency, drawdown, percentile, as-of date, warnings, and non-prediction disclosure.
- Updated pipeline health to report detector coverage.
- Updated methodology, feature, scoring, backtesting, and technical docs.

### Detector mechanics

Growth Spurt means:

```text
Recent prices have formed a relatively persistent and orderly upward trend.
```

It does not mean:

```text
buy, sell, hold, guaranteed continuation, forecasted upside, or official signal improvement.
```

Formula summary:

- adjusted close preferred, close fallback;
- 63-session primary window;
- 21-session confirmation window;
- Theil-Sen trend on log prices;
- score weights:
  - 30% direction;
  - 25% consistency;
  - 20% SPY-relative strength;
  - 15% drawdown control;
  - 10% recent confirmation/acceleration;
- one-day spike dominance warning/rejection via `largestOneDayContribution63d`;
- cross-sectional percentiles for slope, R2, SPY excess, drawdown-control score, and total score.

Detected threshold:

```text
growthSpurtScore >= 70
trendSlope63d > 0
return63d > 0
return21d >= 0
trendFitR2_63d >= 0.45
positiveWeekRatio63d >= 0.60
maxDrawdown63d >= -0.15
no ONE_DAY_SPIKE_DOMINATED warning
```

Emerging threshold:

```text
growthSpurtScore >= 55
trendSlope63d > 0
return63d > 0
no spike dominance
```

### Current generated detector counts

- Stocks evaluated: 245.
- Growth Spurt detected: 19.
- Emerging upward trend: 30.
- Not detected: 187.
- Unavailable: 9.
- Calculation failures: 0.
- Median detected 63-day return: about 20.97%.
- Median detected 63-day SPY excess return: about 16.20%.

Example current detections:

```text
AAPL, JPM, KO, ABBV, ACA, ACCL, ACIW, ACNB, ACVA, AEG
```

Example current one-day-spike rejections:

```text
GOOGL, AMZN, XOM, F, A, AACB, AAON, ABEV, ABLV, ABNB
```

### Benchmark snapshot

`scripts/benchmark_growth_spurt.py` produced:

- candidate snapshots: 9,950;
- detected snapshots: 570;
- forward observations: 2,280;
- unique tickers detected historically: 135.

Forward benchmark summaries:

| Horizon | Positive forward % | Median forward return | Median SPY excess | False-positive rate |
|---:|---:|---:|---:|---:|
| 21 sessions | 51.58% | 0.24% | -0.87% | 24.21% |
| 30 sessions | 49.47% | -0.04% | -1.02% | 26.84% |
| 63 sessions | 49.82% | -0.14% | -3.40% | 38.07% |
| 90 sessions | 50.35% | 0.29% | -4.67% | 39.30% |

Interpretation: current starting thresholds are good enough for a descriptive UI tag but not strong enough to justify official scoring integration. Treat benchmark results as calibration evidence, not a performance claim.

### Validation results

Passed:

```text
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/audit_features.py
python scripts/audit_scoring.py
python scripts/benchmark_growth_spurt.py
python scripts/audit_backtest.py
python scripts/audit_search.py
python scripts/forecast/audit_training_dataset.py
python scripts/forecast/audit_forecasts.py
python scripts/pipeline_health.py
npm run test:brief
npm run typecheck
npm run build
```

Notes:

- Python suite passed 100 tests.
- TypeScript test bundle passed 12 tests.
- Production Next.js build passed.
- Pipeline health remains `partial_success` with `ready_with_known_limitations`, 0 critical failures, 47 noncritical ticker/forecast failures, 246 expected unavailable items, and 235 data-quality warnings.
- `python scripts/forecast/evaluate_models.py` timed out on the scaled fixture after a long validation window. Growth Spurt does not change forecast model selection; selected 30-day and 90-day models remain zero-return baseline.
- This feature has not been deployed. Stop for review before deployment.

### Key files

```text
scripts/growth_spurt.py
scripts/build_growth_spurt_artifacts.py
scripts/benchmark_growth_spurt.py
scripts/run_etl.py
scripts/pipeline_health.py
tests/test_growth_spurt.py
tests/test_pipeline.py
tests/test_pipeline_health.py
tests/growthSpurtBadge.test.tsx
src/components/GrowthSpurtBadge.tsx
src/features/dashboard/StockTable.tsx
src/app/stock/[ticker]/page.tsx
src/app/methodology/page.tsx
src/types/stock.ts
src/lib/etl.ts
src/lib/research.ts
```

### Commands

```powershell
python scripts/build_growth_spurt_artifacts.py
python scripts/benchmark_growth_spurt.py
python scripts/pipeline_health.py
npm run test:brief
```

Full validation remains:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/audit_features.py
python scripts/audit_scoring.py
python scripts/benchmark_growth_spurt.py
python scripts/audit_backtest.py
npm run typecheck
npm run build
```

### Guardrails

- Do not blend Growth Spurt into official scoring until a later reviewed scoring-integration phase.
- Do not present the tag as a price prediction.
- Keep insufficient detector history as `unavailable`, not zero.
- Preserve generated artifacts as script outputs, not hand-maintained source.
- Stop for review before deployment for this feature.

---

## 27. Live Implementation Context - Saved Outcome Cards and Market-Target Guardrails

**Updated:** 2026-07-21 UTC
**Repository path:** `C:\Users\stahm\Projects\Decision Scientist`
**Git branch:** `scale-universe-foundation`
**Pre-change rollback anchors:** branch `checkpoint/pre-saved-outcomes-final-instruction`, tag `checkpoint-pre-saved-outcomes-final-instruction`, both pointing to `543be62`.

### What changed

- Refactored saved-position projections into normalized `HoldingOutcome` records in `src/lib/position-projections.ts`.
- Added a reusable `src/components/HoldingOutcomeCard.tsx` renderer for normalized saved-position outcome cards.
- Replaced the main saved-position display with two primary ValueSignal cards:
  - `ValueSignal 30 Days`;
  - `ValueSignal 90 Days`.
- Hid customer-facing Market Target 30/90 cards until a legitimate analyst-target provider is configured, while preserving backend `AnalystTargetArtifact` and `marketTargetOutcomes` extension points.
- Moved zero-return baseline names, selected model details, sample counts, and personal scenario fields into collapsed panels.
- Kept personal 30/90-day percentages separate as `Personal 30-Day Scenario %` and `Personal 90-Day Scenario %`.
- Standardized holding gain/loss math:
  - `estimatedGainLossPerShare = estimatedSellPrice - currentPurchasePrice`;
  - `estimatedTotalGainLoss = sharesHeld * estimatedGainLossPerShare`;
  - `estimatedPositionValue = sharesHeld * estimatedSellPrice`;
  - dollar allocation first converts to `impliedShares = dollarAllocation / currentPrice`, then uses the same per-share formulas.
- Cleaned the final saved-position card UI:
  - dollar allocations display `Implied shares`;
  - share positions display `Shares held`;
  - total gain/loss appears only once as the card headline;
  - ValueSignal unavailable cards use horizon-specific observation details;
  - market-target unavailable outcomes stay in backend data only and do not render as primary cards;
  - displayed dates use `Jul 20, 2026` style formatting instead of raw ISO timestamps.
- Added market-target time-scaling logic, but only as a future backend extension when a legitimate provider supplies target mean, current price at collection, and a documented horizon.
- Current market-target state remains unavailable and hidden from the saved-portfolio primary interface because no analyst target provider is configured.
- Updated pipeline health so expected unavailable forecast/market-target/Growth Spurt coverage gaps do not count as real failures.
- Added `--limit all` / omitted-limit parsing and batch metadata for scaling scripts without removing the safe scheduled batch cap.

### Customer-facing language

Use:

```text
Estimated gain/loss
Estimated gain/loss per share
Shares held
Implied shares
Estimated return
Estimated sell price
Estimated position value
Scenario range
Projection source
```

Do not use "earnings" for a user's saved-position outcome. "Earnings" is reserved for company net income/EPS/earnings releases.

### Market-target mechanics

Market-target scenarios are not ValueSignal estimates and are not analyst-issued 30/90-day forecasts. If a future provider supplies a target with known horizon:

```text
totalTargetReturn = targetMean / currentPriceAtCollection - 1
marketImpliedReturn30 = (1 + totalTargetReturn)^(30 / targetHorizonDays) - 1
marketImpliedReturn90 = (1 + totalTargetReturn)^(90 / targetHorizonDays) - 1
```

The current fixture keeps market-target artifacts unsupported and hidden from the primary saved-portfolio UI. Backend unavailable outcomes report:

```text
Unavailable
Analyst target data is not currently available.
```

Unavailable market-target `HoldingOutcome` records keep `methodology`, `sourceProvider`, and `sourceHorizonDays` null. A market-implied scenario source exists only after a target, provider, horizon, and implied 30/90-day scenario are valid.

### Health state after this update

- Overall status: `partial_success`.
- Release readiness: `ready_with_known_limitations`.
- Critical failures: `0`.
- True noncritical failures: `5` ETL provider 404s.
- Expected unavailable count: `246` items, dominated by unavailable market targets and intentionally skipped scaled backtest.
- Data-quality warnings: `226`, currently from partial balance-sheet context.

### Validation results

Passed:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/audit_features.py
python scripts/audit_scoring.py
python scripts/audit_backtest.py
python scripts/audit_search.py
python scripts/forecast/audit_training_dataset.py
python scripts/forecast/evaluate_models.py
python scripts/forecast/audit_forecasts.py
python scripts/benchmark_growth_spurt.py
python scripts/pipeline_health.py
npm run test:brief
npm run typecheck
npm run build
```

Notes:

- Python suite passed 105 tests.
- TypeScript brief/render/projection suite passed 31 tests after the two-card saved-portfolio cleanup.
- Forecast evaluator passed this time on the scaled fixture and retained zero-return baselines for 30/90 days.
- Production Next.js build passed after the saved-outcome and market-target UI changes.
- This feature has not been deployed. Stop for review before deployment.

---

## 28. Live Implementation Context - Checkpointed Full-Universe ETL

**Updated:** 2026-07-22 UTC
**Git branch:** `scale-universe-foundation`
**Reason:** A single uncapped live ETL process over the supported SEC-listed universe was too fragile for laptop/network interruptions and did not publish artifacts until the whole run ended.

### Current universe scale

- `data/universe/universe.json` contains the uncapped SEC-listed universe built by the scaling track.
- `data/universe/universe_manifest.json` reports:
  - supported operating companies: `6017`;
  - unsupported/excluded symbols: `4397`;
  - total company rows: `10414`.
- The local frontend artifacts now represent the completed checkpoint merge: `5799` published stock records from `6017` supported requests, with `218` isolated noncritical ETL failures.

### New checkpointed ETL workflow

Use `scripts/pipeline/run_checkpointed_etl.py` for broad/full refreshes:

```powershell
$env:VS_USER_AGENT="ValueSignal research ETL <contact>"
$env:BALANCE_SHEET_SCORING_MODE="official"
$env:GROWTH_SPURT_MODE="display"
python scripts/pipeline/run_checkpointed_etl.py --universe data/universe/universe.json --limit all --batch-size 10 --fetch-only --skip-backtest
powershell -ExecutionPolicy Bypass -File scripts/pipeline/diagnose_checkpointed_etl.ps1
python scripts/pipeline/run_checkpointed_etl.py --universe data/universe/universe.json --limit all --batch-size 10 --merge-only --skip-backtest
python scripts/forecast/run_forecast_pipeline.py --summary --scaled-fast
python scripts/pipeline_health.py
```

Mechanics:

- Fetch mode writes raw provider checkpoints into `data/checkpoints/etl_raw/`.
- The active batch checkpoint is atomically rewritten after each ticker, not only after each batch.
- Existing complete batches are cache hits on resume.
- Existing partial batches resume from completed ticker records and ticker-level errors.
- `--max-workers 5` can parallelize up to five ticker fetches inside one process while keeping a single checkpoint writer.
- Do not run multiple independent checkpoint fetch scripts against the same checkpoint directory because they can race on batch files.
- Merge mode replays completed checkpoint data through the existing `scripts/run_etl.py` scoring/export path so official scoring is still one global universe calculation.
- Merge mode blocks incomplete checkpoint sets by default; `--allow-partial-merge` must be intentional.
- `scripts/pipeline/diagnose_checkpointed_etl.ps1` reports the live Python process, batch counts, partial progress, ticker success/failure counts, latest batch file, and latest log lines.
- Future checkpoint fetches default to the same 5-year Yahoo price window as `scripts/run_etl.py`. The first completed full-universe checkpoint used shorter provider-default price histories, so the first scaled-fast forecast set intentionally falls back to sparse historical scenarios where available.

### Operational reality

SEC Company Facts payloads are large for mega-caps. In the first live checkpointed refresh attempt:

- AAPL company facts produced about 34 MB of checkpointed facts and took about 85 seconds.
- MSFT company facts produced about 43 MB of checkpointed facts and took about 86 seconds.

Therefore a true 6,000-company fundamentals refresh may take many hours or days on a laptop, even though it is now resumable. Do not assume full-universe fundamentals can be refreshed quickly without either a stronger runtime, parallelism with SEC-safe rate limiting, or a more selective fundamentals strategy. The current raw checkpoint store is about `26.2 GB` and must stay out of Git.

### Validation added

New tests:

```powershell
python -m unittest tests.test_checkpointed_etl tests.test_pipeline tests.test_scaled_universe -v
```

Passed on 2026-07-22 UTC:

- checkpoint cache reuse;
- partial/incomplete merge blocking;
- complete checkpoint replay through the real scoring/export pipeline;
- existing one-ticker-failure isolation;
- scaled universe parser/regression tests.

### Parallel fetch restart

On 2026-07-22 UTC, the single-worker run was stopped at:

- processed tickers: `996 / 6017`;
- successful tickers: `953`;
- failed tickers: `43`;
- latest partial batch: `batch_00990_01000.json`.

The runner was upgraded with `--max-workers` and restarted with:

```powershell
python scripts/pipeline/run_checkpointed_etl.py --universe data/universe/universe.json --limit all --batch-size 10 --max-workers 5 --fetch-only --skip-backtest
```

Validation before restart:

```powershell
python -m unittest tests.test_checkpointed_etl tests.test_pipeline tests.test_scaled_universe -v
```

Result: `19` ETL/scaling tests passed. The five-worker run resumed from existing checkpoints and completed the supported universe.

### Completed full-universe local run

Final local status on 2026-07-22 UTC:

- Raw checkpoint fetch processed: `6017 / 6017`.
- Raw checkpoint successes: `5802`.
- Raw checkpoint failures: `215`.
- Corrected merge/export published: `5799` stock detail artifacts and aggregate dashboard/features/signals artifacts.
- ETL report status: `partial_success` with `218` noncritical failures and zero critical pipeline-health failures.
- Forecast scaled-fast artifacts: `5799` records; `5475` conservative scenarios available, `321` insufficient-data scenarios, `3` stale scenarios.
- Largest deployable public artifacts after merge and dashboard trim: `public/data/dashboard.json` about `24 MB`, `public/data/signals.json` about `66 MB`, `public/data/features.json` about `54 MB`, and `public/data/etl_report.json` about `13 MB`.
- `public/data/dashboard.json` is now an intentional dashboard-summary artifact. Full per-ticker balance-sheet and price-history detail remains in `public/data/stocks/{TICKER}.json`, and official scoring components remain in `public/data/signals.json`.
- BM25 filing search remains capped at `199` indexed tickers. Scaling SEC filing/BM25 evidence for all `5799` stocks is a separate large ingestion job and was not completed by the market/companyfacts ETL merge.

Validation after the corrected merge:

```powershell
python scripts/audit_features.py
python scripts/audit_scoring.py
python -m unittest tests.test_forecast_pipeline -v
python scripts/forecast/run_forecast_pipeline.py --summary --scaled-fast
python scripts/forecast/audit_forecasts.py
python scripts/pipeline_health.py
python scripts/audit_search.py
npm run test:brief
npm run typecheck
npm run build
```

Results:

- Feature audit passed price ordering, annualization, and denominator-sign gates after the `scripts/cleaning.py` / `scripts/features.py` denominator fix.
- Scoring audit passed 0-100 bounds and deterministic sensitivity checks across `5799` records.
- Forecast audit passed for `5799` scaled-fast forecast files.
- Search audit passed structurally, but only for the current `199`-ticker BM25 corpus.
- Next.js type-check, production build, and brief UI tests passed.
- The post-trim dashboard validation passed `python -m unittest tests.test_pipeline tests.test_checkpointed_etl -v`, `python scripts/audit_features.py`, `python scripts/pipeline_health.py`, `npm run typecheck`, `npm run build`, and `npm run test:brief`.

Automation caution:

- `.github/workflows/refresh-data.yml` is still capped at `VS_UNIVERSE_LIMIT: "250"` for GitHub runner safety.
- Scheduled workflow runs now act as health checks and do not commit public artifacts; manual dispatch is required for the artifact commit step while the deployed dataset is full-universe.
- Do not remove this guard or let a capped scheduled refresh overwrite the `5799` artifact set until an incremental/full-run automation design exists.

---

## 29. Live Implementation Context - Growth Spurt Full Coverage and Batch-Aware BM25

**Updated:** 2026-07-23 UTC
**Git branch:** `scale-universe-foundation`
**Reason:** The scaled dashboard needed two cleanups before subscription/paywall work: Growth Spurt tags had to reflect all published stocks without noisy "No tag" cells, and BM25 filing evidence needed a resumable indexing path instead of a brittle monolithic rebuild.

### Growth Spurt coverage

Current generated dashboard/summary artifacts include a Growth Spurt record for every published stock:

- published stocks: `5799`;
- Growth Spurt detected: `357`;
- emerging upward trend: `746`;
- not detected: `4548`;
- unavailable: `148`;
- missing Growth Spurt stock artifacts: `0`.

Frontend behavior:

- `src/components/GrowthSpurtBadge.tsx` compact mode renders only `detected` and `emerging`.
- `not_detected` and `unavailable` compact cells intentionally render empty instead of "No tag".
- The stock-detail Recent Trend card still explains unavailable/not-detected states when the user opens the company page.
- `src/features/dashboard/StockTable.tsx` Growth filter now exposes only the actionable display tags: "Growth spurt detected" and "Emerging upward trend".

Guardrail: Growth Spurt remains display-only. It does not alter official ValueSignal scoring, confidence, or signal classification.

### Batch-aware BM25 filing index

Current BM25 layout:

- `public/data/search_index.json` remains a lightweight per-ticker manifest.
- Ticker corpora live under `public/data/search/{TICKER}.json`.
- The manifest is marked `batchAware: true`.
- Current coverage is `210` indexed tickers and `54272` SEC filing chunks.
- `50` no-searchable-filing gaps are logged in the manifest instead of being retried forever.
- Latest successful increment requested `25` tickers, indexed `10`, failed/logged `15`, and left `5757` supported universe rows unattempted.

New batch command:

```powershell
$env:VS_USER_AGENT="ValueSignal research ETL <contact-email>"
python scripts/build_search_index_batch.py --universe data/universe/universe.json --batch-size 25
```

Batch mechanics:

- Selects the next unattempted supported tickers from `data/universe/universe.json`.
- Skips both already indexed tickers and previously failed/no-searchable-filing tickers unless `--force` is passed.
- Writes per-ticker search files after each successful ticker, then updates the manifest so the run is resumable.
- Stores the batch report at `data/reports/search_index_batch_report.json`.
- Updates dashboard, ETL report, stock summary, and stock detail BM25 status flags from the manifest.
- Must not erase broader filing freshness fields such as `latestFilingDate`; those come from the SEC/companyfacts pipeline, not from BM25 coverage alone.

GitHub Actions change:

- `.github/workflows/refresh-data.yml` now uses `scripts/build_search_index_batch.py` with `VS_SEARCH_BATCH_SIZE`.
- This avoids rebuilding a monolithic search index during scheduled/dispatch refreshes.
- Scheduled artifact commits remain guarded; manual dispatch is still required to publish changed artifacts while the deployed dataset is full-universe.

Validation:

```powershell
python -m unittest tests.test_search_index_batch tests.test_artifact_paths tests.test_retrieval -v
npm run test:brief
npm run typecheck
python scripts/audit_search.py
```

Results:

- BM25 batch/retrieval tests passed: `22` Python tests.
- Brief/dashboard component tests passed: `32` TypeScript/TSX tests.
- Type-check passed.
- Search audit passed against the per-ticker manifest: `54272` chunks, `210` tickers, schema `3.0.0`, no metadata/citation failures.
- Local ACDC smoke searches now return cited passages for `risk analysis`, `supply chain`, `market risk`, and `liquidity`.

### Pre-Stripe checkpoint rule

Before implementing subscription billing, commit this BM25/Growth Spurt checkpoint first. Do not mix Stripe code, Stripe env placeholders, or subscription gating changes into the BM25 artifact commit.

---

## 30. Live Implementation Context - Stripe Billing and Pro Access Gate

**Updated:** 2026-07-23 UTC
**Git branch:** `scale-universe-foundation`
**Pre-Stripe checkpoint:** `40b40222 feat: add batch-aware BM25 growth checkpoint`
**Reason:** ValueSignal now needs a paid access layer after Google auth so the full scaled universe can be reserved for Pro users while still offering a limited signed-in preview.

### Access tiers

The current intended access model is:

```text
1. Signed out
   -> original 10-stock public preview only

2. Google signed-in free
   -> original preview
   -> up to 3 potentially-undervalued candidates
   -> up to 3 Growth Spurt/emerging candidates

3. ValueSignal Pro
   -> full 5,799-stock universe
   -> full stock-detail access
```

The full universe is no longer unlocked by Google sign-in alone. Google sign-in associates the user identity; Stripe/webhook-backed Pro entitlement unlocks the full universe.

### Stripe implementation boundary

The current code implements the app-side billing system only:

- no live Stripe resources were created;
- no live Stripe key was committed;
- no deployment was performed for the billing layer;
- the live secret key pasted in chat should be rotated before real use;
- test-mode Stripe Product/Price/Webhook setup must happen before production use.

Current Stripe documentation differences from the pasted blueprint:

- The app-side Stripe wrapper defaults to request-scoped `STRIPE_API_VERSION=2025-03-31.basil` for Managed Payments requests rather than the older blueprint preview header.
- The product tax code should be confirmed in the Stripe Dashboard/MCP before Product creation. Browser SaaS appears closer to `txcd_10103000` than an electronic-download tax code, but this is not hardcoded or created by the app code.

### Code modules

Billing routes:

- `src/app/billing/page.tsx`
- `src/app/billing/success/page.tsx`
- `src/app/billing/cancel/page.tsx`
- `src/app/api/billing/checkout/route.ts`
- `src/app/api/billing/subscription/route.ts`
- `src/app/api/billing/webhook/route.ts`

Billing/server modules:

- `src/lib/access-policy.ts` centralizes public/free/pro visibility.
- `src/lib/billing-policy.ts` centralizes subscription-status-to-Pro rules.
- `src/lib/billing-store.ts` creates/reads PostgreSQL subscription and processed-event tables.
- `src/lib/stripe-server.ts` creates server-controlled Stripe Checkout Sessions and customers through Stripe REST.
- `src/lib/stripe-signature.ts` verifies raw-body webhook signatures.
- `src/components/BillingPlans.tsx` starts monthly/yearly Checkout from the client without exposing Price IDs.

Database tables created at runtime, following the existing saved-data pattern:

- `user_subscription`
- `processed_stripe_event`

### Checkout and webhook policy

Checkout behavior:

- authenticated user is resolved server-side;
- unauthenticated requests are rejected;
- client cannot submit arbitrary Product IDs, Price IDs, user IDs, plan state, or entitlement state;
- monthly Price ID comes from `STRIPE_VALUE_SIGNAL_MONTHLY_PRICE_ID`;
- annual Price ID comes from `STRIPE_VALUE_SIGNAL_ANNUAL_PRICE_ID` and is disabled when absent;
- quantity is fixed at `1`;
- mode is `subscription`;
- normal Stripe Checkout is the default;
- Managed Payments is opt-in only when `STRIPE_ENABLE_MANAGED_PAYMENTS=true`;
- if Managed Payments is enabled, the exact live Stripe Product attached to the configured Price IDs must expose an eligible product-level `tax_code`;
- success URL returns to `/billing/success`;
- cancel URL returns to `/billing/cancel`;
- success page explicitly says webhook verification is required before access changes.

Webhook behavior:

- raw request body is used;
- Stripe signature is verified;
- duplicate event IDs are idempotently ignored via `processed_stripe_event`;
- handled events:
  - `checkout.session.completed`
  - `checkout.session.async_payment_succeeded`
  - `checkout.session.async_payment_failed`
  - `invoice.paid`
  - `invoice.payment_failed`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`

Subscription statuses:

- Pro access: `active`, `trialing`;
- Pro through paid period: `canceled` with future `currentPeriodEnd`;
- no Pro: `past_due`, `paused`, `unpaid`, `incomplete`, `incomplete_expired`, `none`.

### Environment variables

Use placeholders only in Git:

```text
STRIPE_SECRET_KEY=
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_VALUE_SIGNAL_PRODUCT_ID=
STRIPE_VALUE_SIGNAL_MONTHLY_PRICE_ID=
STRIPE_VALUE_SIGNAL_ANNUAL_PRICE_ID=
STRIPE_API_VERSION=2025-03-31.basil
NEXT_PUBLIC_APP_URL=
```

For local/test setup, use Stripe test-mode keys and price IDs first. Do not use the pasted live secret key. If a live key was exposed, rotate it in Stripe before production.

### Validation

Passed after the billing implementation:

```powershell
npm run test:billing
npm run test:brief
npm run typecheck
npm run build
```

Results:

- Billing/access/signature tests: `4` passed.
- Existing brief/dashboard/saved-position tests: `32` passed.
- Type-check passed.
- Production Next.js build passed and includes `/billing`, `/billing/success`, `/billing/cancel`, and the billing API routes.

### Current Stripe deployment notes

- Production deploy for the Stripe/Pro access gate is live on `https://value-signal.vercel.app`.
- Test-mode Stripe keys and webhook envs are configured in Vercel.
- Production smoke tests confirmed `/billing`, signed-out entitlement, signed-out checkout rejection, unsigned webhook rejection, and healthy auth debug configuration.
- User-facing dashboard copy now avoids `BS`; balance-sheet coverage is spelled out as `Balance sheet full`, `Balance sheet partial`, or `No balance sheet`.
- User-facing ETL status should say `Data pipeline succeeded` when more than 25% of requested tickers populate successfully. Raw audit artifacts may still use `partial_success` for strict lineage.

### Known next improvements

- Complete a full test subscription in-browser and verify webhook-granted Pro unlock with the signed-in user session.
- Add a Stripe billing portal / manage-subscription flow after checkout is stable.
- Consider updating the Neon `DATABASE_URL` SSL query from `sslmode=require` to `sslmode=verify-full` to silence the current Postgres driver warning.
- Rotate any live-mode Stripe key if it was ever exposed before enabling real payments.

### Live Stripe cutover guardrail

When switching from Stripe test mode to live mode, saved test-mode customer/subscription IDs must not be trusted as live records. Checkout now verifies any stored customer ID against the active Stripe key, finds or creates a customer in the active mode when needed, and tags subscription rows with `stripeLivemode`. Entitlement checks only grant Pro when the stored subscription row matches the current Stripe mode.

---

## 31. Live Implementation Context - Scheduled Batch ETL Publishing

**Updated:** 2026-07-30 America/Chicago
**Git branch:** `scale-universe-foundation`
**Reason:** The deployed dashboard reported old committed data even though GitHub Actions scheduled runs were green.

### Root cause

The hosted workflow `.github/workflows/refresh-data.yml` was still running on schedule, and recent scheduled runs were successful. The problem was operational, not provider failure:

- the workflow refreshed a capped ETL slice for health checking;
- the scheduled path intentionally skipped artifact commits to avoid overwriting the 5,799-company deployed dataset with a 250-company output;
- therefore the bot could show green runs while `public/data/*.json` remained old.

### New scheduled behavior

The cron time remains unchanged:

```yaml
cron: "25 23 * * 1-5"
```

The workflow now builds the full SEC-listed universe file, refreshes a bounded ETL batch, merges that batch into the existing published full-universe artifacts, recomputes global feature percentiles and official scores, then commits the changed artifacts on both scheduled and manual runs.

New module:

```powershell
python scripts/pipeline/refresh_public_batch.py --universe data/universe/universe.json --batch-size 250 --batch-count 4 --skip-backtest
```

Safety mechanics:

- `public/data/dashboard.json` keeps the full published universe instead of shrinking to the batch.
- `public/data/features.json` replaces only refreshed raw feature rows, then re-normalizes all published rows.
- `public/data/signals.json` is regenerated from the merged, globally normalized feature set.
- refreshed stock detail files replace only the tickers in the current batch.
- `data/reports/scheduled_etl_batch_state.json` tracks the next universe offset so weekday runs progress through the universe in resumable batches.
- forecast publication uses `python scripts/forecast/run_forecast_pipeline.py --summary --scaled-fast` because the published dataset remains full-universe scale even when only one ETL batch is refreshed.
- `git pull --rebase` runs before the bot push to reduce GitHub-side race failures.

### Current hosted rotation policy

As of 2026-07-30, the hosted GitHub Action still runs at the original weekday cron time:

```yaml
cron: "25 23 * * 1-5"
```

The schedule now refreshes four consecutive 250-company ETL chunks per run, for a maximum of 1,000 active universe rows per weekday run. This keeps each bot run bounded for GitHub Actions while advancing through the full SEC-listed universe in roughly seven business-day runs. Manual dispatch can still override `etl_batch_size` and `etl_batch_count`.

The latest batch report may say, for example, `246 / 250 companies refreshed; 4 failed`. That is not the deployed universe size. It means the most recent bounded GitHub batch refreshed 246 rows and logged four ticker-level provider failures. The public artifacts remain full-universe merged artifacts, and `public/data/etl_report.json` exposes:

- `publicationMode: "incremental_batch_merge"`;
- `fullUniversePublishedTickers`, the number of companies currently present in public dashboard artifacts;
- `batchState.universeSize`, the active universe row count;
- `batchState.nextOffset`, the next cursor position for the following scheduled run.

### User-facing stale-data display

`src/features/dashboard/DataStatus.tsx` no longer promotes age over pipeline health. If more than 25 percent of the requested tickers were populated, the status headline says `Data pipeline succeeded`; the latest-batch success/failure counts, full published universe count, rotation checkpoint, batch configuration, and last run time remain visible in the body copy. Older artifact age is now a plain explanatory note instead of a `Stale data` screen.

### Validation

Passed on 2026-07-30 America/Chicago:

```powershell
python scripts/pipeline/refresh_public_batch.py --universe data/universe/universe.json --batch-size 3 --batch-count 4 --dry-run
python -m unittest tests.test_scheduled_batch_refresh tests.test_pipeline_health -v
python -m unittest discover -s tests -p "test_*.py" -v
python scripts/pipeline_health.py
npm run test:brief
npm run typecheck
npm run build
```

Results:

- scheduled batch selection dry-run selected the first twelve supported tickers and preserved a 6,017-supported-row universe;
- targeted scheduled-batch and pipeline-health tests passed;
- full Python suite passed 115 tests;
- pipeline health reported zero critical failures;
- existing frontend brief/dashboard/saved-position tests passed 32 tests;
- TypeScript type-check and production build passed.
