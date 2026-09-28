"""
Scheduled Task Database Model.
Recurring background job definitions (e.g. re-run a workflow every hour).
"""

import secrets
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class ScheduledTask(Base, TimestampMixin):
    """A recurring background job."""
    __tablename__ = "scheduled_tasks"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"sch_{secrets.token_hex(6)}",
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    interval_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ScheduledTask id={self.id} kind={self.kind} target={self.target_id}>"
