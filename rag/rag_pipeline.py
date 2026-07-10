from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from rag.config import RagConfig
from rag.hybrid_retriever import retrieve
from rag.prompt_builder import build_prompt
from rag.stock_context import build_stock_context, extract_evidence_assessment
from rag.synthesize import synthesize_answer

def _signal_context(ticker: str | None, path: Path = Path("public/data/signals.json")) -> tuple[str | None, str | None]:
    if not ticker or not path.exists(): return None, None
    try: payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return None, None
    rows = payload.get("records") or payload.get("signals") or []
    for row in rows:
        if str(row.get("ticker") or row.get("security", {}).get("ticker", "")).upper() == ticker.upper():
            signal = row.get("primarySignal") or row.get("primary_signal") or row.get("label") or row.get("signal")
            return (row.get("companyName") or row.get("security", {}).get("company_name"), signal)
    return None, None


def run_rag(query: str, ticker: str | None = None, form_type: str | None = None,
            retrieval_mode: str = "hybrid", top_k: int = 3, synthesize: bool = True,
            *, index: dict[str, Any] | None = None,
            embedding_search: Callable[..., list[dict[str, Any]]] | None = None,
            generator: Callable[[str], str] | None = None) -> dict[str, Any]:
    if not query.strip(): raise ValueError("query must not be empty")
    ticker = ticker.upper() if ticker else None
    chunks, warnings, effective_mode = retrieve(query, ticker=ticker, form_type=form_type,
                                                 mode=retrieval_mode, top_k=top_k, index=index,
                                                 embedding_search=embedding_search)
    ids = [str(row.get("chunkId") or row.get("id")) for row in chunks]
    stock_context = build_stock_context(ticker)
    company, signal = _signal_context(ticker)
    company = company or (stock_context or {}).get("companyName")
    signal_label = (stock_context or {}).get("officialSignalLabel") or signal
    answer = None
    limitations = None
    evidence_assessment = "Insufficient evidence"
    if not chunks:
        limitations = "No relevant SEC filing evidence was retrieved; the evidence is insufficient."
    elif synthesize:
        config = RagConfig.from_env()
        prompt = build_prompt(query, chunks, ticker=ticker, company_name=company or chunks[0].get("companyName"),
                              primary_signal=signal_label, stock_context=stock_context,
                              max_context_chars=config.max_context_chars)
        try:
            answer, synthesis_warnings = synthesize_answer(prompt, set(ids), generator)
            warnings.extend(synthesis_warnings)
            evidence_assessment = extract_evidence_assessment(answer)
        except Exception as exc:
            warnings.append(str(exc))
            limitations = "Local synthesis is unavailable. Retrieved evidence is provided without interpretation."
    elif chunks:
        evidence_assessment = "Insufficient evidence"
    return {"query": query, "ticker": ticker, "retrieval_mode": effective_mode,
            "retrieved_chunks": chunks, "answer": answer, "citations": ids,
            "stock_context": stock_context, "official_signal": (stock_context or {}).get("officialSignal"),
            "official_signal_label": (stock_context or {}).get("officialSignalLabel") or signal_label,
            "signal_confidence": (stock_context or {}).get("confidence"),
            "evidence_assessment": evidence_assessment,
            "limitations": limitations, "warnings": warnings}
