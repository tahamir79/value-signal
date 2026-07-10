from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class SecRequestError(RuntimeError):
    pass


class SecClient:
    def __init__(self, *, user_agent: str, cache_dir: str | Path = "data/cache/sec/http",
                 sleep_ms: int = 200, attempts: int = 3, timeout: int = 30) -> None:
        if not user_agent or "@" not in user_agent:
            raise ValueError("SEC User-Agent should include an identifying contact email.")
        self.user_agent = user_agent
        self.cache_dir = Path(cache_dir)
        self.sleep_ms = max(100, sleep_ms)
        self.attempts = max(1, attempts)
        self.timeout = timeout
        self._last_request = 0.0

    def cache_path(self, url: str) -> Path:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{digest}.bin"

    def get_bytes(self, url: str, *, force: bool = False) -> tuple[bytes, dict[str, Any]]:
        path = self.cache_path(url)
        if path.exists() and not force:
            return path.read_bytes(), {"url": url, "status": 200, "cacheHit": True, "path": str(path)}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        error: Exception | None = None
        for attempt in range(self.attempts):
            self._throttle()
            try:
                request = Request(url, headers={"User-Agent": self.user_agent, "Accept": "application/json,text/html,*/*"})
                with urlopen(request, timeout=self.timeout) as response:
                    body = response.read()
                    status = getattr(response, "status", 200)
                    if status != 200:
                        raise SecRequestError(f"HTTP {status} for {url}")
                    path.write_bytes(body)
                    return body, {"url": url, "status": status, "cacheHit": False, "path": str(path)}
            except (HTTPError, URLError, TimeoutError, SecRequestError) as exc:
                error = exc
                if attempt < self.attempts - 1:
                    time.sleep(2 ** attempt)
        raise SecRequestError(f"SEC request failed after {self.attempts} attempts: {error}")

    def get_json(self, url: str, *, force: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
        body, meta = self.get_bytes(url, force=force)
        try:
            return json.loads(body.decode("utf-8")), meta
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SecRequestError(f"Invalid JSON from {url}: {exc}") from exc

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request
        required = self.sleep_ms / 1000
        if elapsed < required:
            time.sleep(required - elapsed)
        self._last_request = time.monotonic()

