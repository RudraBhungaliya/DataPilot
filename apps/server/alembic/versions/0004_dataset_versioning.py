"""dataset versioning

Revision ID: 0004_dataset_versioning
Revises: 0003_extraction_quality
Create Date: 2026-09-29
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_dataset_versioning"
down_revision: Union[str, None] = "0003_extraction_quality"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "datasets",
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "datasets",
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_datasets_is_latest", "datasets", ["is_latest"])


def downgrade() -> None:
    op.drop_index("ix_datasets_is_latest", table_name="datasets")
    op.drop_column("datasets", "is_latest")
    op.drop_column("datasets", "version")
