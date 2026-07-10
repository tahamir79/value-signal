from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from rag.config import RagConfig
from rag.hybrid_retriever import retrieve
from rag.intent import RISK_OUTLOOK_INTENT, detect_intent, deterministic_risk_posture, intent_retrieval_queries
from rag.prompt_builder import build_prompt
from rag.stock_context import build_stock_context, extract_evidence_assessment, extract_named_field, normalize_evidence_relevance, normalize_signal_relationship
from rag.synthesize import synthesize_answer
from rag.synthesis_profile import profile_for
from scripts.retrieval import diversify_results


def _merge_evidence(results: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for row in results:
        key = str(row.get("chunkId") or row.get("id"))
        if key not in by_id or float(row.get("score", 0)) > float(by_id[key].get("score", 0)):
            by_id[key] = row
    ranked = sorted(by_id.values(), key=lambda row: (-float(row.get("score", 0)), str(row.get("chunkId") or row.get("id"))))
    return diversify_results(ranked, limit)


RISK_OUTLOOK_PREFACE = (
    "I cannot predict whether the stock will go up or down, but I can assess whether "
    "the current signal and retrieved risk evidence support, weaken, or complicate the research case."
)


def _enforce_risk_outlook_safety(answer: str | None, intent: str) -> str | None:
    if not answer or intent != RISK_OUTLOOK_INTENT:
        return answer
    if "cannot predict whether the stock will go up or down" in answer.lower():
        return answer
    return f"Risk-Based Assessment:\n{RISK_OUTLOOK_PREFACE}\n\n{answer}"


def _guard_signal_relationship(intent: str, relationship: str, signal_label: str | None, answer: str | None) -> str:
    """Prevent the LLM from over-connecting thematic evidence to the official signal.

    A cybersecurity governance excerpt can be directly relevant to the user's question
    while still only indirectly related to a deterministic signal such as momentum risk.
    The official signal remains pipeline-owned; this guard only normalizes the local
    RAG interpretation field.
    """
    if relationship not in {"Supports signal", "Weakens signal"}:
        return relationship
    if intent in {RISK_OUTLOOK_INTENT, "general"}:
        return relationship
    signal = (signal_label or "").lower()
    if not signal:
        return "Indirect relationship"
    answer_text = (answer or "").lower()
    signal_terms = {term for term in signal.replace("-", " ").split() if len(term) >= 5}
    if signal_terms and all(term in answer_text for term in signal_terms):
        return relationship
    return "Indirect relationship"

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
            synthesis_depth: str | None = None, session_summary: str | None = None,
            *, index: dict[str, Any] | None = None,
            embedding_search: Callable[..., list[dict[str, Any]]] | None = None,
            generator: Callable[[str], str] | None = None) -> dict[str, Any]:
    if not query.strip(): raise ValueError("query must not be empty")
    ticker = ticker.upper() if ticker else None
    intent = detect_intent(query)
    profile = profile_for(synthesis_depth, query)
    effective_top_k = max(top_k, profile.top_k)
    warnings: list[str] = []
    effective_modes: list[str] = []
    if intent != "general":
        gathered: list[dict[str, Any]] = []
        for retrieval_kind, retrieval_query in intent_retrieval_queries(query, intent):
            rows, row_warnings, mode = retrieve(retrieval_query, ticker=ticker, form_type=form_type,
                                                mode=retrieval_mode, top_k=max(effective_top_k, 4), index=index,
                                                embedding_search=embedding_search)
            for row in rows:
                row["retrievalIntent"] = retrieval_kind
            gathered.extend(rows)
            warnings.extend(row_warnings)
            effective_modes.append(mode)
        chunks = _merge_evidence(gathered, max(effective_top_k, 5))
        effective_mode = "+".join(sorted(set(effective_modes))) if effective_modes else retrieval_mode
    else:
        chunks, warnings, effective_mode = retrieve(query, ticker=ticker, form_type=form_type,
                                                    mode=retrieval_mode, top_k=effective_top_k, index=index,
                                                    embedding_search=embedding_search)
    ids = [str(row.get("chunkId") or row.get("id")) for row in chunks]
    stock_context = build_stock_context(ticker)
    company, signal = _signal_context(ticker)
    company = company or (stock_context or {}).get("companyName")
    signal_label = (stock_context or {}).get("officialSignalLabel") or signal
    answer = None
    limitations = None
    evidence_assessment = "Insufficient evidence"
    evidence_relevance = "Insufficient evidence"
    signal_relationship = "Not enough evidence to connect to signal"
    if not chunks:
        limitations = "No relevant SEC filing evidence was retrieved; the evidence is insufficient."
    elif synthesize:
        config = RagConfig.from_env()
        prompt = build_prompt(query, chunks, ticker=ticker, company_name=company or chunks[0].get("companyName"),
                              primary_signal=signal_label, stock_context=stock_context,
                              intent=intent, synthesis_depth=profile.name,
                              session_summary=session_summary,
                              max_context_chars=profile.max_context_chars or config.max_context_chars)
        try:
            answer, synthesis_warnings = synthesize_answer(prompt, set(ids), generator, profile.max_output_tokens)
            answer = _enforce_risk_outlook_safety(answer, intent)
            warnings.extend(synthesis_warnings)
            evidence_assessment = extract_evidence_assessment(answer)
            evidence_relevance = normalize_evidence_relevance(extract_named_field(answer, {"Evidence Relevance"}))
            signal_relationship = normalize_signal_relationship(extract_named_field(answer, {"Signal Relationship", "Impact on Current Signal", "Evidence Assessment"}))
            signal_relationship = _guard_signal_relationship(intent, signal_relationship, signal_label, answer)
        except Exception as exc:
            warnings.append(str(exc))
            limitations = "Local synthesis is unavailable. Retrieved evidence is provided without interpretation."
    elif chunks:
        evidence_assessment = "Insufficient evidence"
    return {"query": query, "ticker": ticker, "retrieval_mode": effective_mode,
            "intent": intent,
            "synthesis_depth": profile.name,
            "retrieved_chunks": chunks, "answer": answer, "citations": ids,
            "stock_context": stock_context, "official_signal": (stock_context or {}).get("officialSignal"),
            "official_signal_label": (stock_context or {}).get("officialSignalLabel") or signal_label,
            "signal_confidence": (stock_context or {}).get("confidence"),
            "evidence_assessment": evidence_assessment,
            "evidence_relevance": evidence_relevance,
            "signal_relationship": signal_relationship,
            "deterministic_risk_posture": deterministic_risk_posture(stock_context),
            "limitations": limitations, "warnings": warnings}
