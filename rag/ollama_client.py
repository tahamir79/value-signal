from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from rag.config import RagConfig


class OllamaError(RuntimeError):
    """An actionable local Ollama error safe to display to a user."""


def _request(path: str, payload: dict[str, Any] | None = None, *, timeout: float = 30) -> dict[str, Any]:
    base = RagConfig.from_env().ollama_base_url
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(base + path, data=data, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OllamaError(f"Ollama request failed ({exc.code}): {detail}") from exc
    except (URLError, TimeoutError, ConnectionError) as exc:
        raise OllamaError("Ollama is not running. Start Ollama locally and try again.") from exc
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise OllamaError("Ollama returned an invalid response.") from exc


def check_ollama_available() -> bool:
    try:
        _request("/api/tags", timeout=3)
        return True
    except OllamaError:
        return False


def check_model_available(model_name: str) -> bool:
    result = _request("/api/tags", timeout=5)
    names = {row.get("name") for row in result.get("models", [])}
    return model_name in names or f"{model_name}:latest" in names


_verified_models: set[str] = set()


def _require_model(model: str, kind: str) -> None:
    if model not in _verified_models and not check_model_available(model):
        label = "Embedding" if kind == "embedding" else "Synthesis"
        raise OllamaError(f"{label} model {model} is not installed. Run: ollama pull {model}")
    _verified_models.add(model)


def get_embedding(text: str, model: str = "nomic-embed-text") -> list[float]:
    return get_embeddings([text], model)[0]


def get_embeddings(texts: list[str], model: str = "nomic-embed-text") -> list[list[float]]:
    if not texts:
        return []
    _require_model(model, "embedding")
    result = _request("/api/embed", {"model": model, "input": texts}, timeout=120)
    embeddings = result.get("embeddings")
    if not isinstance(embeddings, list) or len(embeddings) != len(texts) or any(not isinstance(row, list) for row in embeddings):
        raise OllamaError("Ollama returned an invalid number of embedding vectors.")
    return [[float(value) for value in row] for row in embeddings]


def generate_with_llama(prompt: str, model: str = "llama3.2:3b", max_output_tokens: int | None = None) -> str:
    _require_model(model, "synthesis")
    payload: dict[str, Any] = {"model": model, "prompt": prompt, "stream": False}
    if max_output_tokens:
        payload["options"] = {"num_predict": max_output_tokens}
    result = _request("/api/generate", payload, timeout=180)
    answer = result.get("response")
    if not isinstance(answer, str):
        raise OllamaError("Ollama returned no generated response.")
    return answer.strip()
