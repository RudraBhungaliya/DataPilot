"""
Source Discovery and Registry Module.
"""

from app.collection.discovery.registry import SourceRegistry
from app.collection.discovery.base import BaseDiscoveryProvider
from app.collection.discovery.registry_provider import RegistryDiscoveryProvider
from app.collection.discovery.direct_provider import DirectURLProvider
from app.collection.discovery.search_provider import SearchDiscoveryProvider
from app.collection.discovery.discovery import SourceDiscovery

__all__ = [
    "SourceRegistry",
    "BaseDiscoveryProvider",
    "RegistryDiscoveryProvider",
    "DirectURLProvider",
    "SearchDiscoveryProvider",
    "SourceDiscovery",
]
