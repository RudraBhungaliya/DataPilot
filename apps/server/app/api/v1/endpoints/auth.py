"""
Authentication Endpoints.
API-key lifecycle management. All endpoints require a valid key when AUTH_ENABLED.
"""

from typing import Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.auth import get_auth_service

router = APIRouter()


class CreateKeyRequest(BaseModel):
    name: str = Field(default="api-key", min_length=1, max_length=255)


class ApiKeyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    key_prefix: str
    is_active: bool
    created_at: Optional[Any] = None
    last_used_at: Optional[Any] = None


class CreateKeyResponse(ApiKeyResponse):
    api_key: str  # returned once at creation only


@router.post(
    "/keys",
    response_model=CreateKeyResponse,
    summary="Create a new API key",
    status_code=status.HTTP_201_CREATED,
)
async def create_key(
    payload: CreateKeyRequest,
    db: AsyncSession = Depends(get_db),
) -> CreateKeyResponse:
    """Creates an API key. The raw key is returned only once, at creation."""
    record, raw_key = await get_auth_service().create_key(payload.name, db=db)
    return CreateKeyResponse(
        id=record.id,
        name=record.name,
        key_prefix=record.key_prefix,
        is_active=record.is_active,
        created_at=record.created_at,
        last_used_at=record.last_used_at,
        api_key=raw_key,
    )


@router.get(
    "/keys",
    response_model=List[ApiKeyResponse],
    summary="List API keys",
    status_code=status.HTTP_200_OK,
)
async def list_keys(db: AsyncSession = Depends(get_db)) -> List[ApiKeyResponse]:
    """Lists API keys (without the secret material)."""
    records = await get_auth_service().list_keys(db=db)
    return [
        ApiKeyResponse(
            id=r.id,
            name=r.name,
            key_prefix=r.key_prefix,
            is_active=r.is_active,
            created_at=r.created_at,
            last_used_at=r.last_used_at,
        )
        for r in records
    ]


@router.delete(
    "/keys/{key_id}",
    summary="Revoke an API key",
    status_code=status.HTTP_200_OK,
)
async def revoke_key(key_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    """Deactivates an API key."""
    revoked = await get_auth_service().revoke_key(key_id, db=db)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"API key '{key_id}' not found.")
    return {"id": key_id, "is_active": False}
