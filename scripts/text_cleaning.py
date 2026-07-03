from __future__ import annotations

import html
import re
from collections import Counter
from html.parser import HTMLParser


class _TextExtractor(HTMLParser):
    block_tags = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "table", "section"}
    ignored_tags = {"script", "style", "noscript", "svg"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self.ignored_tags:
            self.ignored_depth += 1
        elif not self.ignored_depth and tag in self.block_tags:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.ignored_tags and self.ignored_depth:
            self.ignored_depth -= 1
        elif not self.ignored_depth and tag in self.block_tags:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.ignored_depth:
            self.parts.append(data)


def clean_filing_html(source: str) -> str:
    parser = _TextExtractor()
    parser.feed(source)
    raw = html.unescape("".join(parser.parts)).replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines()]
    lines = [line for line in lines if line and line.lower() not in {"table of contents", "index"} and not re.fullmatch(r"[.\s\-–—]*\d+", line)]
    normalized = [re.sub(r"\d+", "#", line.lower()) for line in lines]
    repeated = {value for value, count in Counter(normalized).items() if count >= 4 and len(value) < 120}
    kept = [line for line, key in zip(lines, normalized) if key not in repeated]
    text = "\n".join(kept)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
