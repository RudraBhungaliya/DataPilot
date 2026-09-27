"""
Registry Discovery Provider.
Discovers sources from SourceRegistry matching request entity, capabilities, and preferences.
"""

from typing import List, Set
from app.collection.discovery.base import BaseDiscoveryProvider
from app.collection.discovery.registry import SourceRegistry
from app.collection.schemas import CollectionRequest, SourceDefinition, SourceStatus, SourceType
from app.core.logger import logger


class RegistryDiscoveryProvider(BaseDiscoveryProvider):
    """
    Evaluates registered sources in SourceRegistry against CollectionRequest criteria.
    """

    def __init__(self, registry: SourceRegistry):
        self.registry = registry

    async def discover(self, request: CollectionRequest) -> List[SourceDefinition]:
        """
        Discovers eligible active sources from the registry.
        """
        strat = request.collection_strategy
        active_sources = self.registry.list(status=SourceStatus.ACTIVE)
        matched_sources: List[SourceDefinition] = []

        # Target search tokens
        search_tokens: Set[str] = set()
        search_tokens.add(request.entity.lower().strip())
        for f in request.required_fields:
            search_tokens.add(f.lower().strip())
        for k, v in request.constraints.items():
            if isinstance(v, str):
                search_tokens.add(v.lower().strip())
            search_tokens.add(k.lower().strip())

        # Check source preferences
        pref_domains = [
            self.registry.normalize_domain(p) for p in request.source_preferences if p
        ]

        for src in active_sources:
            # 1. Check strategy permissions
            if src.type == SourceType.API and not strat.allow_api:
                continue
            if src.type == SourceType.WEBSITE and not strat.allow_web:
                continue
            if src.type == SourceType.DATASET and not strat.allow_public_datasets:
                continue
            if src.type == SourceType.RSS and not strat.allow_rss:
                continue

            # 2. Check source preferences priority
            is_preferred = False
            for p in request.source_preferences:
                p_clean = p.lower().strip()
                if p_clean in src.name.lower() or p_clean in src.domain.lower() or src.domain in pref_domains:
                    is_preferred = True
                    break

            # 3. Match capabilities against search tokens
            src_caps = [c.lower().strip() for c in src.capabilities]
            has_capability_match = any(token in src_caps for token in search_tokens) or any(
                any(token in c for c in src_caps) for token in search_tokens
            )

            # 4. If preferred or capability match, include
            if is_preferred or has_capability_match:
                matched_sources.append(src)

        logger.info(
            f"RegistryDiscoveryProvider found {len(matched_sources)} sources for entity '{request.entity}'"
        )
        return matched_sources
