"""
Rate limiting.

Redis-backed sliding-window counter with an in-process fallback, so the limiter
works in single-process development and scales across processes in production.
"""

import asyncio
import time
from collections import defaultdict, deque
from typing import Any, Deque, Dict

import redis.asyncio as aioredis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.logger import logger

# Redis clients are cached per running event loop to avoid cross-loop reuse.
_loop_clients: Dict[int, Any] = {}


async def _get_limiter_client():
    """Returns a Redis client bound to the current event loop, or None."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    key = id(loop)
    client = _loop_clients.get(key)
    if client is None:
        try:
            client = aioredis.from_url(
                settings.redis_connection_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=1.0,
            )
            _loop_clients[key] = client
        except Exception as e:
            logger.warning(f"Rate limiter could not create Redis client: {e}")
            return None
    return client


class _MemoryWindow:
    def __init__(self) -> None:
        self.hits: Dict[str, Deque[float]] = defaultdict(deque)


_memory = _MemoryWindow()


def client_identifier(request: Request) -> str:
    """Identifies a client by API key when present, otherwise by IP."""
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"key:{api_key[:16]}"
    host = request.client.host if request.client else "anonymous"
    return f"ip:{host}"


async def check_rate_limit(identifier: str, limit: int, window_seconds: int) -> bool:
    """Returns True if the request is allowed under the limit."""
    if limit <= 0:
        return True

    bucket = f"datapilot:rl:{identifier}"
    client = await _get_limiter_client()
    if client is not None:
        try:
            count = await client.incr(bucket)
            if count == 1:
                await client.expire(bucket, window_seconds)
            return int(count) <= limit
        except Exception as e:  # drop the broken client and fall back to memory
            logger.warning(f"Rate limiter Redis error, using memory fallback: {e}")
            try:
                key = id(asyncio.get_running_loop())
                _loop_clients.pop(key, None)
            except RuntimeError:
                pass

    now = time.monotonic()
    hits = _memory.hits[identifier]
    while hits and (now - hits[0]) > window_seconds:
        hits.popleft()
    if len(hits) >= limit:
        return False
    hits.append(now)
    return True


def reset_rate_limiter() -> None:
    _memory.hits.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Applies the configured per-client rate limit to API routes."""

    async def dispatch(self, request: Request, call_next):
        limit = settings.RATE_LIMIT_PER_MINUTE
        if limit > 0 and request.url.path.startswith("/api/"):
            identifier = client_identifier(request)
            allowed = await check_rate_limit(identifier, limit, settings.RATE_LIMIT_WINDOW_SECONDS)
            if not allowed:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Please retry later."},
                )
        return await call_next(request)
