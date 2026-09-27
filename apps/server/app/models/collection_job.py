"""
CollectionJob Database Model.
Tracks runtime state, metrics, and outcomes of a data collection job.
"""

import uuid
from datetime import datetime
from typing import Optional, Any, Dict, List
from sqlalchemy import String, Text, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class CollectionJob(Base, TimestampMixin):
    """
    CollectionJob model representing a source collection execution lifecycle.
    """
    __tablename__ = "collection_jobs"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"job_{uuid.uuid4().hex[:12]}",
        index=True,
    )
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    workflow_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), default="CREATED", nullable=False, index=True)
    collection_request: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    discovered_sources: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    selected_sources: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    errors: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)

    def __repr__(self) -> str:
        return f"<CollectionJob id={self.id} status={self.status} request_id={self.request_id}>"
