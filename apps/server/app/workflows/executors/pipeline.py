"""
Phase 5 pipeline step executors.

Replace the Phase 3 mock extractors for:
EXTRACT_DATA, NORMALIZE_DATA, VALIDATE_DATA, DEDUPLICATE_DATA,
BUILD_DATASET and EXPORT_DATA.
"""

from typing import Any, Dict, List, Optional

from app.collection.dependencies import get_collection_service
from app.collection.schemas import RawDocument
from app.core.logger import logger
from app.pipeline.dependencies import get_data_service
from app.workflows.executors.base import BaseStepExecutor, ExecutionContext, StepResult
from app.workflows.schemas import WorkflowStep


def _req(req: Any, name: str, default: Any = None) -> Any:
    """Reads an attribute from a StructuredRequirement or a plain dict."""
    if hasattr(req, name):
        return getattr(req, name)
    if isinstance(req, dict):
        return req.get(name, default)
    return default


def _filters_as_dicts(req: Any) -> List[Dict[str, Any]]:
    filters = _req(req, "filters", []) or []
    out: List[Dict[str, Any]] = []
    for rule in filters:
        if hasattr(rule, "model_dump"):
            out.append(rule.model_dump())
        elif isinstance(rule, dict):
            out.append(rule)
    return out


async def _resolve_documents(step: WorkflowStep, context: ExecutionContext) -> List[RawDocument]:
    """Locates the raw documents produced by the upstream COLLECT_DATA step."""
    job_id = step.metadata.get("job_id")
    collection_output: Optional[Dict[str, Any]] = None
    for dep_id in step.depends_on:
        dep_out = context.get_step_output(dep_id)
        if isinstance(dep_out, dict) and dep_out.get("job_id"):
            job_id = dep_out.get("job_id")
            collection_output = dep_out
            break

    documents: List[RawDocument] = []
    if job_id:
        try:
            documents = await get_collection_service().get_documents(
                job_id=job_id, limit=500, db=context.db
            )
        except Exception as err:
            logger.warning(f"Could not load documents for job {job_id}: {err}")

    if not documents and collection_output and isinstance(collection_output.get("documents"), list):
        for doc in collection_output["documents"]:
            try:
                documents.append(
                    RawDocument(
                        document_id=doc.get("document_id", ""),
                        job_id=doc.get("job_id") or job_id or "",
                        source_id=doc.get("source_id", ""),
                        url=doc.get("url", ""),
                        canonical_url=doc.get("canonical_url") or doc.get("url", ""),
                        content_type=doc.get("content_type", "text/html"),
                        content=doc.get("content") or "",
                        status_code=doc.get("status_code", 200),
                    )
                )
            except Exception:
                pass
    return documents


class ExtractionStepExecutor(BaseStepExecutor):
    """EXTRACT_DATA: documents -> structured records."""

    async def execute(self, step: WorkflowStep, context: ExecutionContext) -> StepResult:
        req = context.input_requirement
        entity = _req(req, "entity", "item")
        required_fields = _req(req, "required_fields", []) or []

        try:
            documents = await _resolve_documents(step, context)
            stats = await get_data_service().extract_records(
                workflow_id=context.workflow_id,
                entity=entity,
                required_fields=required_fields,
                documents=documents,
                db=context.db,
            )
            return StepResult(
                success=True,
                output={
                    "is_mock": False,
                    "documents_processed": stats.documents_processed,
                    "records_extracted": stats.records_extracted,
                    "method_counts": stats.method_counts,
                    "entity": entity,
                    "required_fields": required_fields,
                },
                metadata={"is_mock": False, "records_extracted": stats.records_extracted},
            )
        except Exception as e:
            logger.error(f"ExtractionStepExecutor failed: {e}", exc_info=True)
            return StepResult(success=False, error=f"Extraction failed: {str(e)}", metadata={"is_mock": False})


class NormalizeStepExecutor(BaseStepExecutor):
    """NORMALIZE_DATA: standardize keys/values."""

    async def execute(self, step: WorkflowStep, context: ExecutionContext) -> StepResult:
        try:
            stats = await get_data_service().normalize(context.workflow_id, db=context.db)
            return StepResult(
                success=True,
                output={
                    "is_mock": False,
                    "records_normalized": stats.records_normalized,
                    "records_evaluated": stats.records_evaluated,
                },
                metadata={"is_mock": False},
            )
        except Exception as e:
            logger.error(f"NormalizeStepExecutor failed: {e}", exc_info=True)
            return StepResult(success=False, error=f"Normalization failed: {str(e)}", metadata={"is_mock": False})


class ValidationStepExecutor(BaseStepExecutor):
    """VALIDATE_DATA: required-field and filter checks."""

    async def execute(self, step: WorkflowStep, context: ExecutionContext) -> StepResult:
        req = context.input_requirement
        required_fields = step.config.get("required_fields") or _req(req, "required_fields", []) or []
        filters = step.config.get("filters") or _filters_as_dicts(req)
        strict = bool(step.config.get("strict", False))

        try:
            stats = await get_data_service().validate(
                workflow_id=context.workflow_id,
                required_fields=required_fields,
                filters=filters,
                strict=strict,
                db=context.db,
            )
            return StepResult(
                success=True,
                output={
                    "is_mock": False,
                    "records_evaluated": stats.records_evaluated,
                    "records_valid": stats.records_valid,
                    "records_invalid": stats.records_invalid,
                    "rules_evaluated": len(required_fields) + len(filters),
                    "strict": strict,
                    "mean_completeness": stats.mean_completeness,
                    "missing_counts": stats.missing_counts,
                },
                metadata={"is_mock": False, "records_valid": stats.records_valid},
            )
        except Exception as e:
            logger.error(f"ValidationStepExecutor failed: {e}", exc_info=True)
            return StepResult(success=False, error=f"Validation failed: {str(e)}", metadata={"is_mock": False})


class DeduplicateStepExecutor(BaseStepExecutor):
    """DEDUPLICATE_DATA: composite-key deduplication."""

    async def execute(self, step: WorkflowStep, context: ExecutionContext) -> StepResult:
        req = context.input_requirement
        keys = step.config.get("deduplication_keys") or _req(req, "required_fields", [])[:2] or ["id"]
        threshold = float(step.config.get("match_threshold", 0.95))

        try:
            stats = await get_data_service().deduplicate(
                workflow_id=context.workflow_id,
                keys=keys,
                match_threshold=threshold,
                db=context.db,
            )
            return StepResult(
                success=True,
                output={
                    "is_mock": False,
                    "records_evaluated": stats.records_evaluated,
                    "duplicates_removed": stats.duplicates_removed,
                    "deduplication_keys_used": keys,
                },
                metadata={"is_mock": False},
            )
        except Exception as e:
            logger.error(f"DeduplicateStepExecutor failed: {e}", exc_info=True)
            return StepResult(success=False, error=f"Deduplication failed: {str(e)}", metadata={"is_mock": False})


class BuildDatasetStepExecutor(BaseStepExecutor):
    """BUILD_DATASET: compile valid, unique records into a dataset."""

    async def execute(self, step: WorkflowStep, context: ExecutionContext) -> StepResult:
        req = context.input_requirement
        entity = _req(req, "entity", "item")
        schema_fields = step.config.get("schema_fields") or _req(req, "required_fields", []) or []
        output_format = step.config.get("output_format") or "table"

        try:
            dataset = await get_data_service().build_dataset(
                workflow_id=context.workflow_id,
                entity=entity,
                name=f"{str(entity).replace('_', ' ').title()} Dataset",
                schema_fields=schema_fields,
                output_format=output_format,
                db=context.db,
            )
            return StepResult(
                success=True,
                output={
                    "is_mock": False,
                    "dataset_id": dataset.id,
                    "entity": entity,
                    "record_count": dataset.record_count,
                    "schema_fields": schema_fields,
                    "status": dataset.status,
                    "field_coverage": (dataset.metadata_ or {}).get("field_coverage", {}),
                    "mean_completeness": (dataset.metadata_ or {}).get("mean_completeness", 0.0),
                },
                metadata={"is_mock": False, "dataset_id": dataset.id, "record_count": dataset.record_count},
            )
        except Exception as e:
            logger.error(f"BuildDatasetStepExecutor failed: {e}", exc_info=True)
            return StepResult(success=False, error=f"Dataset build failed: {str(e)}", metadata={"is_mock": False})


class ExportStepExecutor(BaseStepExecutor):
    """EXPORT_DATA: materialize a dataset as CSV/JSON."""

    async def execute(self, step: WorkflowStep, context: ExecutionContext) -> StepResult:
        dataset_id = step.metadata.get("dataset_id")
        if not dataset_id:
            for dep_id in step.depends_on:
                dep_out = context.get_step_output(dep_id)
                if isinstance(dep_out, dict) and dep_out.get("dataset_id"):
                    dataset_id = dep_out["dataset_id"]
                    break

        if not dataset_id:
            return StepResult(success=False, error="No dataset available to export.", metadata={"is_mock": False})

        output_format = step.config.get("format", "json")
        try:
            result = await get_data_service().export_dataset(
                dataset_id=dataset_id, output_format=output_format, db=context.db
            )
            return StepResult(
                success=True,
                output={"is_mock": False, **result},
                metadata={"is_mock": False, "dataset_id": dataset_id},
            )
        except Exception as e:
            logger.error(f"ExportStepExecutor failed: {e}", exc_info=True)
            return StepResult(success=False, error=f"Export failed: {str(e)}", metadata={"is_mock": False})
