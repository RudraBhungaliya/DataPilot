"""
Shared API dependencies (authentication, etc.).
"""

from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import constant_time_equals
from app.db.session import get_db
from app.services.auth import get_auth_service


async def require_api_key(
    x_api_key: Optional[str] = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db),
):
    """
    Enforces API-key authentication when AUTH_ENABLED is on.

    A configured BOOTSTRAP_API_KEY is always accepted (for first-run provisioning).
    When AUTH_ENABLED is off the dependency is a no-op, so local development and
    the default test suite remain unauthenticated.
    """
    if not settings.AUTH_ENABLED:
        return None

    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Provide the X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if settings.BOOTSTRAP_API_KEY and constant_time_equals(x_api_key, settings.BOOTSTRAP_API_KEY):
        return None

    record = await get_auth_service().verify(x_api_key, db=db)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return record
