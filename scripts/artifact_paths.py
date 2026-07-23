from __future__ import annotations

from pathlib import Path


WINDOWS_RESERVED_FILENAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


def ticker_artifact_stem(ticker: str) -> str:
    """Return a filesystem-safe stem for a ticker JSON artifact.

    Ticker IDs stay unchanged in JSON and URLs. This only protects file names
    such as CON.json, PRN.json, AUX.json, COM1.json, and LPT1.json on Windows.
    """
    normalized = str(ticker).upper().strip()
    safe = "".join(char if char.isalnum() or char in {"-", "_", "."} else "-" for char in normalized).strip(" .")
    if not safe:
        safe = "UNKNOWN"
    if safe.split(".", 1)[0].upper() in WINDOWS_RESERVED_FILENAMES:
        return f"_{safe}"
    return safe


def ticker_artifact_path(directory: Path, ticker: str) -> Path:
    return directory / f"{ticker_artifact_stem(ticker)}.json"


def ticker_from_artifact_stem(stem: str) -> str:
    normalized = str(stem).upper()
    if normalized.startswith("_") and normalized[1:].split(".", 1)[0] in WINDOWS_RESERVED_FILENAMES:
        return normalized[1:]
    return normalized
