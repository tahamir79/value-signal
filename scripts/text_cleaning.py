from __future__ import annotations

import html
import re
from collections import Counter
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    """Small, dependency-free HTML-to-paragraph converter.

    Cells are separated in source order and rows/paragraphs become blank-line
    delimited blocks.  Inline XBRL facts remain text, while hidden payloads do not.
    """

    ignored_tags = {"script", "style", "noscript", "svg", "ix:hidden"}
    paragraph_tags = {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "section", "article"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0
        self.ignored_stack: list[str] = []

    def _break(self) -> None:
        if self.parts and not self.parts[-1].endswith("\n\n"):
            self.parts.append("\n\n")

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        attributes = dict(attrs)
        if tag in self.ignored_tags or attributes.get("style", "").replace(" ", "").lower().find("display:none") >= 0:
            self.ignored_depth += 1
            self.ignored_stack.append(tag)
        elif not self.ignored_depth and (tag in self.paragraph_tags or tag == "br"):
            self._break()
        elif not self.ignored_depth and tag in {"td", "th"} and self.parts:
            self.parts.append(" | ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.ignored_depth and self.ignored_stack and tag == self.ignored_stack[-1]:
            self.ignored_depth -= 1
            self.ignored_stack.pop()
        elif not self.ignored_depth and tag in self.paragraph_tags:
            self._break()

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)


_PAGE_NUMBER = re.compile(r"(?i)^(?:page\s+)?\d+(?:\s+of\s+\d+)?$")
_TOC_MARKER = re.compile(r"(?i)^(?:table of contents|index)$")


def _line_key(value: str) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", value).strip().lower())


def clean_filing_html(source: str) -> str:
    """Return deterministic, paragraph-preserving filing text."""
    parser = _TextExtractor()
    parser.feed(source)
    raw = html.unescape("".join(parser.parts)).replace("\xa0", " ")
    paragraphs: list[str] = []
    for block in re.split(r"\n\s*\n+", raw):
        lines = [re.sub(r"\s+", " ", line).strip(" |") for line in block.splitlines()]
        lines = [line for line in lines if line and not _PAGE_NUMBER.fullmatch(line) and not _TOC_MARKER.fullmatch(line)]
        if lines:
            paragraphs.append(" ".join(lines))

    keys = [_line_key(p) for p in paragraphs]
    repeated = {key for key, count in Counter(keys).items() if count >= 4 and len(key) < 120}
    paragraphs = [p for p, key in zip(paragraphs, keys) if key not in repeated]
    return "\n\n".join(paragraphs).strip()
