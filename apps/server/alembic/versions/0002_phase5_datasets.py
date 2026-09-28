"""phase 5 datasets and extracted records

Revision ID: 0002_phase5_datasets
Revises: 0001_initial
Create Date: 2026-09-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_phase5_datasets"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("workflow_id", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("entity", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schema_fields", sa.JSON(), nullable=False),
        sa.Column("output_format", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_datasets_id", "datasets", ["id"])
    op.create_index("ix_datasets_workflow_id", "datasets", ["workflow_id"])
    op.create_index("ix_datasets_entity", "datasets", ["entity"])
    op.create_index("ix_datasets_status", "datasets", ["status"])

    op.create_table(
        "extracted_records",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("workflow_id", sa.String(length=64), nullable=True),
        sa.Column("collection_job_id", sa.String(length=64), nullable=True),
        sa.Column("document_id", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("entity", sa.String(length=64), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("extraction_method", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("is_valid", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("validation_errors", sa.JSON(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=256), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("dataset_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_extracted_records_id", "extracted_records", ["id"])
    op.create_index("ix_extracted_records_workflow_id", "extracted_records", ["workflow_id"])
    op.create_index("ix_extracted_records_collection_job_id", "extracted_records", ["collection_job_id"])
    op.create_index("ix_extracted_records_document_id", "extracted_records", ["document_id"])
    op.create_index("ix_extracted_records_source_id", "extracted_records", ["source_id"])
    op.create_index("ix_extracted_records_entity", "extracted_records", ["entity"])
    op.create_index("ix_extracted_records_is_valid", "extracted_records", ["is_valid"])
    op.create_index("ix_extracted_records_dedupe_key", "extracted_records", ["dedupe_key"])
    op.create_index("ix_extracted_records_is_duplicate", "extracted_records", ["is_duplicate"])
    op.create_index("ix_extracted_records_dataset_id", "extracted_records", ["dataset_id"])


def downgrade() -> None:
    op.drop_table("extracted_records")
    op.drop_table("datasets")
