from __future__ import annotations
import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

class ProviderError(RuntimeError):
    pass

def fetch_bytes(url: str, user_agent: str, attempts: int = 3, timeout: int = 30) -> bytes:
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json,text/csv,*/*"})
            with urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    raise ProviderError(f"HTTP {response.status} for {url}")
                return response.read()
        except (HTTPError, URLError, TimeoutError, ProviderError) as exc:
            error = exc
            if attempt < attempts - 1:
                time.sleep(2 ** attempt)
    raise ProviderError(f"Request failed after {attempts} attempts: {error}")

def fetch_json(url: str, user_agent: str) -> dict[str, Any]:
    try:
        return json.loads(fetch_bytes(url, user_agent).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProviderError(f"Invalid JSON from {url}: {exc}") from exc
