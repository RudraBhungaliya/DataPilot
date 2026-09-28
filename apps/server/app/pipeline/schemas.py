"""
Phase 5 Data Intelligence domain schemas.

Pydantic models describing extracted records, pipeline statistics, and dataset
summaries used across the extraction/normalization/validation/dedup/build stages.
"""

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


def _record_id() -> str:
    return f"rec_{uuid.uuid4().hex[:12]}"


class ExtractionRecord(BaseModel):
    """A single structured record produced from a raw document."""
    record_id: str = Field(default_factory=_record_id)
    entity: str
    data: Dict[str, Any] = Field(default_factory=dict)
    source_document_id: Optional[str] = None
    source_id: Optional[str] = None
    source_url: Optional[str] = None
    collection_job_id: Optional[str] = None
    extraction_method: str = "deterministic_json"
    confidence: float = 0.5
    is_valid: bool = True
    validation_errors: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    completeness: float = 0.0
    dedupe_key: Optional[str] = None
    is_duplicate: bool = False
    dataset_id: Optional[str] = None


class DatasetStatus(str, Enum):
    BUILDING = "BUILDING"
    READY = "READY"
    FAILED = "FAILED"


class PipelineStats(BaseModel):
    """Counters reported by each pipeline stage."""
    documents_processed: int = 0
    records_extracted: int = 0
    records_normalized: int = 0
    records_enriched: int = 0
    records_evaluated: int = 0
    records_valid: int = 0
    records_invalid: int = 0
    duplicates_removed: int = 0
    records_in_dataset: int = 0
    mean_completeness: float = 0.0
    missing_counts: Dict[str, int] = Field(default_factory=dict)
    field_coverage: Dict[str, float] = Field(default_factory=dict)
    method_counts: Dict[str, int] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
