"""
Source Router.
Deterministically maps SourceDefinitions to the appropriate collector implementation.
"""

from typing import Optional
from app.collection.schemas import SourceDefinition, SourceType, AccessMethod
from app.collection.collectors.base import BaseCollector
from app.collection.collectors.http import HTTPCollector
from app.collection.collectors.api import APICollector
from app.collection.collectors.browser import BrowserCollector
from app.collection.collectors.zyte import ZyteAdapter
from app.core.logger import logger


class SourceRouter:
    """
    Deterministic routing engine matching sources to collectors.
    """

    def __init__(
        self,
        http_collector: Optional[HTTPCollector] = None,
        api_collector: Optional[APICollector] = None,
        browser_collector: Optional[BrowserCollector] = None,
        zyte_adapter: Optional[ZyteAdapter] = None,
    ):
        self.http_collector = http_collector or HTTPCollector()
        self.api_collector = api_collector or APICollector()
        self.browser_collector = browser_collector or BrowserCollector()
        self.zyte_adapter = zyte_adapter or ZyteAdapter()

    def route(self, source: SourceDefinition) -> BaseCollector:
        """
        Determines and returns the collector for a given source.
        Priority:
        1. API (if access_method is api or source type is api)
        2. Browser (if explicit JS-rendering required or access_method is browser)
        3. Zyte (if access_method is zyte)
        4. HTTP (default public web collector)
        """
        if source.access_method == AccessMethod.API or source.type == SourceType.API:
            logger.debug(f"SourceRouter: Routed {source.source_id} to APICollector")
            return self.api_collector

        if (
            source.access_method == AccessMethod.BROWSER
            or source.metadata.get("render_js") is True
            or source.metadata.get("requires_browser") is True
        ):
            logger.debug(f"SourceRouter: Routed {source.source_id} to BrowserCollector")
            return self.browser_collector

        if source.access_method == AccessMethod.ZYTE:
            logger.debug(f"SourceRouter: Routed {source.source_id} to ZyteAdapter")
            return self.zyte_adapter

        logger.debug(f"SourceRouter: Routed {source.source_id} to HTTPCollector")
        return self.http_collector

    async def aclose(self) -> None:
        """Closes all collector network clients."""
        await self.http_collector.aclose()
        await self.api_collector.aclose()
        await self.browser_collector.aclose()
        await self.zyte_adapter.aclose()
