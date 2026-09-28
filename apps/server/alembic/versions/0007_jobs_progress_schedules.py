"""background job progress/cancellation + scheduled tasks

Revision ID: 0007_jobs_progress_schedules
Revises: 0006_background_jobs
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0007_jobs_progress_schedules"
down_revision: Union[str, None] = "0006_background_jobs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("background_jobs", sa.Column("progress", sa.Float(), nullable=False, server_default="0"))
    op.add_column(
        "background_jobs",
        sa.Column("cancel_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "scheduled_tasks",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_scheduled_tasks_id", "scheduled_tasks", ["id"])
    op.create_index("ix_scheduled_tasks_kind", "scheduled_tasks", ["kind"])
    op.create_index("ix_scheduled_tasks_target_id", "scheduled_tasks", ["target_id"])
    op.create_index("ix_scheduled_tasks_enabled", "scheduled_tasks", ["enabled"])


def downgrade() -> None:
    op.drop_table("scheduled_tasks")
    op.drop_column("background_jobs", "cancel_requested")
    op.drop_column("background_jobs", "progress")
