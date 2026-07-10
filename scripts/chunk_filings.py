from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from scripts.providers.sec_filings import FilingDocument

SCHEMA_VERSION = "3.0.0"
PART_RE = re.compile(r"(?i)^part\s+([ivx]+)\b")
ITEM_RE = re.compile(r"(?i)^item\s+(\d+[a-z]?|[ivx]+)\s*[.:-]?\s*(.*)$")
TERMINAL_RE = re.compile(r"(?i)^(?:signatures?|exhibit\s+index)\b")
SENTENCE_RE = re.compile(r".*?(?:[.!?](?=\s|$)|$)", re.S)
WORD_RE = re.compile(r"\S+")
STRUCTURAL_BODY_RE = re.compile(r"(?im)^(?:part|item|signatures?)\b")


@dataclass
class Section:
    part: str | None
    number: str
    title: str | None
    heading: str
    text: str
    char_start: int
    paragraph_start: int
    preamble: bool = False

    @property
    def key(self) -> str:
        if self.preamble:
            return "preamble:forward-looking-statements"
        part = f"part-{self.part.lower()}:" if self.part else ""
        return f"{part}item-{self.number.lower()}"


TEN_K_PARTS = {
    "1": "i", "1a": "i", "1b": "i", "1c": "i", "2": "i", "3": "i", "4": "i",
    "5": "ii", "6": "ii", "7": "ii", "7a": "ii", "8": "ii", "9": "ii", "9a": "ii",
    "9b": "ii", "9c": "ii", "10": "iii", "11": "iii", "12": "iii", "13": "iii",
    "14": "iii", "15": "iv", "16": "iv",
}
TEN_Q_ITEMS = {"i": {"1", "2", "3", "4"}, "ii": {"1", "1a", "2", "3", "4", "5", "6"}}


def _canonical_part(form_type: str, number: str, detected: str | None) -> str | None:
    number = number.lower()
    if form_type.upper() == "10-K":
        return TEN_K_PARTS.get(number)
    if form_type.upper() == "10-Q":
        return detected if detected in TEN_Q_ITEMS and number in TEN_Q_ITEMS[detected] else None
    return detected


def _sections(text: str, form_type: str = "") -> list[Section]:
    # Clean HTML uses blank lines, while plain-text filings and fixtures often
    # place headings and body paragraphs on consecutive single-newline lines.
    paragraph_matches = list(re.finditer(r"[^\r\n]+", text))
    paragraphs = [match.group(0).strip() for match in paragraph_matches]
    starts = [match.start() + len(match.group(0)) - len(match.group(0).lstrip()) for match in paragraph_matches]
    part: str | None = None
    part_positions: list[int] = []
    terminal_positions: list[int] = []
    structural_positions: list[int] = []
    headings: list[tuple[int, str | None, re.Match[str]]] = []
    for index, paragraph in enumerate(paragraphs):
        if TERMINAL_RE.match(paragraph.strip()):
            terminal_positions.append(index)
        part_match = PART_RE.match(paragraph)
        if part_match and len(paragraph.split()) <= 12:
            part = part_match.group(1).lower()
            part_positions.append(index)
            structural_positions.append(index)
            continue
        item_match = ITEM_RE.match(paragraph)
        if item_match:
            structural_positions.append(index)
        if item_match and len(paragraph.split()) <= 24:
            canonical_part = _canonical_part(form_type, item_match.group(1), part)
            if canonical_part is not None:
                headings.append((index, canonical_part, item_match))

    # The last Part I / Item 1 occurrence is the deterministic body anchor.
    # Earlier occurrences are normally navigation tables whose links can make
    # tiny TOC headings appear to own most of the document.
    anchors = [index for index, heading_part, match in headings
               if heading_part == "i" and match.group(1).lower() == "1"]
    body_anchor = max(anchors) if anchors else 0
    structural_end = min([index for index in terminal_positions if index > body_anchor] or [len(paragraphs)])
    headings = [row for row in headings if body_anchor <= row[0] < structural_end]

    candidates: list[Section] = []
    preambles: list[Section] = []
    for index, paragraph in enumerate(paragraphs[:body_anchor]):
        if "forward-looking statement" not in paragraph.lower() or len(paragraph.split()) > 12:
            continue
        end = min([boundary for boundary in structural_positions
                   if index < boundary <= body_anchor] or [body_anchor])
        body_start = starts[index + 1] if index + 1 < len(starts) else len(text)
        body_char_end = starts[end] if end < len(starts) else len(text)
        raw_body = text[body_start:body_char_end]
        leading = len(raw_body) - len(raw_body.lstrip())
        body = raw_body.strip()
        if 100 <= len(body.split()) <= 5000 and not STRUCTURAL_BODY_RE.search(body):
            preambles.append(Section(None, "forward-looking-statements", "Forward-Looking Statements",
                                     paragraph, body, body_start + leading, index + 1, True))
    if preambles:
        candidates.append(max(preambles, key=lambda section: section.char_start))
    for pos, (index, heading_part, match) in enumerate(headings):
        end = min([boundary for boundary in structural_positions if index < boundary <= structural_end]
                  or [structural_end])
        end = min([boundary for boundary in part_positions if index < boundary < end] or [end])
        body_start = starts[index + 1] if index + 1 < len(starts) else len(text)
        body_char_end = starts[end] if end < len(starts) else len(text)
        raw_body = text[body_start:body_char_end]
        leading = len(raw_body) - len(raw_body.lstrip())
        body = raw_body.strip()
        candidates.append(Section(heading_part, match.group(1), match.group(2).strip() or None,
                                  paragraphs[index], body, body_start + leading, index + 1))

    # TOCs repeat headings with little or no prose. For each canonical section,
    # retain the densest occurrence; ties deterministically prefer the later body.
    best: dict[str, Section] = {}
    for section in candidates:
        current = best.get(section.key)
        density = len(section.text.split())
        if current is None or (density, section.char_start) >= (len(current.text.split()), current.char_start):
            best[section.key] = section
    return sorted(best.values(), key=lambda section: section.char_start)


def _sentences(paragraph: str) -> list[str]:
    return [match.group(0).strip() for match in SENTENCE_RE.finditer(paragraph) if match.group(0).strip()]


def _units(section: Section, maximum: int) -> list[dict[str, Any]]:
    units: list[dict[str, Any]] = []
    paragraphs = list(re.finditer(r"[^\r\n]+", section.text))
    for p_index, paragraph_match in enumerate(paragraphs):
        paragraph = paragraph_match.group(0).strip()
        paragraph_start = paragraph_match.start() + len(paragraph_match.group(0)) - len(paragraph_match.group(0).lstrip())
        words = paragraph.split()
        if len(words) <= maximum:
            units.append({"text": paragraph, "p": p_index, "s0": 0, "s1": max(0, len(_sentences(paragraph)) - 1), "boundary": "paragraph", "c0": paragraph_start, "c1": paragraph_start + len(paragraph)})
            continue
        sentences = [match for match in SENTENCE_RE.finditer(paragraph) if match.group(0).strip()]
        for s_index, sentence_match in enumerate(sentences):
            sentence = sentence_match.group(0).strip()
            sentence_start = paragraph_start + sentence_match.start() + len(sentence_match.group(0)) - len(sentence_match.group(0).lstrip())
            sentence_words = sentence.split()
            if len(sentence_words) <= maximum:
                units.append({"text": sentence, "p": p_index, "s0": s_index, "s1": s_index, "boundary": "sentence_split", "c0": sentence_start, "c1": sentence_start + len(sentence)})
            else:
                word_matches = list(WORD_RE.finditer(sentence))
                for start in range(0, len(word_matches), 260):
                    window = word_matches[start:start + 300]
                    c0, c1 = sentence_start + window[0].start(), sentence_start + window[-1].end()
                    units.append({"text": section.text[c0:c1], "p": p_index, "s0": s_index, "s1": s_index, "boundary": "fixed_window_fallback", "c0": c0, "c1": c1})
                    if start + 300 >= len(sentence_words):
                        break
    return units


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _sentence_overlap(unit: dict[str, Any], section: Section, cap: int) -> dict[str, Any] | None:
    """Return exactly the final sentence of a unit when it fits the overlap cap."""
    text = section.text[unit["c0"]:unit["c1"]]
    matches = [match for match in SENTENCE_RE.finditer(text) if match.group(0).strip()]
    if not matches:
        return None
    match = matches[-1]
    sentence = match.group(0).strip()
    if not sentence or len(sentence.split()) > cap:
        return None
    leading = len(match.group(0)) - len(match.group(0).lstrip())
    c0 = unit["c0"] + match.start() + leading
    return {"text": sentence, "p": unit["p"], "s0": unit["s1"], "s1": unit["s1"],
            "boundary": "sentence_split", "c0": c0, "c1": c0 + len(sentence), "overlap": True}


def chunk_filing(document: FilingDocument, clean_text: str, target_words: int = 300,
                 overlap_words: int = 60, minimum_words: int = 35, maximum_words: int | None = None) -> list[dict[str, Any]]:
    overlap_cap = min(60, max(0, overlap_words))
    maximum_words = maximum_words or min(450, max(target_words + 40, int(target_words * 1.5)))
    chunks: list[dict[str, Any]] = []
    document_word_starts = [match.start() for match in WORD_RE.finditer(clean_text)]
    for section in _sections(clean_text, document.form):
        if not section.text or _normalize(section.text) in {"reserved", "[reserved]"}:
            continue
        section_words = len(section.text.split())
        if section.preamble and (section_words > 5000 or STRUCTURAL_BODY_RE.search(section.text)):
            continue
        if section.key == "part-iv:item-16" and section_words > 2000:
            continue
        units = _units(section, maximum_words)
        groups: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        for unit in units:
            if current and sum(len(row["text"].split()) for row in current) + len(unit["text"].split()) > maximum_words:
                groups.append(current)
                overlap = _sentence_overlap(current[-1], section, overlap_cap) if overlap_cap else None
                current = [overlap] if overlap else []
            current.append(unit)
            if sum(len(row["text"].split()) for row in current) >= target_words:
                groups.append(current)
                overlap = _sentence_overlap(current[-1], section, overlap_cap) if overlap_cap else None
                current = [overlap] if overlap else []
        if current and (not groups or current != groups[-1]):
            if groups and sum(len(row["text"].split()) for row in current) < minimum_words and sum(len(row["text"].split()) for row in groups[-1] + current) <= maximum_words:
                groups[-1].extend(current[1:] if groups[-1][-1] is current[0] else current)
                groups[-1][0]["merged"] = True
            else:
                groups.append(current)

        section_word_starts = [match.start() for match in WORD_RE.finditer(section.text)]
        for sequence, group in enumerate(groups):
            relative_char = group[0]["c0"]
            relative_end = group[-1]["c1"]
            content = section.text[max(0, relative_char):max(0, relative_end)]
            if not content.strip():
                continue
            doc_char_start = section.char_start + max(0, relative_char)
            doc_char_end = section.char_start + max(0, relative_end)
            doc_word_start = sum(1 for start in document_word_starts if start < doc_char_start)
            doc_word_end = sum(1 for start in document_word_starts if start < doc_char_end)
            word_count = len(content.split())
            section_word_start = sum(1 for start in section_word_starts if start < max(0, relative_char))
            section_word_end = sum(1 for start in section_word_starts if start < max(0, relative_end))
            boundary = "short_section" if len(section.text.split()) < minimum_words else group[0]["boundary"]
            if group[0].get("merged"):
                boundary = "merged_tail"
            digest = hashlib.sha256(_normalize(content).encode()).hexdigest()[:16]
            chunk_id = hashlib.sha256(f"{document.accession}:{section.key}:{digest}".encode()).hexdigest()[:24]
            chunks.append({
                "schemaVersion": SCHEMA_VERSION, "id": chunk_id, "chunkId": chunk_id,
                "ticker": document.ticker, "companyName": document.ticker, "cik": document.cik or None,
                "formType": document.form, "form": document.form, "filingDate": document.filing_date,
                "reportDate": document.report_date, "accession": document.accession,
                "primaryDocument": document.primary_document or None, "part": section.part.upper() if section.part else None,
                "itemNumber": None if section.preamble else section.number.upper(), "sectionKey": section.key, "sectionTitle": section.title,
                "item": section.heading, "chunkSequence": sequence, "boundaryType": boundary,
                "paragraphRange": [section.paragraph_start + group[0]["p"], section.paragraph_start + group[-1]["p"]],
                "sentenceRange": [group[0]["s0"], group[-1]["s1"]],
                "sectionWordStart": section_word_start, "sectionWordEnd": section_word_end,
                "documentWordStart": doc_word_start, "documentWordEnd": doc_word_end,
                "documentCharStart": doc_char_start, "documentCharEnd": doc_char_end,
                "wordStart": doc_word_start, "wordEnd": doc_word_end,
                "previousChunkId": None, "nextChunkId": None, "sourcePath": None,
                "sourceUrl": document.url, "url": document.url, "text": content,
            })
    section_counts: dict[str, int] = {}
    for chunk in chunks:
        section_counts[chunk["sectionKey"]] = section_counts.get(chunk["sectionKey"], 0) + 1
    if len(chunks) >= 10 and section_counts:
        dominant, count = max(section_counts.items(), key=lambda item: item[1])
        if count / len(chunks) > .75:
            chunks = [chunk for chunk in chunks if chunk["sectionKey"] != dominant]
    for index, chunk in enumerate(chunks):
        chunk["previousChunkId"] = chunks[index - 1]["chunkId"] if index else None
        chunk["nextChunkId"] = chunks[index + 1]["chunkId"] if index + 1 < len(chunks) else None
    return chunks
