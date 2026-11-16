"""Shared HTTP layer: disk cache, per-source rate limiting, retries, provenance log.

Every integration goes through `HttpClient.get`, so caching, politeness and
traceability are implemented exactly once. The transport is injectable, which
is how the offline test-suite runs without a network.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

USER_AGENT = "biopathway-mapper/1.0 (Claude Skill; stdlib urllib)"

# Minimum seconds between requests, per source. Values follow each provider's
# published usage guidance (see references/data-sources.md).
MIN_INTERVAL = {
    "ncbi": 0.34,      # 3 requests/s without an API key
    "kegg": 0.34,      # KEGG asks for at most 3 requests/s
    "string": 1.0,     # STRING asks for one request per second
    "uniprot": 0.2,
    "reactome": 0.2,
    "alphafold": 0.2,
    "rcsb": 0.2,
    "gtex": 0.5,
    "hpa": 0.5,
}
RETRY_STATUS = {429, 500, 502, 503, 504}
DEFAULT_TTL = 7 * 24 * 3600


class SourceError(Exception):
    """A data source could not answer. Carries enough context to report honestly."""

    def __init__(self, source: str, url: str, message: str, status: Optional[int] = None):
        super().__init__(f"[{source}] {message} ({url})")
        self.source = source
        self.url = url
        self.status = status
        self.message = message


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _urllib_transport(url: str, headers: dict, timeout: float, data: Optional[bytes] = None):
    """Return (status, response_headers, text). Raises OSError on network failure."""
    req = urllib.request.Request(url, headers=headers, data=data, method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:
            pass
        return exc.code, dict(exc.headers or {}), body


def default_cache_dir() -> Path:
    env = os.environ.get("BPM_CACHE_DIR")
    if env:
        return Path(env)
    return Path.home() / ".cache" / "biopathway-mapper"


class HttpClient:
    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        cache_ttl: float = DEFAULT_TTL,
        use_cache: bool = True,
        offline: bool = False,
        transport: Optional[Callable] = None,
        max_retries: int = 3,
        timeout: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.cache_dir = Path(cache_dir) if cache_dir else default_cache_dir()
        self.cache_ttl = cache_ttl
        self.use_cache = use_cache
        self.offline = offline
        self.transport = transport or _urllib_transport
        self.max_retries = max_retries
        self.timeout = timeout
        self._sleep = sleep
        self._clock = clock
        self._last_request: dict[str, float] = {}
        self.min_interval = dict(MIN_INTERVAL)
        if os.environ.get("NCBI_API_KEY"):
            self.min_interval["ncbi"] = 0.11  # 10 requests/s with a key
        # Provenance: one record per logical request, cached or not.
        self.log: list[dict] = []

    # ---------------------------------------------------------------- cache
    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha256(url.encode()).hexdigest() + ".json")

    def _cache_read(self, url: str, ignore_ttl: bool = False):
        if not self.use_cache:
            return None
        path = self._cache_path(url)
        try:
            entry = json.loads(path.read_text())
        except (OSError, ValueError):
            return None
        if not ignore_ttl and time.time() - entry.get("fetched_epoch", 0) > self.cache_ttl:
            return None
        return entry

    def _cache_write(self, url: str, body: str) -> None:
        if not self.use_cache:
            return
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = self._cache_path(url).with_suffix(".tmp")
            tmp.write_text(json.dumps(
                {"url": url, "fetched_at": utcnow(), "fetched_epoch": time.time(), "body": body}))
            tmp.replace(self._cache_path(url))
        except OSError:
            pass  # a read-only cache directory must never break an analysis

    # ----------------------------------------------------------- rate limit
    def _throttle(self, source: str) -> None:
        interval = self.min_interval.get(source, 0.2)
        last = self._last_request.get(source)
        if last is not None:
            wait = interval - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        self._last_request[source] = self._clock()

    # ------------------------------------------------------------------ get
    def get(self, source: str, url: str, params: Optional[dict] = None,
            accept: Optional[str] = None, secret_params: Optional[dict] = None) -> str:
        """GET `url` and return the body text. Raises SourceError on failure.

        `params` are appended in sorted order so the cache key is stable. API
        keys go in `secret_params`: they are sent on the wire but kept out of
        the cache key and the provenance log.
        """
        return self._get(source, url, params, accept, secret_params)

    def post(self, source: str, url: str, body: str, content_type: str = "text/plain",
             accept: Optional[str] = "application/json") -> str:
        """POST with the same cache/retry/provenance rules. The cache key includes a body hash."""
        return self._get(source, url, None, accept, None, data=body.encode(), content_type=content_type)

    def post_json(self, source: str, url: str, body: str, content_type: str = "text/plain"):
        text = self.post(source, url, body, content_type)
        try:
            return json.loads(text)
        except ValueError as exc:
            raise SourceError(source, url, f"response was not valid JSON: {exc}") from exc

    def _get(self, source, url, params, accept, secret_params, data=None, content_type=None):
        if params:
            query = urllib.parse.urlencode(sorted(params.items()), quote_via=urllib.parse.quote)
            url = f"{url}{'&' if '?' in url else '?'}{query}"
        if data is not None:  # cache/log key for POST: URL plus a digest of the body
            url = f"{url}#POST:{hashlib.sha256(data).hexdigest()[:16]}"
        cached = self._cache_read(url)
        if cached is not None:
            self.log.append({"source": source, "url": url, "cached": True,
                             "retrieved_at": cached["fetched_at"]})
            return cached["body"]
        if self.offline:
            stale = self._cache_read(url, ignore_ttl=True)
            if stale is not None:
                self.log.append({"source": source, "url": url, "cached": True,
                                 "retrieved_at": stale["fetched_at"], "stale": True})
                return stale["body"]
            raise SourceError(source, url, "offline mode and no cached response")

        # Secrets are added to the wire URL only: never to the cache key or log.
        wire_url = url.split("#POST:")[0]
        if secret_params:
            wire_url += ("&" if "?" in url else "?") + urllib.parse.urlencode(secret_params)
        headers = {"User-Agent": USER_AGENT}
        if accept:
            headers["Accept"] = accept
        if content_type:
            headers["Content-Type"] = content_type

        last_error = "no attempt made"
        status = None
        for attempt in range(self.max_retries + 1):
            self._throttle(source)
            try:
                if data is None:
                    status, resp_headers, body = self.transport(wire_url, headers, self.timeout)
                else:
                    status, resp_headers, body = self.transport(wire_url, headers, self.timeout, data)
            except (OSError, ValueError) as exc:  # URLError, timeouts, DNS failures
                status, resp_headers, body = None, {}, ""
                last_error = f"network error: {exc}"
            else:
                if 200 <= status < 300:
                    self._cache_write(url, body)
                    self.log.append({"source": source, "url": url, "cached": False,
                                     "retrieved_at": utcnow()})
                    return body
                last_error = f"HTTP {status}"
                if status not in RETRY_STATUS:
                    break  # 400/404 etc. will not improve on retry
            if attempt < self.max_retries:
                delay = min(2.0 ** attempt, 30.0)
                retry_after = {k.lower(): v for k, v in resp_headers.items()}.get("retry-after")
                if retry_after:
                    try:
                        delay = min(max(delay, float(retry_after)), 60.0)
                    except ValueError:
                        pass
                self._sleep(delay)

        # Graceful degradation: an expired cache entry beats no answer, but is flagged.
        stale = self._cache_read(url, ignore_ttl=True)
        if stale is not None and status != 404:
            self.log.append({"source": source, "url": url, "cached": True,
                             "retrieved_at": stale["fetched_at"], "stale": True})
            return stale["body"]
        raise SourceError(source, url, last_error, status=status)

    def get_json(self, source: str, url: str, params: Optional[dict] = None,
                 secret_params: Optional[dict] = None):
        body = self.get(source, url, params, accept="application/json",
                        secret_params=secret_params)
        try:
            return json.loads(body)
        except ValueError as exc:
            raise SourceError(source, url, f"response was not valid JSON: {exc}") from exc
