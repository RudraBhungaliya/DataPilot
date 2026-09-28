"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("parsed_requirement", sa.JSON(), nullable=True),
        sa.Column("workflow_definition", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("execution_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflows_id", "workflows", ["id"])
    op.create_index("ix_workflows_status", "workflows", ["status"])

    op.create_table(
        "sources",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("access_method", sa.String(length=32), nullable=False),
        sa.Column("rate_limit", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sources_domain", "sources", ["domain"])
    op.create_index("ix_sources_status", "sources", ["status"])

    op.create_table(
        "collection_jobs",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("workflow_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("collection_request", sa.JSON(), nullable=False),
        sa.Column("discovered_sources", sa.JSON(), nullable=False),
        sa.Column("selected_sources", sa.JSON(), nullable=False),
        sa.Column("source", sa.JSON(), nullable=True),
        sa.Column("current_step", sa.String(length=64), nullable=True),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
        sa.Column("human_action_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("human_action_reason", sa.String(length=128), nullable=True),
        sa.Column("checkpoint", sa.JSON(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_collection_jobs_request_id", "collection_jobs", ["request_id"])
    op.create_index("ix_collection_jobs_workflow_id", "collection_jobs", ["workflow_id"])
    op.create_index("ix_collection_jobs_status", "collection_jobs", ["status"])

    op.create_table(
        "documents",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=128), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_documents_job_id", "documents", ["job_id"])
    op.create_index("ix_documents_source_id", "documents", ["source_id"])
    op.create_index("ix_documents_canonical_url", "documents", ["canonical_url"])
    op.create_index("ix_documents_content_hash", "documents", ["content_hash"])
    op.create_index("ix_documents_collected_at", "documents", ["collected_at"])


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("collection_jobs")
    op.drop_table("sources")
    op.drop_table("workflows")
