"""
Base Collector Interface and Collector Exceptions.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from app.collection.schemas import SourceDefinition, CollectionRequest, RawDocument


class CollectorException(Exception):
    """Base exception for collector operations."""
    def __init__(self, message: str, source_id: str = "unknown", url: str = "", status_code: Optional[int] = None):
        self.message = message
        self.source_id = source_id
        self.url = url
        self.status_code = status_code
        super().__init__(f"[{source_id}] {message} (url: {url}, status: {status_code})")

CollectorError = CollectorException


class CaptchaChallengeDetected(CollectorException):
    """
    Raised when an anti-bot challenge, Cloudflare turnstile, or CAPTCHA barrier is encountered.
    Collection Engine policy strictly prohibits attempting to bypass or solve CAPTCHAs.
    """
    def __init__(self, message: str = "CAPTCHA or bot challenge detected", source_id: str = "unknown", url: str = "", **kwargs):
        super().__init__(message=message, source_id=source_id, url=url, status_code=403)


class BaseCollector(ABC):
    """
    Abstract collector interface for fetching raw external documents.
    """

    @abstractmethod
    async def collect(
        self,
        source: SourceDefinition,
        request: CollectionRequest,
    ) -> List[RawDocument]:
        """
        Gathers raw documents from the specified source.

        :param source: Source metadata, base URL, and configuration
        :param request: High-level collection request specifying constraints and limits
        :return: List of immutable RawDocument instances
        """
        pass
