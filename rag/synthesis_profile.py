from __future__ import annotations

from dataclasses import dataclass

QUICK_MODE = "quick"
DEEP_MODE = "deep"


@dataclass(frozen=True)
class SynthesisProfile:
    name: str
    top_k: int
    max_context_chars: int
    max_output_tokens: int
    style: str


PROFILES = {
    QUICK_MODE: SynthesisProfile(QUICK_MODE, 3, 4000, 300, "concise answer"),
    DEEP_MODE: SynthesisProfile(DEEP_MODE, 8, 12000, 900, "detailed analyst-style answer"),
}

DEEP_TRIGGERS = (
    "further review", "research next", "impact", "detailed", "assessment",
    "mitigation", "practices", "specific", "follow-up", "follow up",
)


def normalize_depth(value: str | None, query: str = "") -> str:
    if value in PROFILES:
        return value
    lowered = query.lower()
    if any(trigger in lowered for trigger in DEEP_TRIGGERS):
        return DEEP_MODE
    return DEEP_MODE


def profile_for(value: str | None, query: str = "") -> SynthesisProfile:
    return PROFILES[normalize_depth(value, query)]
