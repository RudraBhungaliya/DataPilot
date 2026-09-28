"""
BackgroundJob Database Model.
Durable record of an asynchronously executed task.
"""

import secrets
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import String, Text, JSON, DateTime, Float, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class BackgroundJob(Base, TimestampMixin):
    """A queued/executed background task (workflow run, collection run, ...)."""
    __tablename__ = "background_jobs"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"task_{secrets.token_hex(6)}",
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="QUEUED", nullable=False, index=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<BackgroundJob id={self.id} kind={self.kind} status={self.status}>"
