from __future__ import annotations

import hashlib
import re
from typing import Any

from scripts.providers.sec_filings import FilingDocument

ITEM_PATTERN = re.compile(r"(?im)^\s*(item\s+(?:\d+[a-z]?|[ivx]+)[\.:]?\s*[^\n]{0,100})$")


def _sections(text: str) -> list[tuple[str, str]]:
    matches = list(ITEM_PATTERN.finditer(text))
    if not matches:
        return [("Full filing", text)]
    sections = []
    if matches[0].start() > 0:
        sections.append(("Front matter", text[:matches[0].start()]))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group(1).strip(), text[match.end():end]))
    return sections


def chunk_filing(document: FilingDocument, clean_text: str, target_words: int = 220, overlap_words: int = 40, minimum_words: int = 35) -> list[dict[str, Any]]:
    chunks = []
    step = max(1, target_words - overlap_words)
    for item, section in _sections(clean_text):
        words = section.split()
        for start in range(0, len(words), step):
            window = words[start:start + target_words]
            if len(window) < minimum_words:
                continue
            identity = f"{document.accession}:{item}:{start}"
            chunks.append({
                "id": hashlib.sha1(identity.encode("utf-8")).hexdigest()[:16], "ticker": document.ticker,
                "accession": document.accession, "filingDate": document.filing_date, "reportDate": document.report_date,
                "form": document.form, "item": item, "url": document.url, "text": " ".join(window),
                "wordStart": start, "wordEnd": start + len(window),
            })
            if start + target_words >= len(words):
                break
    return chunks
