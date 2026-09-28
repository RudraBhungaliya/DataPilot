"""
Phase 5 data store.

Persists extracted records and datasets. Uses an in-memory store as the
authoritative fallback and additionally persists to the database when a
session is provided.
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import select, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger
from app.models.dataset import Dataset as DatasetORM
from app.models.extracted_record import ExtractedRecord as ExtractedRecordORM
from app.pipeline.schemas import ExtractionRecord


def _to_domain(orm: ExtractedRecordORM) -> ExtractionRecord:
    return ExtractionRecord(
        record_id=orm.id,
        entity=orm.entity,
        data=orm.data or {},
        source_document_id=orm.document_id,
        source_id=orm.source_id,
        source_url=orm.source_url,
        collection_job_id=orm.collection_job_id,
        extraction_method=orm.extraction_method,
        confidence=orm.confidence or 0.0,
        is_valid=orm.is_valid,
        validation_errors=orm.validation_errors or [],
        missing_fields=orm.missing_fields or [],
        completeness=orm.completeness or 0.0,
        dedupe_key=orm.dedupe_key,
        is_duplicate=orm.is_duplicate,
        dataset_id=orm.dataset_id,
    )


def _to_orm(record: ExtractionRecord, workflow_id: Optional[str]) -> ExtractedRecordORM:
    return ExtractedRecordORM(
        id=record.record_id,
        workflow_id=workflow_id,
        collection_job_id=record.collection_job_id,
        document_id=record.source_document_id,
        source_id=record.source_id,
        source_url=record.source_url,
        entity=record.entity,
        data=record.data,
        extraction_method=record.extraction_method,
        confidence=record.confidence,
        is_valid=record.is_valid,
        validation_errors=record.validation_errors,
        missing_fields=record.missing_fields,
        completeness=record.completeness,
        dedupe_key=record.dedupe_key,
        is_duplicate=record.is_duplicate,
        dataset_id=record.dataset_id,
    )


class DataStore:
    """Records and datasets, backed by memory plus optional database persistence."""

    def __init__(self) -> None:
        self._records: Dict[str, Dict[str, ExtractionRecord]] = {}
        self._datasets: Dict[str, DatasetORM] = {}

    # -- Records ----------------------------------------------------------

    async def replace_records(
        self,
        workflow_id: str,
        records: List[ExtractionRecord],
        db: Optional[AsyncSession] = None,
    ) -> None:
        """Replaces all records for a workflow (idempotent re-runs)."""
        self._records[workflow_id] = {r.record_id: r for r in records}
        if db is None:
            return
        try:
            await db.execute(
                delete(ExtractedRecordORM).where(ExtractedRecordORM.workflow_id == workflow_id)
            )
            for record in records:
                db.add(_to_orm(record, workflow_id))
            await db.commit()
        except Exception as e:  # resilience: memory remains authoritative
            logger.warning(f"Could not persist extracted records for workflow {workflow_id}: {e}")
            await db.rollback()

    async def update_records(
        self,
        workflow_id: str,
        records: List[ExtractionRecord],
        db: Optional[AsyncSession] = None,
    ) -> None:
        """Updates already-stored records (normalize/validate/dedupe stages)."""
        bucket = self._records.setdefault(workflow_id, {})
        for record in records:
            bucket[record.record_id] = record
        if db is None:
            return
        try:
            for record in records:
                existing = await db.get(ExtractedRecordORM, record.record_id)
                if existing is None:
                    db.add(_to_orm(record, workflow_id))
                    continue
                existing.data = record.data
                existing.confidence = record.confidence
                existing.is_valid = record.is_valid
                existing.validation_errors = record.validation_errors
                existing.missing_fields = record.missing_fields
                existing.completeness = record.completeness
                existing.dedupe_key = record.dedupe_key
                existing.is_duplicate = record.is_duplicate
                existing.dataset_id = record.dataset_id
            await db.commit()
        except Exception as e:
            logger.warning(f"Could not update extracted records for workflow {workflow_id}: {e}")
            await db.rollback()

    async def list_records(
        self,
        workflow_id: str,
        db: Optional[AsyncSession] = None,
        valid_only: bool = False,
        include_duplicates: bool = True,
    ) -> List[ExtractionRecord]:
        records: List[ExtractionRecord] = []
        if db is not None:
            try:
                stmt = select(ExtractedRecordORM).where(ExtractedRecordORM.workflow_id == workflow_id)
                res = await db.execute(stmt)
                rows = res.scalars().all()
                if rows:
                    records = [_to_domain(row) for row in rows]
                    self._records[workflow_id] = {r.record_id: r for r in records}
            except Exception as e:
                logger.warning(f"Could not load extracted records for workflow {workflow_id}: {e}")

        if not records:
            records = list(self._records.get(workflow_id, {}).values())

        if valid_only:
            records = [r for r in records if r.is_valid]
        if not include_duplicates:
            records = [r for r in records if not r.is_duplicate]
        return records

    # -- Datasets ---------------------------------------------------------

    async def save_dataset(self, dataset: DatasetORM, db: Optional[AsyncSession] = None) -> DatasetORM:
        self._datasets[dataset.id] = dataset
        if db is not None:
            try:
                db.add(dataset)
                await db.commit()
                await db.refresh(dataset)
            except Exception as e:
                logger.warning(f"Could not persist dataset {dataset.id}: {e}")
                await db.rollback()
        return dataset

    async def get_dataset(self, dataset_id: str, db: Optional[AsyncSession] = None) -> Optional[DatasetORM]:
        if db is not None:
            try:
                found = await db.get(DatasetORM, dataset_id)
                if found is not None:
                    return found
            except Exception as e:
                logger.warning(f"Could not load dataset {dataset_id}: {e}")
        return self._datasets.get(dataset_id)

    async def list_datasets(
        self,
        db: Optional[AsyncSession] = None,
        limit: int = 50,
        workflow_id: Optional[str] = None,
        latest_only: bool = False,
    ) -> List[DatasetORM]:
        if db is not None:
            try:
                stmt = select(DatasetORM).order_by(desc(DatasetORM.created_at))
                if workflow_id:
                    stmt = stmt.where(DatasetORM.workflow_id == workflow_id)
                if latest_only:
                    stmt = stmt.where(DatasetORM.is_latest.is_(True))
                stmt = stmt.limit(limit)
                res = await db.execute(stmt)
                rows = res.scalars().all()
                if rows:
                    return list(rows)
            except Exception as e:
                logger.warning(f"Could not list datasets: {e}")

        datasets = list(self._datasets.values())
        if workflow_id:
            datasets = [d for d in datasets if d.workflow_id == workflow_id]
        if latest_only:
            datasets = [d for d in datasets if getattr(d, "is_latest", True)]
        return datasets[::-1][:limit]

    async def next_dataset_version(self, workflow_id: Optional[str], db: Optional[AsyncSession] = None) -> int:
        """Returns the next version number for a workflow's dataset lineage."""
        if not workflow_id:
            return 1
        existing = await self.list_datasets(db=db, limit=1000, workflow_id=workflow_id)
        versions = [getattr(d, "version", 1) or 1 for d in existing]
        return (max(versions) + 1) if versions else 1

    async def supersede_previous_versions(self, workflow_id: Optional[str], db: Optional[AsyncSession] = None) -> None:
        """Marks all prior datasets for a workflow as not latest."""
        if not workflow_id:
            return
        previous = await self.list_datasets(db=db, limit=1000, workflow_id=workflow_id)
        for dataset in previous:
            dataset.is_latest = False
        if db is not None and previous:
            try:
                await db.commit()
            except Exception as e:
                logger.warning(f"Could not supersede previous datasets for {workflow_id}: {e}")
                await db.rollback()

    async def _all_dataset_records(
        self, dataset_id: str, db: Optional[AsyncSession] = None
    ) -> List[ExtractionRecord]:
        if db is not None:
            try:
                stmt = select(ExtractedRecordORM).where(ExtractedRecordORM.dataset_id == dataset_id)
                res = await db.execute(stmt)
                rows = res.scalars().all()
                if rows:
                    return [_to_domain(row) for row in rows]
            except Exception as e:
                logger.warning(f"Could not load records for dataset {dataset_id}: {e}")

        matched: List[ExtractionRecord] = []
        for workflow_records in self._records.values():
            for record in workflow_records.values():
                if record.dataset_id == dataset_id:
                    matched.append(record)
        return matched

    async def list_dataset_records(
        self,
        dataset_id: str,
        db: Optional[AsyncSession] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ExtractionRecord]:
        records = await self._all_dataset_records(dataset_id, db=db)
        records.sort(key=lambda r: r.record_id)
        return records[offset : offset + limit]

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
        """Searches, filters, sorts and paginates a dataset's records. Returns (total, page)."""
        records = await self._all_dataset_records(dataset_id, db=db)

        if field and value is not None:
            needle = value.strip().lower()
            records = [
                r for r in records
                if str((r.data or {}).get(field, "")).strip().lower() == needle
            ]

        if q:
            needle = q.strip().lower()
            def _matches(record: ExtractionRecord) -> bool:
                for val in (record.data or {}).values():
                    if needle in str(val).lower():
                        return True
                return needle in (record.source_url or "").lower()
            records = [r for r in records if _matches(r)]

        if sort_field:
            def _sort_key(record: ExtractionRecord):
                val = (record.data or {}).get(sort_field)
                return (val is None, str(val).lower())
            records.sort(key=_sort_key, reverse=(order.lower() == "desc"))
        else:
            records.sort(key=lambda r: r.record_id)

        total = len(records)
        return total, records[offset : offset + limit]

    async def get_record(self, record_id: str, db: Optional[AsyncSession] = None) -> Optional[ExtractionRecord]:
        """Fetches a single extracted record by ID."""
        if db is not None:
            try:
                row = await db.get(ExtractedRecordORM, record_id)
                if row is not None:
                    return _to_domain(row)
            except Exception as e:
                logger.warning(f"Could not load record {record_id}: {e}")
        for bucket in self._records.values():
            if record_id in bucket:
                return bucket[record_id]
        return None

    def clear(self) -> None:
        self._records.clear()
        self._datasets.clear()
