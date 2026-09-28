"""
Workflow Database Model.
Stores parsed workflow requirements and metadata.
"""

import uuid
from typing import Optional, Any, Dict
from sqlalchemy import String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class Workflow(Base, TimestampMixin):
    """Workflow model representing a data intelligence extraction specification."""
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_requirement: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    workflow_definition: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="PARSED", nullable=False, index=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<Workflow id={self.id} status={self.status}>"
