"""
Security helpers: API key generation and hashing.

Raw API keys are never stored; only a SHA-256 hash plus a short display prefix.
"""

import hashlib
import secrets

API_KEY_PREFIX = "dp_"


def generate_api_key() -> str:
    """Generates a new, high-entropy API key."""
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_key(raw_key: str) -> str:
    """Returns the SHA-256 hex digest of an API key."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def key_display_prefix(raw_key: str) -> str:
    """A short, non-sensitive prefix suitable for display."""
    return raw_key[:10]


def constant_time_equals(a: str, b: str) -> bool:
    """Constant-time string comparison to avoid timing attacks."""
    return secrets.compare_digest(a or "", b or "")
