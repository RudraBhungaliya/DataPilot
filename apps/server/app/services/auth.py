"""
Authentication service: API key lifecycle management.

Persistence is database-first with an in-memory fallback (consistent with the
rest of the platform).
"""

import secrets
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.core.security import generate_api_key, hash_api_key, key_display_prefix
from app.models.api_key import ApiKey


class AuthService:
    """Creates, lists, revokes and verifies API keys."""

    def __init__(self) -> None:
        self._memory: Dict[str, ApiKey] = {}

    async def create_key(
        self, name: str, db: Optional[AsyncSession] = None
    ) -> Tuple[ApiKey, str]:
        """Creates a key and returns (record, raw_key). The raw key is shown only once."""
        raw_key = generate_api_key()
        record = ApiKey(
            id=f"key_{secrets.token_hex(6)}",
            name=name or "api-key",
            key_prefix=key_display_prefix(raw_key),
            key_hash=hash_api_key(raw_key),
            is_active=True,
        )
        self._memory[record.id] = record

        if db is not None:
            try:
                db.add(record)
                await db.commit()
                await db.refresh(record)
            except Exception as e:
                logger.warning(f"Could not persist API key {record.id}: {e}")
                await db.rollback()

        logger.info(f"Created API key '{record.name}' ({record.key_prefix}…)")
        return record, raw_key

    async def list_keys(self, db: Optional[AsyncSession] = None) -> List[ApiKey]:
        if db is not None:
            try:
                res = await db.execute(select(ApiKey).order_by(ApiKey.created_at.desc()))
                rows = list(res.scalars().all())
                if rows:
                    return rows
            except Exception as e:
                logger.warning(f"Could not list API keys: {e}")
        return list(self._memory.values())

    async def revoke_key(self, key_id: str, db: Optional[AsyncSession] = None) -> bool:
        record = self._memory.get(key_id)
        if db is not None:
            try:
                record = await db.get(ApiKey, key_id) or record
                if record is not None:
                    record.is_active = False
                    await db.commit()
                    return True
            except Exception as e:
                logger.warning(f"Could not revoke API key {key_id}: {e}")
                await db.rollback()
        if record is not None:
            record.is_active = False
            return True
        return False

    async def verify(self, raw_key: str, db: Optional[AsyncSession] = None) -> Optional[ApiKey]:
        """Returns the matching active key record, or None."""
        if not raw_key:
            return None
        key_hash = hash_api_key(raw_key)

        record: Optional[ApiKey] = None
        if db is not None:
            try:
                res = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))
                record = res.scalar_one_or_none()
            except Exception as e:
                logger.warning(f"Could not verify API key against DB: {e}")

        if record is None:
            for candidate in self._memory.values():
                if candidate.key_hash == key_hash:
                    record = candidate
                    break

        if record is None or not record.is_active:
            return None

        record.last_used_at = datetime.now(timezone.utc)
        return record


_auth_service: Optional[AuthService] = None


def get_auth_service() -> AuthService:
    global _auth_service
    if _auth_service is None:
        _auth_service = AuthService()
    return _auth_service
