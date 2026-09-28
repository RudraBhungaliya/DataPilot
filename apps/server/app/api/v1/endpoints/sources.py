"""
Sources Endpoints.
Provides REST APIs for viewing and managing registered data sources and connectors.
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Query
from app.collection.schemas import SourceDefinition, SourceStatus
from app.collection.dependencies import get_source_registry
from app.core.logger import logger

router = APIRouter()
source_registry = get_source_registry()


@router.get(
    "",
    response_model=List[SourceDefinition],
    summary="List all registered sources",
    status_code=status.HTTP_200_OK,
)
async def list_sources(
    status_filter: Optional[SourceStatus] = Query(default=None, alias="status"),
) -> List[SourceDefinition]:
    """
    Returns registered sources with their domains, types, capabilities, and rate limit rules.
    """
    return source_registry.list(status=status_filter)


@router.post(
    "",
    response_model=SourceDefinition,
    summary="Register a new data source",
    status_code=status.HTTP_201_CREATED,
)
async def register_source(
    payload: SourceDefinition,
) -> SourceDefinition:
    """
    Adds a new data source or API to the central Source Registry.
    """
    try:
        registered = source_registry.register(payload)
        return registered
    except Exception as e:
        logger.error(f"Failed to register source: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Could not register source: {str(e)}",
        )


@router.get(
    "/{source_id}",
    response_model=SourceDefinition,
    summary="Get source details by ID",
    status_code=status.HTTP_200_OK,
)
async def get_source(
    source_id: str,
) -> SourceDefinition:
    """
    Retrieves a single source definition by its unique identifier.
    """
    src = source_registry.get(source_id)
    if not src:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source with ID '{source_id}' not found.",
        )
    return src
