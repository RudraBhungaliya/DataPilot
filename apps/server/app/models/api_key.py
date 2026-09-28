"""
API Key Database Model.
Stores hashed API keys for authenticating clients. Raw keys are never persisted.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class ApiKey(Base, TimestampMixin):
    """A hashed API key belonging to a client or service."""
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"key_{uuid.uuid4().hex[:12]}",
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<ApiKey id={self.id} name='{self.name}' active={self.is_active}>"
