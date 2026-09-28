"""
Source Registry.
Manages registered external data sources, domain normalization, and capability matching.
"""

from urllib.parse import urlparse
from typing import Dict, List, Optional
from app.collection.schemas import (
    SourceDefinition,
    SourceType,
    AccessMethod,
    SourceStatus,
    RateLimitConfig,
)
from app.core.logger import logger


class SourceRegistry:
    """
    Central registry for data providers, public endpoints, and websites.
    """

    def __init__(self, seed_defaults: bool = True):
        self._sources: Dict[str, SourceDefinition] = {}
        if seed_defaults:
            self._seed_default_sources()

    @staticmethod
    def normalize_domain(url_or_domain: str) -> str:
        """
        Normalizes domains consistently:
        e.g. 'https://www.example.com/jobs?q=1' -> 'example.com'
        """
        s = url_or_domain.strip().lower()
        if not s.startswith("http://") and not s.startswith("https://"):
            s = f"https://{s}"

        parsed = urlparse(s)
        netloc = parsed.netloc or parsed.path
        # Remove port
        domain = netloc.split(":")[0]
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]

        return domain.strip()

    def register(self, source: SourceDefinition) -> SourceDefinition:
        """
        Registers a source definition. Enforces domain normalization.
        """
        if not source.domain:
            source.domain = self.normalize_domain(source.base_url)

        # Check duplicate
        for existing in self._sources.values():
            if (
                existing.domain == source.domain
                and existing.base_url == source.base_url
                and existing.access_method == source.access_method
                and existing.source_id != source.source_id
            ):
                logger.info(f"Source already registered for {source.domain}: {existing.source_id}")
                return existing

        self._sources[source.source_id] = source
        logger.info(f"Registered source: {source.name} ({source.source_id}) for domain {source.domain}")
        return source

    def get(self, source_id: str) -> Optional[SourceDefinition]:
        """Retrieves source by ID."""
        if source_id in self._sources:
            return self._sources[source_id]
        for s in self._sources.values():
            if s.source_id == source_id or s.id == source_id:
                return s
        return None

    def list(self, status: Optional[SourceStatus] = None) -> List[SourceDefinition]:
        """Lists sources, optionally filtered by status."""
        sources = list(self._sources.values())
        if status:
            sources = [s for s in sources if s.status == status]
        return sources

    def find_by_domain(self, domain: str) -> List[SourceDefinition]:
        """Finds sources matching normalized domain."""
        norm = self.normalize_domain(domain)
        return [s for s in self._sources.values() if s.domain == norm]

    def find_by_capability(self, capability: str) -> List[SourceDefinition]:
        """Finds active sources that declare a specific capability or tag."""
        cap = capability.lower().strip()
        matched = []
        for s in self._sources.values():
            if s.status != SourceStatus.ACTIVE:
                continue
            caps = [c.lower().strip() for c in s.capabilities]
            if cap in caps or any(cap in c for c in caps):
                matched.append(s)
        return matched

    def disable(self, source_id: str) -> Optional[SourceDefinition]:
        """Marks a source as DISABLED."""
        src = self._sources.get(source_id)
        if src:
            src.status = SourceStatus.DISABLED
            logger.info(f"Source {source_id} marked as DISABLED")
        return src

    def mark_blocked(self, source_id: str) -> Optional[SourceDefinition]:
        """Marks a source as BLOCKED due to bot protection or access challenge."""
        src = self._sources.get(source_id)
        if src:
            src.status = SourceStatus.BLOCKED
            logger.warning(f"Source {source_id} marked as BLOCKED")
        return src

    def _seed_default_sources(self) -> None:
        """Seeds standard, pre-approved public sources."""
        default_sources = [
            SourceDefinition(
                source_id="src_startup_india",
                id="src_startup_india",
                name="Startup India Public Registry API",
                type=SourceType.API,
                base_url="https://api.startupindia.gov.in/v1/startups",
                domain="startupindia.gov.in",
                capabilities=["startup", "company", "funding", "india", "founder", "industry"],
                access_method=AccessMethod.API,
                rate_limit=RateLimitConfig(requests=100, period_seconds=60, min_interval=0.2),
                status=SourceStatus.ACTIVE,
                metadata={"auth_type": "none", "pagination_type": "page_number"},
            ),
            SourceDefinition(
                source_id="source_ycombinator_directory",
                id="source_ycombinator_directory",
                name="Y Combinator Companies Directory",
                type=SourceType.WEBSITE,
                base_url="https://www.ycombinator.com/companies",
                domain="ycombinator.com",
                capabilities=["startup", "company", "founders", "batch", "ai", "technology"],
                access_method=AccessMethod.HTTP,
                rate_limit=RateLimitConfig(requests=30, period_seconds=60, min_interval=1.0),
                status=SourceStatus.ACTIVE,
                metadata={"render_js": False},
            ),
            SourceDefinition(
                source_id="src_crunchbase_public",
                id="src_crunchbase_public",
                name="Crunchbase Public Directory",
                type=SourceType.WEBSITE,
                base_url="https://www.crunchbase.com/discover/organization.companies",
                domain="crunchbase.com",
                capabilities=["startup", "funding", "investor", "valuation", "company"],
                access_method=AccessMethod.HTTP,
                rate_limit=RateLimitConfig(requests=20, period_seconds=60, min_interval=1.5),
                status=SourceStatus.ACTIVE,
                metadata={"render_js": True},
            ),
            SourceDefinition(
                source_id="src_techcrunch_feed",
                id="src_techcrunch_feed",
                name="TechCrunch Startup Funding Feed",
                type=SourceType.RSS,
                base_url="https://techcrunch.com/category/startups/feed/",
                domain="techcrunch.com",
                capabilities=["startup", "funding", "investment", "fintech", "ai"],
                access_method=AccessMethod.HTTP,
                rate_limit=RateLimitConfig(requests=60, period_seconds=60, min_interval=0.5),
                status=SourceStatus.ACTIVE,
            ),
            SourceDefinition(
                source_id="src_linkedin_jobs",
                id="src_linkedin_jobs",
                name="LinkedIn Jobs Portal",
                type=SourceType.WEBSITE,
                base_url="https://www.linkedin.com/jobs/search",
                domain="linkedin.com",
                capabilities=["job_posting", "internship", "salary", "role", "location"],
                access_method=AccessMethod.HTTP,
                rate_limit=RateLimitConfig(requests=20, period_seconds=60, min_interval=2.0),
                status=SourceStatus.ACTIVE,
            ),
            SourceDefinition(
                source_id="src_github_api",
                id="src_github_api",
                name="GitHub Search API",
                type=SourceType.API,
                base_url="https://api.github.com/search/repositories",
                domain="github.com",
                capabilities=["repository", "code", "software", "open_source", "stars"],
                access_method=AccessMethod.API,
                rate_limit=RateLimitConfig(requests=60, period_seconds=60, min_interval=1.0),
                status=SourceStatus.ACTIVE,
                metadata={"pagination_type": "page_number"},
            ),
            SourceDefinition(
                source_id="source_hackernews_api",
                id="source_hackernews_api",
                name="HackerNews Firebase API",
                type=SourceType.API,
                base_url="https://news.ycombinator.com/api",
                domain="news.ycombinator.com",
                capabilities=["tech", "news", "startup", "developer"],
                access_method=AccessMethod.API,
                rate_limit=RateLimitConfig(requests=200, period_seconds=60, min_interval=0.1),
                status=SourceStatus.ACTIVE,
            ),
            SourceDefinition(
                source_id="src_wellfound",
                id="src_wellfound",
                name="Wellfound Startups & Jobs",
                type=SourceType.WEBSITE,
                base_url="https://wellfound.com/startups",
                domain="wellfound.com",
                capabilities=["startup", "job_posting", "funding", "roles"],
                access_method=AccessMethod.HTTP,
                rate_limit=RateLimitConfig(requests=30, period_seconds=60, min_interval=1.0),
                status=SourceStatus.ACTIVE,
            ),
        ]

        for s in default_sources:
            self.register(s)
