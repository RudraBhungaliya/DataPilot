"""background jobs

Revision ID: 0006_background_jobs
Revises: 0005_api_keys
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0006_background_jobs"
down_revision: Union[str, None] = "0005_api_keys"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="QUEUED"),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_background_jobs_id", "background_jobs", ["id"])
    op.create_index("ix_background_jobs_kind", "background_jobs", ["kind"])
    op.create_index("ix_background_jobs_status", "background_jobs", ["status"])


def downgrade() -> None:
    op.drop_table("background_jobs")
