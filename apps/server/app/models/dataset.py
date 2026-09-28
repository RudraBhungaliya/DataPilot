"""
Dataset Database Model.
Represents a compiled, validated, deduplicated dataset built from extracted records.
"""

import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import String, Text, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class Dataset(Base, TimestampMixin):
    """
    A dataset artifact produced by BUILD_DATASET for a workflow run.
    """
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"ds_{uuid.uuid4().hex[:12]}",
        index=True,
    )
    workflow_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    schema_fields: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    output_format: Mapped[str] = mapped_column(String(16), default="table", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="READY", nullable=False, index=True)
    record_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    def __repr__(self) -> str:
        return f"<Dataset id={self.id} entity={self.entity} records={self.record_count}>"
