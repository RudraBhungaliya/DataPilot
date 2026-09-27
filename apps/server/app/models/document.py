"""
Raw Document Database Model.
Stores raw collected HTML, JSON, XML, or Text payloads along with provenance metadata.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Any, Dict
from sqlalchemy import String, Text, Integer, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class Document(Base, TimestampMixin):
    """
    Document model representing an immutable, raw collected artifact.
    Does NOT contain semantic extractions or normalized data.
    """
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"doc_{uuid.uuid4().hex[:12]}",
        index=True,
    )
    job_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(1024), nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(128), default="text/html", nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status_code: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    def __repr__(self) -> str:
        return f"<Document id={self.id} job_id={self.job_id} url='{self.url[:40]}' status={self.status_code}>"
