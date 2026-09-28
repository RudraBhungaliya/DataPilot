"""
Source Access Policy.
Enforces technical, ethical, and legal access boundaries for data collection.
Ensures zero CAPTCHA-bypassing, respects robots.txt, allowed schemes, and source statuses.
"""

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from typing import Dict, Optional, Tuple
import ipaddress
from app.collection.schemas import SourceDefinition, SourceStatus
from app.core.logger import logger
from app.core.config import settings


class AccessDeniedException(Exception):
    """Raised when accessing a target URL is prohibited by policy or robots.txt."""
    def __init__(self, url: str, reason: str):
        self.url = url
        self.reason = reason
        super().__init__(f"Access denied to '{url}': {reason}")


class SourceAccessPolicy:
    """
    Enforces compliance and validation rules before attempting any HTTP/API request.
    """

    ALLOWED_SCHEMES = {"http", "https"}

    # Hostnames that must never be fetched (cloud metadata endpoints, internal names)
    BLOCKED_HOSTNAMES = {
        "localhost",
        "metadata",
        "metadata.google.internal",
        "instance-data",
    }

    def __init__(self, robots_enforced: Optional[bool] = None):
        # Cache for parsed robots.txt: domain -> Optional[RobotFileParser]
        self._robots_cache: Dict[str, Optional[RobotFileParser]] = {}
        self.robots_enforced = settings.DATAPILOT_ROBOTS_ENFORCED if robots_enforced is None else robots_enforced

    @staticmethod
    def _is_blocked_ip(host: str) -> bool:
        """Returns True when `host` is a private, loopback, link-local, or reserved IP."""
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            return False
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        )

    def validate_url(self, url: str) -> Tuple[bool, str]:
        """
        Validates URL formatting, scheme, and presence of netloc.
        Blocks loopback, private, link-local and reserved hosts (SSRF protection).
        Returns (is_valid, error_reason).
        """
        s = url.strip()
        if not s:
            return False, "URL is empty"

        parsed = urlparse(s)
        if not parsed.scheme:
            return False, "Missing URL scheme (http/https)"
        if parsed.scheme.lower() not in self.ALLOWED_SCHEMES:
            return False, f"Unsupported scheme: '{parsed.scheme}'. Must be http or https."
        if not parsed.hostname:
            return False, "Missing host domain in URL"

        host = (parsed.hostname or "").lower()

        if host in self.BLOCKED_HOSTNAMES or host.endswith(".local"):
            return False, f"Restricted host: {host}"

        if self._is_blocked_ip(host):
            return False, f"Restricted private/internal IP address: {host}"

        return True, ""

    def check_source_status(self, source: SourceDefinition) -> None:
        """
        Ensures the source is currently permitted to be accessed.
        """
        if source.status == SourceStatus.DISABLED:
            raise AccessDeniedException(source.base_url, f"Source '{source.name}' ({source.source_id}) is marked DISABLED.")
        if source.status == SourceStatus.BLOCKED:
            raise AccessDeniedException(source.base_url, f"Source '{source.name}' ({source.source_id}) is marked BLOCKED due to access barrier.")

    def is_allowed(self, source: SourceDefinition) -> Tuple[bool, str]:
        """
        Checks whether source and its base URL are allowed by access policy.
        """
        if source.status != SourceStatus.ACTIVE:
            return False, f"Source is not active (status: {source.status.value})"
        valid, reason = self.validate_url(source.base_url)
        if not valid:
            return False, reason
        return True, ""

    def is_robots_allowed(self, url: str, user_agent: Optional[str] = None) -> bool:
        """
        Checks if robots.txt allows accessing this URL.

        When enforcement is disabled this is a no-op. When enabled, it consults
        the cached robots rules for the domain; if robots.txt has not been
        fetched the request is allowed (fail-open) until `ensure_robots` loads it.
        """
        if not self.robots_enforced:
            return True

        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        ua = user_agent or settings.DATAPILOT_HTTP_USER_AGENT

        if domain in self._robots_cache:
            parser = self._robots_cache[domain]
            if parser is None:
                return True
            try:
                return parser.can_fetch(ua, url)
            except Exception:
                return True

        # Not yet fetched -> allow; ensure_robots() will populate the cache first.
        return True

    async def ensure_robots(self, url: str, user_agent: Optional[str] = None, timeout: float = 2.0) -> None:
        """Fetches and caches robots.txt for the URL's domain (idempotent)."""
        if not self.robots_enforced:
            return

        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if not domain or domain in self._robots_cache:
            return

        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        ua = user_agent or settings.DATAPILOT_HTTP_USER_AGENT
        try:
            import httpx

            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                resp = await client.get(robots_url, headers={"User-Agent": ua})
                if resp.status_code == 200:
                    parser = RobotFileParser()
                    parser.parse(resp.text.splitlines())
                    self._robots_cache[domain] = parser
                else:
                    # No robots.txt (404/etc.) -> treat as allow-all
                    self._robots_cache[domain] = None
        except Exception as e:
            logger.debug(f"robots.txt fetch failed for {domain} (allowing): {e}")
            self._robots_cache[domain] = None

    def set_robots_rules(self, domain: str, robots_txt_content: str) -> None:
        """
        Parses and caches robots.txt content for a domain.
        """
        parser = RobotFileParser()
        parser.parse(robots_txt_content.splitlines())
        self._robots_cache[domain.lower()] = parser

    def check_all(self, url: str, source: Optional[SourceDefinition] = None) -> None:
        """
        Performs all pre-flight access policy verifications.
        """
        valid, reason = self.validate_url(url)
        if not valid:
            raise AccessDeniedException(url, reason)
        if source:
            self.check_source_status(source)
        if not self.is_robots_allowed(url):
            raise AccessDeniedException(url, "Disallowed by target website robots.txt policy")
