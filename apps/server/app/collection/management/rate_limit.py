"""
Domain and Source Rate Limiter.
Enforces per-domain concurrency limits, time-window quotas, and minimum request intervals.
"""

import asyncio
import time
from typing import Dict, Optional
from app.collection.schemas import RateLimitConfig
from app.core.config import settings
from app.core.logger import logger


class DomainRateLimiter:
    """
    State tracking for a single domain.
    """

    def __init__(self, domain: str, config: Optional[RateLimitConfig] = None):
        self.domain = domain
        self.config = config or RateLimitConfig(
            requests=settings.DATAPILOT_REQUESTS_PER_DOMAIN,
            period_seconds=60,
            min_interval=settings.DATAPILOT_MIN_REQUEST_INTERVAL,
            max_concurrency=2,
        )
        self.semaphore = asyncio.Semaphore(self.config.max_concurrency)
        self.last_request_time: float = 0.0
        self.request_timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """
        Acquires a concurrency slot and enforces rate limits before returning.
        Callers MUST call `release()` when finished (or use `acquire_context`).
        """
        await self.semaphore.acquire()
        try:
            await self.wait()
        except BaseException:
            self.semaphore.release()
            raise

    async def wait(self) -> None:
        """
        Enforces the sliding-window quota and minimum interval without holding
        a concurrency slot. Safe to call for pure rate limiting.
        """
        async with self._lock:
            now = time.monotonic()

            # 1. Clean up timestamps outside the sliding period window
            window_start = now - self.config.period_seconds
            self.request_timestamps = [t for t in self.request_timestamps if t > window_start]

            # 2. If quota exceeded, sleep until oldest timestamp expires
            if len(self.request_timestamps) >= self.config.requests:
                sleep_needed = (self.request_timestamps[0] + self.config.period_seconds) - now
                if sleep_needed > 0:
                    logger.info(f"Rate limit reached for domain '{self.domain}'. Pausing for {sleep_needed:.2f}s")
                    await asyncio.sleep(sleep_needed)
                    now = time.monotonic()

            # 3. Enforce minimum interval between consecutive requests
            elapsed_since_last = now - self.last_request_time
            if elapsed_since_last < self.config.min_interval:
                pause = self.config.min_interval - elapsed_since_last
                await asyncio.sleep(pause)
                now = time.monotonic()

            self.last_request_time = now
            self.request_timestamps.append(now)

    def release(self) -> None:
        """
        Releases concurrency semaphore.
        """
        self.semaphore.release()


class RateLimiter:
    """
    Global registry of domain rate limiters.
    """

    def __init__(
        self,
        max_per_period: Optional[int] = None,
        period_seconds: Optional[float] = None,
        default_config: Optional[RateLimitConfig] = None,
    ):
        self._limiters: Dict[str, DomainRateLimiter] = {}
        self._global_lock = asyncio.Lock()
        if max_per_period is not None or period_seconds is not None:
            self.default_config = RateLimitConfig(
                requests=max_per_period or 60,
                period_seconds=float(period_seconds if period_seconds is not None else 60.0),
                min_interval=0.0,
                max_concurrency=10,
            )
        else:
            self.default_config = default_config

    async def get_limiter(self, domain: str, config: Optional[RateLimitConfig] = None) -> DomainRateLimiter:
        dom = domain.lower().strip()
        effective_cfg = config or self.default_config
        if dom not in self._limiters:
            async with self._global_lock:
                if dom not in self._limiters:
                    self._limiters[dom] = DomainRateLimiter(dom, effective_cfg)
        return self._limiters[dom]

    async def acquire(self, domain: str, config: Optional[RateLimitConfig] = None) -> None:
        """
        Applies rate limiting for a domain WITHOUT holding a concurrency slot.
        Use `acquire_context(...)` when concurrency must also be bounded.
        """
        limiter = await self.get_limiter(domain, config)
        await limiter.wait()

    def acquire_context(self, domain: str, config: Optional[RateLimitConfig] = None):
        """
        Returns an async context manager for safe acquire & release.
        """
        limiter_mgr = self

        class _Context:
            async def __aenter__(self):
                limiter = await limiter_mgr.get_limiter(domain, config)
                self.limiter = limiter
                await limiter.acquire()
                return limiter

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                self.limiter.release()

        return _Context()
