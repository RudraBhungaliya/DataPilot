"""
Search Discovery Provider Extension Point.
Provides a clean interface for integrating web search engines or external index APIs.
Does not require paid search API keys for MVP operation.
"""

from typing import List
from app.collection.discovery.base import BaseDiscoveryProvider
from app.collection.schemas import CollectionRequest, SourceDefinition
from app.core.logger import logger


class SearchDiscoveryProvider(BaseDiscoveryProvider):
    """
    Extension point for search-engine based dynamic discovery.
    """

    def __init__(self, api_key: str = None):
        self.api_key = api_key

    async def discover(self, request: CollectionRequest) -> List[SourceDefinition]:
        """
        Dynamic search discovery stub.
        In MVP, returns empty list unless external search engine is configured.
        """
        if not self.api_key:
            return []

        logger.info(f"SearchDiscoveryProvider queried for: {request.objective}")
        return []
