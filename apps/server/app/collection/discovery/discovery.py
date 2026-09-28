"""
Source Discovery Engine.
Orchestrates discovery providers to find and rank eligible sources for a CollectionRequest.
Supports discovering alternative sources when a primary source encounters an access barrier.
"""

from typing import List, Optional, Set
from app.collection.schemas import CollectionRequest, SourceDefinition
from app.collection.discovery.base import BaseDiscoveryProvider
from app.collection.discovery.registry import SourceRegistry
from app.collection.discovery.registry_provider import RegistryDiscoveryProvider
from app.collection.discovery.direct_provider import DirectURLProvider
from app.collection.discovery.search_provider import SearchDiscoveryProvider
from app.core.logger import logger


class SourceDiscovery:
    """
    Main source discovery coordinator.
    """

    def __init__(
        self,
        registry: Optional[SourceRegistry] = None,
        providers: Optional[List[BaseDiscoveryProvider]] = None,
    ):
        self.registry = registry or SourceRegistry()
        self.providers = providers or [
            DirectURLProvider(),
            RegistryDiscoveryProvider(self.registry),
            SearchDiscoveryProvider(),
        ]

    async def discover_sources(self, request: CollectionRequest) -> List[SourceDefinition]:
        """
        Discovers eligible sources across all registered discovery providers.
        """
        all_sources: List[SourceDefinition] = []
        seen_domains: Set[str] = set()
        seen_ids: Set[str] = set()

        for provider in self.providers:
            try:
                discovered = await provider.discover(request)
                for src in discovered:
                    if src.source_id in seen_ids:
                        continue
                    if src.domain in seen_domains and not src.metadata.get("direct_url"):
                        continue

                    all_sources.append(src)
                    seen_ids.add(src.source_id)
                    if src.domain:
                        seen_domains.add(src.domain)
            except Exception as e:
                logger.warning(f"Discovery provider {provider.__class__.__name__} failed: {e}")

        # Deterministic sorting: preferred + field-matching + structured sources first
        pref_domains = [
            self.registry.normalize_domain(p) for p in request.source_preferences if p
        ]
        field_tokens = set()
        for field in (request.required_fields or []):
            field_tokens.update(t for t in field.lower().split("_") if len(t) > 2)
        entity_token = (request.entity or "").lower()

        def sort_key(s: SourceDefinition) -> int:
            score = 100
            if s.domain in pref_domains or any(p.lower() in s.name.lower() for p in request.source_preferences):
                score -= 40
            caps = " ".join(c.lower() for c in (s.capabilities or []))
            field_matches = sum(1 for token in field_tokens if token in caps)
            score -= min(field_matches, 4) * 8
            if entity_token and entity_token in caps:
                score -= 15
            if s.type.value == "api":
                score -= 12
            elif s.type.value == "dataset":
                score -= 8
            elif s.type.value == "rss":
                score -= 4
            if (s.metadata or {}).get("discovered_by") == "web_search":
                score += 5  # slight preference for curated registry sources
            return score

        all_sources.sort(key=sort_key)

        # Apply max_sources limit
        max_limit = request.limits.max_sources if request.limits else 10
        selected = all_sources[:max_limit]

        logger.info(f"SourceDiscovery selected {len(selected)}/{len(all_sources)} eligible sources")
        return selected

    async def discover(self, request: CollectionRequest) -> List[SourceDefinition]:
        """Alias for discover_sources."""
        return await self.discover_sources(request)

    def estimate_availability(
        self, request: CollectionRequest, sources: List[SourceDefinition]
    ) -> List[dict]:
        """Estimates which requested fields the given sources can likely provide."""
        from app.collection.discovery.grounding import estimate_field_availability
        return estimate_field_availability(request.required_fields, sources)

    async def discover_alternative_sources(
        self,
        failed_source: Optional[SourceDefinition] = None,
        request: Optional[CollectionRequest] = None,
        exclude_source_ids: Optional[List[str]] = None,
    ) -> List[SourceDefinition]:
        """
        Discovers fallback/alternative sources excluding the failed source and any
        already-processed/blocked source IDs.

        :param failed_source: The source that encountered an access barrier or failure.
        :param request: The originating CollectionRequest used to match replacements.
        :param exclude_source_ids: Additional source IDs that must not be returned.
        """
        exclude_ids = list(exclude_source_ids or [])
        if failed_source is not None and failed_source.source_id not in exclude_ids:
            exclude_ids.append(failed_source.source_id)

        actual_req = request or CollectionRequest(
            objective="Discover alternative sources", entity="startup"
        )

        exclude_set = set(exclude_ids)
        all_eligible = await self.discover_sources(actual_req)
        alternatives = [s for s in all_eligible if s.source_id not in exclude_set]

        # If standard discovery did not yield unused sources, search for broader capability matches
        if not alternatives:
            broader = self.registry.find_by_capability(actual_req.entity)
            for s in broader:
                if s.source_id not in exclude_set and s not in alternatives:
                    alternatives.append(s)

        logger.info(
            f"Discovered {len(alternatives)} alternative sources (excluded: {exclude_ids})"
        )
        return alternatives
