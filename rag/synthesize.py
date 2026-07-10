from __future__ import annotations

import re
from typing import Callable

PROHIBITED = re.compile(r"\b(buy|sell|hold|guaranteed upside|this stock will go (?:up|down))\b", re.I)


def validate_answer(answer: str, allowed_chunk_ids: set[str]) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if PROHIBITED.search(answer):
        warnings.append("Generated response contained prohibited financial-advice language and was withheld.")
        return "The generated interpretation was withheld because it did not meet the research-only safety rules.", warnings
    cited = {chunk_id for chunk_id in allowed_chunk_ids if chunk_id in answer}
    if allowed_chunk_ids and not cited:
        warnings.append("Generated response did not cite retrieved chunk IDs.")
    return answer, warnings


def synthesize_answer(prompt: str, chunk_ids: set[str], generator: Callable[[str], str] | None = None) -> tuple[str, list[str]]:
    if generator is None:
        from rag.ollama_client import generate_with_llama
        generator = generate_with_llama
    answer = generator(prompt)
    return validate_answer(answer, chunk_ids)
