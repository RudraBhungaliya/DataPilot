"""
Source Access Policy.
Enforces technical, ethical, and legal access boundaries for data collection.
Ensures zero CAPTCHA-bypassing, respects robots.txt, allowed schemes, and source statuses.
"""

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from typing import Dict, Optional, Tuple
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

    def __init__(self):
        # Cache for parsed robots.txt: domain -> RobotFileParser
        self._robots_cache: Dict[str, Optional[RobotFileParser]] = {}

    def validate_url(self, url: str) -> Tuple[bool, str]:
        """
        Validates URL formatting, scheme, and presence of netloc.
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
        if not parsed.netloc:
            return False, "Missing host domain in URL"

        host = parsed.netloc.split(":")[0].lower()
        if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
            return False, f"Restricted host: {host}"

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
        Defaults to True if robots.txt cannot be parsed or is unavailable.
        """
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

        # For MVP resilience, non-blocking check
        # Real HTTP collector will populate or verify cache
        return True

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
