"""
Source Collection Engine Module.
"""

from app.collection.schemas import (
    SourceType,
    AccessMethod,
    SourceStatus,
    JobStatus,
    RateLimitConfig,
    SourceDefinition,
    CollectionStrategy,
    CollectionLimits,
    CollectionRequest,
    DocumentReference,
    CollectionMetadata,
    CollectionResult,
    RawDocument,
)
from app.collection.policies import SourceAccessPolicy, AccessDeniedException
from app.collection.discovery.registry import SourceRegistry
from app.collection.discovery.discovery import SourceDiscovery
from app.collection.router import SourceRouter
from app.collection.collectors.base import BaseCollector, CollectorException, CaptchaChallengeDetected
from app.collection.collectors.http import HTTPCollector
from app.collection.collectors.api import APICollector
from app.collection.collectors.browser import BrowserCollector
from app.collection.collectors.zyte import ZyteAdapter
from app.collection.management.retry import RetryHandler, RetryableError, NonRetryableError
from app.collection.management.rate_limit import RateLimiter
from app.collection.management.pagination import PaginationHandler
from app.collection.management.cache import DocumentCache
from app.collection.storage.document_store import RawDocumentStore
from app.collection.manager import CollectionManager
from app.collection.service import CollectionService

__all__ = [
    "SourceType",
    "AccessMethod",
    "SourceStatus",
    "JobStatus",
    "RateLimitConfig",
    "SourceDefinition",
    "CollectionStrategy",
    "CollectionLimits",
    "CollectionRequest",
    "DocumentReference",
    "CollectionMetadata",
    "CollectionResult",
    "RawDocument",
    "SourceAccessPolicy",
    "AccessDeniedException",
    "SourceRegistry",
    "SourceDiscovery",
    "SourceRouter",
    "BaseCollector",
    "CollectorException",
    "CaptchaChallengeDetected",
    "HTTPCollector",
    "APICollector",
    "BrowserCollector",
    "ZyteAdapter",
    "RetryHandler",
    "RetryableError",
    "NonRetryableError",
    "RateLimiter",
    "PaginationHandler",
    "DocumentCache",
    "RawDocumentStore",
    "CollectionManager",
    "CollectionService",
]
