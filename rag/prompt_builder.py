from __future__ import annotations

import os
from typing import Any

from rag.intent import RISK_OUTLOOK_INTENT
from rag.stock_context import EVIDENCE_ASSESSMENTS, stock_context_summary

SYSTEM_PROMPT = """You are a cautious financial research assistant.

Use only the retrieved SEC filing evidence provided below. Do not use outside knowledge or invent facts.
Do not give buy, sell, or hold advice and do not predict stock prices. Cite chunk IDs for every major claim.
If evidence is weak or incomplete, say it is insufficient. Separate evidence from interpretation and use cautious language.

Explain whether the evidence supports, weakens, or complicates the research signal. Do not relabel it.

The deterministic scoring pipeline assigns the official signal. You may say the signal should be reviewed when cited evidence strongly contradicts it, but you must not assign a new official signal or overwrite it.

Evidence Assessment must be exactly one of:
""" + "\n".join(f"- {value}" for value in sorted(EVIDENCE_ASSESSMENTS)) + """

Required structure:
Deterministic Signal:
Evidence Assessment:
Retrieved SEC Evidence:
RAG Interpretation:
Limitations and Missing Evidence:
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


def build_prompt(query: str, chunks: list[dict[str, Any]], *, ticker: str | None = None,
                 company_name: str | None = None, primary_signal: str | None = None,
                 stock_context: dict[str, Any] | None = None, intent: str = "general",
                 max_context_chars: int | None = None) -> str:
    limit = max_context_chars or int(os.getenv("RAG_MAX_CONTEXT_CHARS", "6000"))
    structured_context = stock_context_summary(stock_context)
    intent_rules = f"\n\n{RISK_OUTLOOK_STRUCTURE}" if intent == RISK_OUTLOOK_INTENT else ""
    header = f"{SYSTEM_PROMPT}{intent_rules}\n\nQuestion: {query}\nIntent: {intent}\nTicker: {ticker or 'Not specified'}\nCompany: {company_name or 'Not available'}\nPrimary signal: {primary_signal or 'Not available'}\n\n{structured_context}\n\nRetrieved SEC filing evidence:\n"
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
    return header + "\n".join(blocks)
