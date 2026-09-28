"""
Phase 5 Data Pipeline service.

Orchestrates extraction, normalization, validation, deduplication, dataset
building and export over the shared DataStore.
"""

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.collection.schemas import RawDocument
from app.core.logger import logger
from app.models.dataset import Dataset as DatasetORM
from app.pipeline.extraction import ExtractionEngine
from app.pipeline.schemas import ExtractionRecord, PipelineStats, DatasetStatus
from app.pipeline.stages import (
    mark_duplicates,
    normalize_records,
    records_to_csv,
    records_to_json,
    records_to_jsonl,
    validate_records,
)
from app.pipeline.store import DataStore

EXPORT_DIR = Path(__file__).resolve().parents[2] / "storage" / "exports"


class DataPipelineService:
    """Business logic for the Phase 5 data intelligence pipeline."""

    def __init__(
        self,
        store: Optional[DataStore] = None,
        extractor: Optional[ExtractionEngine] = None,
    ):
        self.store = store or DataStore()
        self.extractor = extractor or ExtractionEngine()

    # -- Stages -----------------------------------------------------------

    async def extract_records(
        self,
        workflow_id: str,
        entity: str,
        required_fields: List[str],
        documents: List[RawDocument],
        db: Optional[AsyncSession] = None,
    ) -> PipelineStats:
        records: List[ExtractionRecord] = []
        method_counts: Dict[str, int] = {}
        for document in documents:
            extracted = await self.extractor.extract_document(document, entity, required_fields)
            for record in extracted:
                method_counts[record.extraction_method] = method_counts.get(record.extraction_method, 0) + 1
            records.extend(extracted)

        await self.store.replace_records(workflow_id, records, db=db)
        logger.info(
            f"Extracted {len(records)} records from {len(documents)} documents "
            f"for workflow {workflow_id} (methods: {method_counts})"
        )
        return PipelineStats(
            documents_processed=len(documents),
            records_extracted=len(records),
            method_counts=method_counts,
        )

    async def normalize(self, workflow_id: str, db: Optional[AsyncSession] = None) -> PipelineStats:
        records = await self.store.list_records(workflow_id, db=db)
        count = normalize_records(records)
        await self.store.update_records(workflow_id, records, db=db)
        return PipelineStats(records_evaluated=len(records), records_normalized=count)

    async def validate(
        self,
        workflow_id: str,
        required_fields: List[str],
        filters: Optional[List[Dict[str, Any]]] = None,
        strict: bool = False,
        db: Optional[AsyncSession] = None,
    ) -> PipelineStats:
        records = await self.store.list_records(workflow_id, db=db)
        result = validate_records(records, required_fields, filters, strict=strict)
        await self.store.update_records(workflow_id, records, db=db)
        warnings = [
            f"{missing_count}/{len(records)} records missing '{field}'"
            for field, missing_count in result["missing_counts"].items()
        ]
        return PipelineStats(
            records_evaluated=len(records),
            records_valid=result["valid"],
            records_invalid=result["invalid"],
            mean_completeness=result["mean_completeness"],
            missing_counts=result["missing_counts"],
            warnings=warnings,
        )

    async def deduplicate(
        self,
        workflow_id: str,
        keys: List[str],
        match_threshold: float = 0.95,
        db: Optional[AsyncSession] = None,
    ) -> PipelineStats:
        records = await self.store.list_records(workflow_id, db=db)
        duplicates = mark_duplicates(records, keys, match_threshold)
        await self.store.update_records(workflow_id, records, db=db)
        return PipelineStats(records_evaluated=len(records), duplicates_removed=duplicates)

    async def build_dataset(
        self,
        workflow_id: str,
        entity: str,
        name: str,
        schema_fields: List[str],
        output_format: str = "table",
        db: Optional[AsyncSession] = None,
    ) -> DatasetORM:
        all_records = await self.store.list_records(workflow_id, db=db)
        selected = [r for r in all_records if r.is_valid and not r.is_duplicate]

        dataset_id = f"ds_{uuid.uuid4().hex[:12]}"
        for record in selected:
            record.dataset_id = dataset_id
        if selected:
            await self.store.update_records(workflow_id, selected, db=db)

        duplicates = sum(1 for r in all_records if r.is_duplicate)
        invalid = sum(1 for r in all_records if not r.is_valid)

        # Versioning: each rebuild for a workflow becomes a new version
        version = await self.store.next_dataset_version(workflow_id, db=db)
        await self.store.supersede_previous_versions(workflow_id, db=db)

        # Coverage: fraction of included records that actually provide each field
        coverage: Dict[str, float] = {}
        for field in (schema_fields or []):
            if selected:
                have = sum(1 for r in selected if r.data.get(field) not in (None, "", [], {}))
                coverage[field] = round(have / len(selected), 3)
            else:
                coverage[field] = 0.0
        mean_completeness = (
            round(sum(r.completeness for r in selected) / len(selected), 4) if selected else 0.0
        )

        dataset = DatasetORM(
            id=dataset_id,
            workflow_id=workflow_id,
            name=name or f"{entity} Dataset",
            entity=entity,
            description=f"{len(selected)} validated records for {entity}",
            schema_fields=schema_fields or [],
            output_format=output_format or "table",
            status=DatasetStatus.READY.value,
            version=version,
            is_latest=True,
            record_count=len(selected),
            valid_count=len(selected),
            duplicate_count=duplicates,
            metadata_={
                "total_records": len(all_records),
                "invalid_records": invalid,
                "duplicate_records": duplicates,
                "field_coverage": coverage,
                "mean_completeness": mean_completeness,
            },
        )
        await self.store.save_dataset(dataset, db=db)
        logger.info(f"Built dataset {dataset_id} with {len(selected)} records for workflow {workflow_id}")
        return dataset

    async def export_dataset(
        self,
        dataset_id: str,
        output_format: Optional[str] = None,
        db: Optional[AsyncSession] = None,
    ) -> Dict[str, Any]:
        dataset = await self.store.get_dataset(dataset_id, db=db)
        if dataset is None:
            raise ValueError(f"Dataset '{dataset_id}' not found.")

        fmt = (output_format or dataset.output_format or "json").lower()
        if fmt == "table":
            fmt = "json"
        if fmt not in ("csv", "json", "jsonl"):
            raise ValueError(f"Unsupported export format '{fmt}'. Use csv, json or jsonl.")
        records = await self.store.list_dataset_records(dataset_id, db=db, limit=100000)
        fields = dataset.schema_fields or []

        if fmt == "csv":
            content = records_to_csv(records, fields)
        elif fmt == "jsonl":
            content = records_to_jsonl(records, fields)
        else:
            content = records_to_json(records, fields)

        EXPORT_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{dataset.entity}_{dataset_id}.{fmt}"
        path = EXPORT_DIR / filename
        path.write_text(content, encoding="utf-8")

        return {
            "dataset_id": dataset_id,
            "format": fmt,
            "file_name": filename,
            "stored_at": str(path),
            "size_bytes": len(content.encode("utf-8")),
            "record_count": len(records),
        }

    # -- Queries ----------------------------------------------------------

    async def get_dataset(self, dataset_id: str, db: Optional[AsyncSession] = None) -> Optional[DatasetORM]:
        return await self.store.get_dataset(dataset_id, db=db)

    async def list_datasets(
        self,
        db: Optional[AsyncSession] = None,
        limit: int = 50,
        workflow_id: Optional[str] = None,
        latest_only: bool = False,
    ) -> List[DatasetORM]:
        return await self.store.list_datasets(
            db=db, limit=limit, workflow_id=workflow_id, latest_only=latest_only
        )

    async def list_dataset_records(
        self,
        dataset_id: str,
        db: Optional[AsyncSession] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ExtractionRecord]:
        return await self.store.list_dataset_records(dataset_id, db=db, limit=limit, offset=offset)

    async def query_dataset_records(
        self,
        dataset_id: str,
        db: Optional[AsyncSession] = None,
        q: Optional[str] = None,
        field: Optional[str] = None,
        value: Optional[str] = None,
        sort_field: Optional[str] = None,
        order: str = "asc",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, List[ExtractionRecord]]:
        return await self.store.query_dataset_records(
            dataset_id, db=db, q=q, field=field, value=value,
            sort_field=sort_field, order=order, limit=limit, offset=offset,
        )

    async def get_record(self, record_id: str, db: Optional[AsyncSession] = None) -> Optional[ExtractionRecord]:
        return await self.store.get_record(record_id, db=db)

    async def get_record_evidence(self, record_id: str, db: Optional[AsyncSession] = None) -> Optional[Dict[str, Any]]:
        """Builds the provenance chain for a record: record -> document -> source."""
        record = await self.store.get_record(record_id, db=db)
        if record is None:
            return None

        document: Optional[Any] = None
        if record.source_document_id:
            try:
                from app.collection.dependencies import get_collection_service
                document = await get_collection_service().get_document(record.source_document_id, db=db)
            except Exception as e:
                logger.warning(f"Could not load source document {record.source_document_id}: {e}")

        source: Optional[Any] = None
        if record.source_id:
            try:
                from app.collection.dependencies import get_source_registry
                src = get_source_registry().get(record.source_id)
                source = src.model_dump(mode="json") if src else None
            except Exception as e:
                logger.warning(f"Could not load source {record.source_id}: {e}")

        document_dict: Optional[Dict[str, Any]] = None
        if document is not None:
            document_dict = {
                "document_id": document.document_id,
                "url": document.url,
                "canonical_url": document.canonical_url,
                "content_type": document.content_type,
                "content_hash": document.content_hash,
                "status_code": document.status_code,
                "collected_at": document.collected_at.isoformat() if document.collected_at else None,
                "size_bytes": len(document.content.encode("utf-8")) if document.content else 0,
                "excerpt": (document.content or "")[:1000],
            }

        return {
            "record": record,
            "document": document_dict,
            "source": source,
        }

    async def list_workflow_records(
        self,
        workflow_id: str,
        db: Optional[AsyncSession] = None,
        valid_only: bool = False,
        include_duplicates: bool = True,
    ) -> List[ExtractionRecord]:
        return await self.store.list_records(
            workflow_id, db=db, valid_only=valid_only, include_duplicates=include_duplicates
        )
