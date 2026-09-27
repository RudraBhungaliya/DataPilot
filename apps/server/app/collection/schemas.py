"""
Collection Engine Pydantic Schemas.
Defines strict schemas for collection requests, results, source definitions, and raw documents.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional, Any, Dict, Union
from pydantic import BaseModel, Field, field_validator


class SourceType(str, Enum):
    API = "api"
    WEBSITE = "website"
    DATASET = "dataset"
    RSS = "rss"
    CONNECTOR = "connector"


class AccessMethod(str, Enum):
    API = "api"
    HTTP = "http"
    BROWSER = "browser"
    ZYTE = "zyte"


class SourceStatus(str, Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"


class JobStatus(str, Enum):
    CREATED = "CREATED"
    DISCOVERING = "DISCOVERING"
    COLLECTING = "COLLECTING"
    COMPLETED = "COMPLETED"
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RateLimitConfig(BaseModel):
    requests: int = Field(default=60, ge=1, description="Max requests permitted per period")
    period_seconds: float = Field(default=60.0, ge=0.01, description="Time window in seconds")
    min_interval: float = Field(default=0.5, ge=0.0, description="Minimum pause between requests in seconds")
    max_concurrency: int = Field(default=2, ge=1, description="Max parallel connections to this source")


class SourceDefinition(BaseModel):
    """
    Representation of an external data source or platform.
    """
    source_id: str = Field(
        default_factory=lambda: f"src_{uuid.uuid4().hex[:12]}",
        description="Unique source identifier",
    )
    id: Optional[str] = Field(
        default=None,
        description="Alias for source_id",
    )
    name: str = Field(..., min_length=1, description="Human-readable source name")
    type: SourceType = Field(default=SourceType.WEBSITE, description="Type of source")
    base_url: str = Field(..., description="Base root URL or primary API endpoint")
    domain: Optional[str] = Field(None, description="Normalized domain name")
    capabilities: List[str] = Field(
        default_factory=list,
        description="Keywords/tags representing entities and fields this source can provide",
    )
    access_method: AccessMethod = Field(
        default=AccessMethod.HTTP,
        description="Method required to collect from this source",
    )
    rate_limit: RateLimitConfig = Field(
        default_factory=RateLimitConfig,
        description="Rate limiting constraints for this source",
    )
    status: SourceStatus = Field(
        default=SourceStatus.ACTIVE,
        description="Operational status of the source",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Source-specific parameters (auth templates, headers, pagination type, etc.)",
    )

    def model_post_init(self, __context: Any) -> None:
        if self.id:
            self.source_id = self.id
        elif self.source_id:
            self.id = self.source_id
        if not self.domain and self.base_url:
            self.domain = self._extract_domain(self.base_url)

    @staticmethod
    def _extract_domain(url: str) -> str:
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc or parsed.path
        netloc = netloc.split(":")[0].lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc

    @field_validator("name", "base_url")
    @classmethod
    def validate_non_empty(cls, v: str) -> str:
        s = v.strip()
        if not s:
            raise ValueError("Field must not be empty.")
        return s


class CollectionStrategy(BaseModel):
    allow_api: bool = True
    allow_web: bool = True
    allow_public_datasets: bool = True
    allow_rss: bool = True
    allow_zyte: bool = True


class CollectionLimits(BaseModel):
    max_sources: int = Field(default=10, ge=1, le=50)
    max_documents: int = Field(default=100, ge=1, le=1000)
    timeout_seconds: int = Field(default=60, ge=5, le=300)


class CollectionRequest(BaseModel):
    """
    Input request specifying what raw data needs to be collected.
    The user/workflow does NOT need to provide CSS selectors, scraping scripts, or browser commands.
    """
    request_id: str = Field(
        default_factory=lambda: f"colreq_{uuid.uuid4().hex[:12]}",
        description="Unique collection request identifier",
    )
    workflow_id: Optional[str] = Field(
        default=None,
        description="Associated workflow ID if initiated from a workflow",
    )
    objective: str = Field(..., min_length=1, description="High-level data collection goal")
    entity: str = Field(..., min_length=1, description="Target entity type, e.g. startup, job_posting")
    required_fields: List[str] = Field(
        default_factory=list,
        description="Target attributes to be gathered",
    )
    constraints: Dict[str, Any] = Field(
        default_factory=dict,
        description="Geographic, temporal, or filtering constraints",
    )
    source_preferences: List[str] = Field(
        default_factory=list,
        description="Preferred platforms or domains if mentioned",
    )
    collection_strategy: CollectionStrategy = Field(
        default_factory=CollectionStrategy,
        description="Allowed collection source types and methods",
    )
    limits: CollectionLimits = Field(
        default_factory=CollectionLimits,
        description="Limits on sources, documents, and execution time",
    )
    direct_urls: List[str] = Field(
        default_factory=list,
        description="Optional explicit URLs to collect if specified",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context metadata",
    )


class DocumentReference(BaseModel):
    """
    Lightweight reference to a raw document stored in RawDocumentStore.
    Avoids transmitting massive HTML/JSON strings in general API responses.
    """
    document_id: str
    source_id: str
    url: str
    canonical_url: str
    content_type: str
    status_code: int
    content_location: str
    content_hash: str
    collected_at: str
    size_bytes: int = 0
    collector: Optional[str] = None
    zyte_used: bool = False
    content: Optional[str] = None


class CollectionMetadata(BaseModel):
    sources_discovered: int = 0
    sources_used: int = 0
    pages_collected: int = 0
    documents_collected: int = 0
    failed_urls: int = 0
    duration_ms: int = 0
    zyte_used: bool = False
    zyte_used_count: int = 0
    alternative_sources_used: List[str] = Field(default_factory=list)
    blocked_sources: List[str] = Field(default_factory=list)
    inaccessible_sources: List[str] = Field(default_factory=list)
    successful_sources: List[str] = Field(default_factory=list)
    failed_sources: List[str] = Field(default_factory=list)


class CollectionResult(BaseModel):
    """
    Standard outcome returned by the Collection Engine.
    Contains document references and audit statistics.
    Does NOT contain extracted semantic entities.
    """
    job_id: str
    request_id: str
    status: str  # COMPLETED, PARTIAL_SUCCESS, FAILED
    documents: List[DocumentReference] = Field(default_factory=list)
    metadata: CollectionMetadata = Field(default_factory=CollectionMetadata)
    errors: List[Dict[str, Any]] = Field(default_factory=list)


class RawDocument(BaseModel):
    """
    In-memory representation of a collected raw document payload.
    """
    document_id: str = Field(
        default_factory=lambda: f"doc_{uuid.uuid4().hex[:12]}",
        description="Unique document identifier",
    )
    job_id: str = Field(default_factory=lambda: f"job_{uuid.uuid4().hex[:12]}")
    source_id: str = "source_unknown"
    url: str = ""
    canonical_url: str = ""
    content_type: str = "text/html"
    content: str = ""
    content_hash: Optional[str] = None
    status_code: int = 200
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        import hashlib
        if not self.content_hash and self.content is not None:
            self.content_hash = f"sha256:{hashlib.sha256(self.content.encode('utf-8')).hexdigest()}"
        if not self.canonical_url and self.url:
            self.canonical_url = self.url

    @property
    def id(self) -> str:
        return self.document_id

    def to_reference(self, content_location: str = "") -> DocumentReference:
        return DocumentReference(
            document_id=self.document_id,
            source_id=self.source_id,
            url=self.url,
            canonical_url=self.canonical_url or self.url,
            content_type=self.content_type,
            status_code=self.status_code,
            content_location=content_location or f"storage://documents/{self.document_id}",
            content_hash=self.content_hash or "",
            collected_at=self.collected_at.isoformat() if isinstance(self.collected_at, datetime) else str(self.collected_at),
            size_bytes=len(self.content.encode('utf-8')) if self.content else 0,
            collector=self.metadata.get("collector"),
            zyte_used=bool(self.metadata.get("zyte_used", False)),
            content=self.content,
        )
