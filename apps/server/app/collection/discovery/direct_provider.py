"""
Direct URL Discovery Provider.
Converts explicitly specified URLs into ad-hoc SourceDefinitions.
"""

from typing import List
from app.collection.discovery.base import BaseDiscoveryProvider
from app.collection.discovery.registry import SourceRegistry
from app.collection.schemas import (
    CollectionRequest,
    SourceDefinition,
    SourceType,
    AccessMethod,
    SourceStatus,
)


class DirectURLProvider(BaseDiscoveryProvider):
    """
    Creates temporary or ad-hoc SourceDefinitions for user-provided direct URLs.
    """

    async def discover(self, request: CollectionRequest) -> List[SourceDefinition]:
        sources: List[SourceDefinition] = []
        urls = list(request.direct_urls or [])
        if request.metadata and "direct_urls" in request.metadata and isinstance(request.metadata["direct_urls"], list):
            urls.extend(request.metadata["direct_urls"])

        if not urls:
            return sources

        for idx, url in enumerate(urls, 1):
            clean_url = url.strip()
            if not clean_url:
                continue

            domain = SourceRegistry.normalize_domain(clean_url)
            src_id = f"src_direct_{idx}_{domain.replace('.', '_')}"
            sources.append(
                SourceDefinition(
                    source_id=src_id,
                    name=f"Direct URL: {domain}",
                    type=SourceType.WEBSITE,
                    base_url=clean_url,
                    domain=domain,
                    capabilities=[request.entity],
                    access_method=AccessMethod.HTTP,
                    status=SourceStatus.ACTIVE,
                    metadata={"direct_url": True},
                )
            )

        return sources
