"""extraction quality columns (completeness, missing fields)

Revision ID: 0003_extraction_quality
Revises: 0002_phase5_datasets
Create Date: 2026-09-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_extraction_quality"
down_revision: Union[str, None] = "0002_phase5_datasets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "extracted_records",
        sa.Column("missing_fields", sa.JSON(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "extracted_records",
        sa.Column("completeness", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("extracted_records", "completeness")
    op.drop_column("extracted_records", "missing_fields")
