"""
Base Source Discovery Provider Interface.
"""

from abc import ABC, abstractmethod
from typing import List
from app.collection.schemas import CollectionRequest, SourceDefinition


class BaseDiscoveryProvider(ABC):
    """
    Abstract interface for source discovery providers.
    """

    @abstractmethod
    async def discover(self, request: CollectionRequest) -> List[SourceDefinition]:
        """
        Discovers sources eligible to fulfill the collection request.
        """
        pass
