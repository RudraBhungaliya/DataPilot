"""
ExtractedRecord Database Model.
Stores structured records extracted from raw documents, with full provenance
back to the source document and collection job.
"""

import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import String, Text, JSON, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class ExtractedRecord(Base, TimestampMixin):
    """
    A single structured record produced by the extraction pipeline.
    Carries provenance (document/source/url) and validation/dedupe state.
    """
    __tablename__ = "extracted_records"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"rec_{uuid.uuid4().hex[:12]}",
        index=True,
    )
    workflow_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    collection_job_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    document_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    source_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    entity: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    extraction_method: Mapped[str] = mapped_column(String(32), default="deterministic_json", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    validation_errors: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    missing_fields: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    completeness: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    dedupe_key: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, index=True)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    dataset_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    def __repr__(self) -> str:
        return f"<ExtractedRecord id={self.id} entity={self.entity} valid={self.is_valid}>"
