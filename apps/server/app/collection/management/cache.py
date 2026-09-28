"""
Document Cache Abstraction.
Avoids redundant fetches of recently retrieved canonical URLs.
Designed with in-memory local caching and future Redis compatibility.
"""

import time
from typing import Optional, Dict, Any, Tuple
from app.collection.schemas import RawDocument
from app.core.config import settings
from app.core.logger import logger


class DocumentCache:
    """
    Caching layer checking canonical URL and content freshness.
    """

    def __init__(
        self,
        default_ttl_seconds: int = 3600,
        ttl_seconds: Optional[int] = None,
        max_entries: Optional[int] = None,
    ):
        self.default_ttl = ttl_seconds if ttl_seconds is not None else default_ttl_seconds
        self.max_entries = max_entries if max_entries is not None else settings.DATAPILOT_CACHE_MAX_ENTRIES
        # In-memory store: key -> (RawDocument, expiry_timestamp)
        self._store: Dict[str, Tuple[RawDocument, float]] = {}

    def _evict(self) -> None:
        """Removes expired entries and enforces the maximum entry bound."""
        now = time.time()
        for key in [k for k, (_, exp) in self._store.items() if exp <= now]:
            self._store.pop(key, None)

        overflow = len(self._store) - self.max_entries
        if overflow > 0:
            # Drop the entries expiring soonest first
            soonest = sorted(self._store.items(), key=lambda kv: kv[1][1])[:overflow]
            for key, _ in soonest:
                self._store.pop(key, None)


    def _get_doc(self, arg1: str, arg2: Optional[str] = None) -> Optional[RawDocument]:
        key = f"{arg1}:{arg2.strip().lower()}" if arg2 else arg1.strip().lower()
        if key in self._store:
            doc, expiry = self._store[key]
            if time.time() < expiry:
                logger.debug(f"Cache HIT for key: {key}")
                return doc
            del self._store[key]

        if arg2 and arg2.strip().lower() in self._store:
            doc, expiry = self._store[arg2.strip().lower()]
            if time.time() < expiry:
                logger.debug(f"Cache HIT for URL: {arg2}")
                return doc
            del self._store[arg2.strip().lower()]

        return None

    def _set_doc(self, arg1: str, arg2: Any, document: Optional[RawDocument] = None, ttl_seconds: Optional[int] = None) -> None:
        if isinstance(arg2, RawDocument):
            key = arg1.strip().lower()
            doc = arg2
            ttl = ttl_seconds or self.default_ttl
        else:
            key = f"{arg1}:{str(arg2).strip().lower()}"
            doc = document
            ttl = ttl_seconds or self.default_ttl

        if doc is not None:
            expiry = time.time() + ttl
            # Index under the requested key plus the requested and canonical URLs so that
            # lookups by base_url or canonical_url both hit (they often differ after redirects).
            for candidate in (key, doc.url.strip().lower() if doc.url else "", doc.canonical_url.strip().lower() if doc.canonical_url else ""):
                if candidate:
                    self._store[candidate] = (doc, expiry)
            self._evict()
            logger.debug(f"Cached document under key: {key} (TTL: {ttl}s)")

    async def get(self, arg1: str, arg2: Optional[str] = None) -> Optional[RawDocument]:
        """Async get supporting get(canonical_url) and get(source_id, canonical_url)."""
        return self._get_doc(arg1, arg2)

    def get_sync(self, arg1: str, arg2: Optional[str] = None) -> Optional[RawDocument]:
        return self._get_doc(arg1, arg2)

    async def set(self, arg1: str, arg2: Any, document: Optional[RawDocument] = None, ttl_seconds: Optional[int] = None) -> None:
        """Async set supporting set(canonical_url, doc) and set(source_id, canonical_url, doc)."""
        self._set_doc(arg1, arg2, document, ttl_seconds)

    def set_sync(self, arg1: str, arg2: Any, document: Optional[RawDocument] = None, ttl_seconds: Optional[int] = None) -> None:
        self._set_doc(arg1, arg2, document, ttl_seconds)

    def clear(self) -> None:
        """Flushes cache."""
        self._store.clear()
