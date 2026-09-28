"""
Search-based source discovery.

Turns a data requirement into candidate sources by querying a configurable web
search API (Brave / Tavily / any generic JSON endpoint), so discovery is not
limited to a fixed registry. When no provider is configured this is a no-op.
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from app.collection.discovery.base import BaseDiscoveryProvider
from app.collection.discovery.registry import SourceRegistry
from app.collection.schemas import (
    AccessMethod,
    CollectionRequest,
    SourceDefinition,
    SourceType,
)
from app.core.config import settings
from app.core.logger import logger


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


def _dotted_get(payload: Any, path: str) -> Any:
    """Resolves a dotted path like 'web.results' against nested dicts."""
    current = payload
    for part in (path or "").split("."):
        if not part:
            continue
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


class BaseSearchProvider:
    name = "none"

    def is_configured(self) -> bool:
        return bool(settings.SEARCH_API_URL and settings.SEARCH_API_KEY)

    async def search(self, query: str, max_results: int) -> List[SearchResult]:
        raise NotImplementedError


class BraveSearchProvider(BaseSearchProvider):
    name = "brave"

    async def search(self, query: str, max_results: int) -> List[SearchResult]:
        url = settings.SEARCH_API_URL or "https://api.search.brave.com/res/v1/web/search"
        headers = {
            "Accept": "application/json",
            "X-Subscription-Token": settings.SEARCH_API_KEY or "",
        }
        params = {"q": query, "count": max_results}
        async with httpx.AsyncClient(timeout=settings.SEARCH_TIMEOUT_SECONDS) as client:
            resp = await client.get(url, headers=headers, params=params)
            resp.raise_for_status()
            return self._parse(resp.json(), "web.results", "url", "title", "description")

    @staticmethod
    def _parse(payload: Any, path: str, url_f: str, title_f: str, snippet_f: str) -> List[SearchResult]:
        return _parse_results(payload, path, url_f, title_f, snippet_f)


class TavilySearchProvider(BaseSearchProvider):
    name = "tavily"

    async def search(self, query: str, max_results: int) -> List[SearchResult]:
        url = settings.SEARCH_API_URL or "https://api.tavily.com/search"
        payload = {
            "api_key": settings.SEARCH_API_KEY,
            "query": query,
            "max_results": max_results,
            "search_depth": "basic",
        }
        async with httpx.AsyncClient(timeout=settings.SEARCH_TIMEOUT_SECONDS) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return _parse_results(resp.json(), "results", "url", "title", "content")


class GenericSearchProvider(BaseSearchProvider):
    name = "generic"

    async def search(self, query: str, max_results: int) -> List[SearchResult]:
        headers = {"Accept": "application/json"}
        if settings.SEARCH_API_KEY:
            headers["Authorization"] = f"Bearer {settings.SEARCH_API_KEY}"
        params = {"q": query, "limit": max_results}
        async with httpx.AsyncClient(timeout=settings.SEARCH_TIMEOUT_SECONDS) as client:
            resp = await client.get(settings.SEARCH_API_URL, headers=headers, params=params)
            resp.raise_for_status()
            return _parse_results(
                resp.json(),
                settings.SEARCH_RESULTS_PATH,
                settings.SEARCH_URL_FIELD,
                settings.SEARCH_TITLE_FIELD,
                settings.SEARCH_SNIPPET_FIELD,
            )


def _parse_results(
    payload: Any, path: str, url_field: str, title_field: str, snippet_field: str
) -> List[SearchResult]:
    items = _dotted_get(payload, path) if path else payload
    if not isinstance(items, list):
        return []
    results: List[SearchResult] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = item.get(url_field) or item.get("url") or item.get("link")
        if not url:
            continue
        results.append(
            SearchResult(
                title=str(item.get(title_field) or item.get("title") or ""),
                url=str(url),
                snippet=str(item.get(snippet_field) or item.get("snippet") or item.get("description") or ""),
            )
        )
    return results


def get_search_provider() -> Optional[BaseSearchProvider]:
    """Returns the configured search provider, or None if discovery is disabled."""
    name = (settings.SEARCH_PROVIDER or "").strip().lower()
    if not name:
        return None
    provider = {"brave": BraveSearchProvider, "tavily": TavilySearchProvider,
                "generic": GenericSearchProvider}.get(name)
    if provider is None:
        logger.warning(f"Unknown SEARCH_PROVIDER '{name}'; search discovery disabled.")
        return None
    instance = provider()
    if not instance.is_configured():
        logger.info(f"Search provider '{name}' is not configured (missing URL/key); skipping.")
        return None
    return instance


class SearchDiscoveryProvider(BaseDiscoveryProvider):
    """
    Discovers candidate sources from a web search API.
    Falls back to a no-op when no provider is configured.
    """

    def __init__(self, search_provider: Optional[BaseSearchProvider] = None):
        self.search_provider = search_provider if search_provider is not None else get_search_provider()

    async def discover(self, request: CollectionRequest) -> List[SourceDefinition]:
        if self.search_provider is None:
            return []

        query = self._build_query(request)
        try:
            results = await self.search_provider.search(query, settings.SEARCH_MAX_RESULTS)
        except Exception as e:
            logger.warning(f"Search discovery failed ({type(e).__name__}): {e}")
            return []

        sources: List[SourceDefinition] = []
        seen_domains = set()
        for result in results:
            domain = SourceRegistry.normalize_domain(result.url)
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)
            sources.append(
                SourceDefinition(
                    source_id=f"src_search_{domain.replace('.', '_')}",
                    name=result.title or f"Search result: {domain}",
                    type=SourceType.WEBSITE,
                    base_url=result.url,
                    domain=domain,
                    capabilities=[request.entity] + [f.lower() for f in request.required_fields],
                    access_method=AccessMethod.HTTP,
                    status="active",
                    metadata={
                        "discovered_by": "web_search",
                        "query": query,
                        "snippet": result.snippet,
                    },
                )
            )
        logger.info(f"SearchDiscoveryProvider found {len(sources)} candidate sources for '{query}'")
        return sources

    @staticmethod
    def _build_query(request: CollectionRequest) -> str:
        parts = [request.entity.replace("_", " ")]
        if request.constraints:
            for key, value in request.constraints.items():
                if isinstance(value, str):
                    parts.append(value)
        return " ".join(parts) + " list"
