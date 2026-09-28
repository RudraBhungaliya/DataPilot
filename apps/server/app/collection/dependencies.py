"""
Shared, process-wide collection engine singletons.

Endpoints and workflow executors must share the same SourceRegistry and
CollectionService so runtime state (e.g. blocked sources, in-memory jobs) is
consistent across the application instead of being duplicated per module.
"""

from functools import lru_cache

from app.collection.discovery.registry import SourceRegistry
from app.collection.discovery.discovery import SourceDiscovery
from app.collection.service import CollectionService


@lru_cache(maxsize=1)
def get_source_registry() -> SourceRegistry:
    """Returns the single shared SourceRegistry for the process."""
    return SourceRegistry()


@lru_cache(maxsize=1)
def get_collection_service() -> CollectionService:
    """Returns the single shared CollectionService (sharing the shared registry)."""
    registry = get_source_registry()
    discovery = SourceDiscovery(registry=registry)
    return CollectionService(registry=registry, discovery=discovery)
