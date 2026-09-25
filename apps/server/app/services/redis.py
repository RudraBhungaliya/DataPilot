import redis.asyncio as aioredis
from typing import Optional
from app.core.config import settings
from app.core.logger import logger

class RedisService:
    """Async Redis Service Foundation for caching, pub/sub, and task queue management."""
    _client: Optional[aioredis.Redis] = None

    @classmethod
    async def get_client(cls) -> Optional[aioredis.Redis]:
        if cls._client is None:
            try:
                cls._client = aioredis.from_url(
                    settings.redis_connection_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                )
            except Exception as e:
                logger.warning(f"Failed to create Redis client: {e}")
                return None
        return cls._client

    @classmethod
    async def close(cls):
        if cls._client is not None:
            await cls._client.aclose()
            cls._client = None
            logger.info("Redis client connection closed.")

    @classmethod
    async def check_connection(cls) -> bool:
        """Utility to ping Redis without raising unhandled exceptions."""
        try:
            client = await cls.get_client()
            if client is None:
                return False
            response = await client.ping()
            return bool(response)
        except Exception as e:
            logger.warning(f"Redis ping check failed (is Redis running?): {e}")
            return False

async def get_redis():
    """FastAPI dependency for accessing Redis."""
    client = await RedisService.get_client()
    try:
        yield client
    finally:
        pass
