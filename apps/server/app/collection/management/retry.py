"""
Retry Handler with Exponential Backoff.
Distinguishes between retryable transient errors and permanent failures.
"""

import asyncio
import random
from typing import Callable, Awaitable, TypeVar, Optional, Any
from app.core.logger import logger
from app.core.config import settings

T = TypeVar("T")


class RetryableError(Exception):
    """Marks an operation failure as safe to retry."""
    pass


class NonRetryableError(Exception):
    """Marks an operation failure as permanent (e.g. 404, invalid auth, CAPTCHA)."""
    pass


class RetryHandler:
    """
    Executes async callables with exponential backoff and jitter.
    """

    def __init__(
        self,
        max_retries: Optional[int] = None,
        base_delay: float = 0.5,
        max_delay: float = 8.0,
        factor: float = 2.0,
        jitter: bool = True,
        initial_delay: Optional[float] = None,
    ):
        self.max_retries = max_retries if max_retries is not None else settings.DATAPILOT_HTTP_MAX_RETRIES
        self.base_delay = initial_delay if initial_delay is not None else base_delay
        self.max_delay = max_delay
        self.factor = factor
        self.jitter = jitter

    async def execute(
        self,
        operation: Callable[[], Awaitable[T]],
        is_retryable: Optional[Callable[[Exception], bool]] = None,
        on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    ) -> T:
        """
        Executes operation with retries on transient errors.

        :param operation: Zero-arg async function
        :param is_retryable: Optional predicate to decide if an exception is retryable
        :param on_retry: Optional callback before sleep
        :return: Result of operation
        """
        attempt = 0
        while True:
            try:
                return await operation()
            except Exception as exc:
                attempt += 1

                # Check if error is retryable
                retryable = False
                if is_retryable:
                    retryable = is_retryable(exc)
                elif isinstance(exc, RetryableError):
                    retryable = True
                elif isinstance(exc, NonRetryableError):
                    retryable = False
                elif isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError)):
                    retryable = True

                if not retryable or attempt > self.max_retries:
                    raise exc

                # Compute exponential backoff
                delay = min(self.max_delay, self.base_delay * (self.factor ** (attempt - 1)))
                if self.jitter:
                    delay += random.uniform(0, 0.1 * delay)

                logger.warning(
                    f"Transient failure (attempt {attempt}/{self.max_retries}): {exc}. "
                    f"Retrying in {delay:.2f}s..."
                )

                if on_retry:
                    try:
                        on_retry(attempt, exc, delay)
                    except Exception:
                        pass

                await asyncio.sleep(delay)
