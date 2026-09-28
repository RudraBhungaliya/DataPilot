"""
Dataset Endpoints (Phase 5).
Exposes compiled datasets, their records, and export downloads.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from app.db.session import get_db
from app.pipeline.dependencies import get_data_service
from app.pipeline.schemas import ExtractionRecord
from app.core.logger import logger

router = APIRouter()
data_service = get_data_service()


class DatasetSummary(BaseModel):
    id: str
    workflow_id: Optional[str] = None
    name: str
    entity: str
    description: Optional[str] = None
    schema_fields: List[str] = Field(default_factory=list)
    output_format: str = "table"
    status: str = "READY"
    record_count: int = 0
    valid_count: int = 0
    duplicate_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[Any] = None
    updated_at: Optional[Any] = None


class DatasetRecord(BaseModel):
    record_id: str
    entity: str
    data: Dict[str, Any] = Field(default_factory=dict)
    source_document_id: Optional[str] = None
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    extraction_method: str = "deterministic_json"
    confidence: float = 0.0
    is_valid: bool = True
    validation_errors: List[str] = Field(default_factory=list)
    dedupe_key: Optional[str] = None
    is_duplicate: bool = False


class DatasetRecordsResponse(BaseModel):
    dataset_id: str
    total: int
    records: List[DatasetRecord]


def _serialize_dataset(ds) -> DatasetSummary:
    return DatasetSummary(
        id=ds.id,
        workflow_id=ds.workflow_id,
        name=ds.name,
        entity=ds.entity,
        description=ds.description,
        schema_fields=ds.schema_fields or [],
        output_format=ds.output_format,
        status=ds.status,
        record_count=ds.record_count,
        valid_count=ds.valid_count,
        duplicate_count=ds.duplicate_count,
        metadata=ds.metadata_ or {},
        created_at=ds.created_at.isoformat() if getattr(ds, "created_at", None) else None,
        updated_at=ds.updated_at.isoformat() if getattr(ds, "updated_at", None) else None,
    )


def _serialize_record(record: ExtractionRecord) -> DatasetRecord:
    return DatasetRecord(
        record_id=record.record_id,
        entity=record.entity,
        data=record.data,
        source_document_id=record.source_document_id,
        source_id=record.source_id,
        source_url=record.source_url,
        extraction_method=record.extraction_method,
        confidence=record.confidence,
        is_valid=record.is_valid,
        validation_errors=record.validation_errors,
        dedupe_key=record.dedupe_key,
        is_duplicate=record.is_duplicate,
    )


@router.get("", response_model=List[DatasetSummary], summary="List datasets", status_code=status.HTTP_200_OK)
async def list_datasets(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> List[DatasetSummary]:
    """Returns compiled datasets, most recent first."""
    datasets = await data_service.list_datasets(db=db, limit=limit)
    return [_serialize_dataset(ds) for ds in datasets]


@router.get("/{dataset_id}", response_model=DatasetSummary, summary="Get dataset details", status_code=status.HTTP_200_OK)
async def get_dataset(dataset_id: str, db: AsyncSession = Depends(get_db)) -> DatasetSummary:
    """Returns a single dataset's metadata and statistics."""
    dataset = await data_service.get_dataset(dataset_id, db=db)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dataset '{dataset_id}' not found.")
    return _serialize_dataset(dataset)


@router.get(
    "/{dataset_id}/records",
    response_model=DatasetRecordsResponse,
    summary="List dataset records",
    status_code=status.HTTP_200_OK,
)
async def get_dataset_records(
    dataset_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> DatasetRecordsResponse:
    """Returns the records contained in a dataset."""
    dataset = await data_service.get_dataset(dataset_id, db=db)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dataset '{dataset_id}' not found.")

    records = await data_service.list_dataset_records(dataset_id, db=db, limit=limit, offset=offset)
    return DatasetRecordsResponse(
        dataset_id=dataset_id,
        total=dataset.record_count,
        records=[_serialize_record(r) for r in records],
    )


@router.get(
    "/{dataset_id}/export/{output_format}",
    summary="Export a dataset as CSV or JSON",
    status_code=status.HTTP_200_OK,
)
async def export_dataset(
    dataset_id: str,
    output_format: str,
    db: AsyncSession = Depends(get_db),
):
    """Materializes and downloads a dataset in the requested format (csv|json)."""
    fmt = output_format.lower()
    if fmt not in ("csv", "json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported export format. Use 'csv' or 'json'.",
        )
    try:
        meta = await data_service.export_dataset(dataset_id=dataset_id, output_format=fmt, db=db)
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error(f"Dataset export failed for {dataset_id}: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Dataset export failed.")

    media_type = "text/csv" if fmt == "csv" else "application/json"
    return FileResponse(meta["stored_at"], media_type=media_type, filename=meta["file_name"])
