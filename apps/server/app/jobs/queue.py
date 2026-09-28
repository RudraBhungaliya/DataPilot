"""
Background job queue.

Redis list when available (multi-process), in-process queue otherwise.
Clients are cached per event loop to avoid cross-loop reuse.
"""

import asyncio
from typing import Any, Dict, Optional

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logger import logger

QUEUE_KEY = "datapilot:jobs:queue"

_clients: Dict[int, Any] = {}
_mem_queues: Dict[int, "asyncio.Queue[str]"] = {}


def _loop_key() -> Optional[int]:
    try:
        return id(asyncio.get_running_loop())
    except RuntimeError:
        return None


async def _redis():
    key = _loop_key()
    if key is None:
        return None
    client = _clients.get(key)
    if client is None:
        try:
            client = aioredis.from_url(
                settings.redis_connection_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=1.0,
            )
            _clients[key] = client
        except Exception as e:
            logger.warning(f"Job queue Redis unavailable: {e}")
            return None
    return client


def _mem_queue() -> "asyncio.Queue[str]":
    key = _loop_key() or 0
    queue = _mem_queues.get(key)
    if queue is None:
        queue = asyncio.Queue()
        _mem_queues[key] = queue
    return queue


async def enqueue(job_id: str) -> None:
    """Pushes a job id onto the queue."""
    client = await _redis()
    if client is not None:
        try:
            await client.lpush(QUEUE_KEY, job_id)
            return
        except Exception as e:
            logger.warning(f"Job enqueue via Redis failed, using memory: {e}")
    _mem_queue().put_nowait(job_id)


async def dequeue(timeout: float = 1.0) -> Optional[str]:
    """Pops the next job id, or None on timeout."""
    client = await _redis()
    if client is not None:
        try:
            res = await client.brpop(QUEUE_KEY, timeout=max(1, int(timeout)))
            if res:
                return res[1]
            return None
        except Exception as e:
            logger.warning(f"Job dequeue via Redis failed, using memory: {e}")

    try:
        return await asyncio.wait_for(_mem_queue().get(), timeout=timeout)
    except asyncio.TimeoutError:
        return None


async def queue_depth() -> int:
    """Best-effort queue depth for monitoring."""
    client = await _redis()
    if client is not None:
        try:
            return int(await client.llen(QUEUE_KEY))
        except Exception:
            pass
    return _mem_queue().qsize()
