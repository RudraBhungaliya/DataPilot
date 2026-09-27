"""
Source Database Model.
Stores registered data providers, APIs, websites, and external feeds.
"""

import uuid
from typing import Optional, Any, Dict, List
from sqlalchemy import String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin


class Source(Base, TimestampMixin):
    """
    Source model representing an external data source or endpoint.
    """
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
        default=lambda: f"src_{uuid.uuid4().hex[:12]}",
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)  # api, website, dataset, rss, connector
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    capabilities: Mapped[List[str]] = mapped_column(JSON, default=list, nullable=False)
    access_method: Mapped[str] = mapped_column(String(32), default="http", nullable=False)  # api, http, browser, zyte
    rate_limit: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False, index=True)  # active, blocked, disabled, deprecated
    metadata_: Mapped[Dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)

    def __repr__(self) -> str:
        return f"<Source id={self.id} name='{self.name}' type={self.type} status={self.status}>"
