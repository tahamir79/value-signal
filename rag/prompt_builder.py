from __future__ import annotations

import os
from typing import Any

from rag.intent import RISK_OUTLOOK_INTENT
from rag.stock_context import EVIDENCE_ASSESSMENTS, EVIDENCE_RELEVANCE_VALUES, SIGNAL_RELATIONSHIP_VALUES, stock_context_summary
from rag.synthesis_profile import DEEP_MODE

SYSTEM_PROMPT = """You are a cautious financial research assistant.

Use only the retrieved SEC filing evidence provided below and the compact pipeline context. Do not use outside knowledge or invent facts.
Do not give buy, sell, or hold advice and do not predict stock prices. Cite chunk IDs for every major claim.
If evidence is weak or incomplete, say it is insufficient. Separate evidence from interpretation and use cautious language.
Use the pipeline context as background only. Do not restate UI-visible scores, raw features, or latest facts unless they directly answer the question.

Explain whether the evidence supports, weakens, or complicates the research signal. Do not relabel it.

The deterministic scoring pipeline assigns the official signal. You may say the signal should be reviewed when cited evidence strongly contradicts it, but you must not assign a new official signal or overwrite it.

Evidence Assessment must be exactly one of:
""" + "\n".join(f"- {value}" for value in sorted(EVIDENCE_ASSESSMENTS)) + """

Required structure:
Short Synthesis:
Key Caveat:
Citations:"""

DEEP_RESEARCH_PROMPT = """You are a cautious financial research assistant.

Use only the retrieved public-company evidence and provided scoring context.
Do not use outside knowledge.
Do not invent facts.
Do not give buy, sell, or hold advice.
Do not predict stock prices.
Cite chunk IDs for every major claim.
Separate evidence from interpretation.
If evidence is missing, say what is missing.
Use the pipeline context as background, not answer content.
Do not list component scores, raw features, derived fields, or latest facts unless the user specifically asks for raw data or a debug trace.
Spend most of the answer on what the retrieved evidence adds, weakens, complicates, or leaves unresolved.
Summarize SEC evidence briefly, then synthesize implications.

The official signal comes from a deterministic scoring pipeline. Do not overwrite it.
Your job is to answer the user's specific research question first, then explain whether the retrieved evidence supports, weakens, complicates, or is only indirectly related to the signal.

Evidence Relevance must be exactly one of:
""" + "\n".join(f"- {value}" for value in sorted(EVIDENCE_RELEVANCE_VALUES)) + """

Signal Relationship must be exactly one of:
""" + "\n".join(f"- {value}" for value in sorted(SIGNAL_RELATIONSHIP_VALUES)) + """

Required structure:
Brief Answer:
Evidence Relevance:
What the SEC Evidence Adds:
What This Changes or Complicates:
Signal Relationship:
Missing Evidence:
What To Research Next:
Citations:"""

RISK_OUTLOOK_STRUCTURE = """This is a risk-based outlook question. Do not answer it as a price prediction.

You must say: "I cannot predict whether the stock will go up or down, but I can assess whether the current signal and retrieved risk evidence support, weaken, or complicate the research case."

If retrieved filing evidence is weak, say: "The retrieved filing evidence is insufficient to assess price direction, but the deterministic risk/scoring data suggests the case is supportive/mixed/elevated risk/insufficient."

Required structure:
Risk-Based Assessment:
What Supports the Research Case:
What Weakens the Research Case:
Evidence Assessment:
What Would Need More Research:
Citations:"""


def _compact_header(query: str, intent: str, synthesis_depth: str, ticker: str | None,
                    company_name: str | None, primary_signal: str | None,
                    structured_context: str, session_block: str) -> str:
    return (
        "You are a cautious financial research assistant. Use only retrieved SEC evidence and compact pipeline context. "
        "Do not give buy/sell/hold advice or price predictions. Cite chunk IDs. "
        "Use pipeline context as background; do not restate UI-visible scores or raw data unless directly needed.\n\n"
        "Required structure:\n"
        "Brief Answer:\n"
        "Evidence Relevance:\n"
        "What the SEC Evidence Adds:\n"
        "What This Changes or Complicates:\n"
        "Signal Relationship:\n"
        "Missing Evidence:\n"
        "What To Research Next:\n"
        "Citations:\n\n"
        f"Question: {query}\nIntent: {intent}\nDepth: {synthesis_depth}\n"
        f"Ticker: {ticker or 'Not specified'}\nCompany: {company_name or 'Not available'}\n"
        f"Primary signal: {primary_signal or 'Not available'}\n"
        f"{session_block}\n{structured_context}\n\nRetrieved SEC filing evidence:\n"
    )


def build_prompt(query: str, chunks: list[dict[str, Any]], *, ticker: str | None = None,
                 company_name: str | None = None, primary_signal: str | None = None,
                 stock_context: dict[str, Any] | None = None, intent: str = "general",
                 synthesis_depth: str = DEEP_MODE, session_summary: str | None = None,
                 max_context_chars: int | None = None) -> str:
    limit = max_context_chars or int(os.getenv("RAG_MAX_CONTEXT_CHARS", "6000"))
    wants_full_context = any(term in query.lower() for term in ("raw data", "raw feature", "latest fact", "debug", "trace", "component score"))
    structured_context = stock_context_summary(stock_context, detail="full" if wants_full_context else "compact")
    intent_rules = f"\n\n{RISK_OUTLOOK_STRUCTURE}" if intent == RISK_OUTLOOK_INTENT else ""
    base_prompt = DEEP_RESEARCH_PROMPT if synthesis_depth == DEEP_MODE else SYSTEM_PROMPT
    session_block = f"\n\nResearch Session Summary:\n{session_summary.strip()}\n" if session_summary and session_summary.strip() else ""
    header = f"{base_prompt}{intent_rules}\n\nQuestion: {query}\nIntent: {intent}\nDepth: {synthesis_depth}\nTicker: {ticker or 'Not specified'}\nCompany: {company_name or 'Not available'}\nPrimary signal: {primary_signal or 'Not available'}\n{session_block}\n{structured_context}\n\nRetrieved SEC filing evidence:\n"
    if len(header) > max(0, limit - 300):
        header = _compact_header(query, intent, synthesis_depth, ticker, company_name, primary_signal, structured_context, session_block)
    available = max(0, limit - len(header))
    blocks: list[str] = []
    for row in chunks:
        block = (f"[Chunk ID: {row.get('chunkId') or row.get('id')}]\n"
                 f"Ticker: {row.get('ticker', ticker or 'Unknown')}\n"
                 f"Company: {row.get('companyName', company_name or 'Unknown')}\n"
                 f"Filing: {row.get('formType') or row.get('form', 'Unknown')}\n"
                 f"Date: {row.get('filingDate', 'Unknown')}\n"
                 f"Section: {row.get('sectionKey') or row.get('item', 'Unclassified')}"
                 f" — {row.get('sectionTitle') or 'Title unavailable'}\n"
                 f"Source: {row.get('sourceUrl') or row.get('url', 'Unknown')}\nText:\n{row.get('text', '')}\n")
        if len(block) > available:
            if not blocks and available > 100:
                blocks.append(block[:available])
            break
        blocks.append(block); available -= len(block)
    prompt = header + "\n".join(blocks)
    return prompt[:limit] if len(prompt) > limit else prompt
