"""add operator settings vault

Revision ID: 20260529_01
Revises: 20260528_01
Create Date: 2026-05-29 02:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260529_01"
down_revision = "20260528_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operator_settings",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value_encrypted", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    op.drop_table("operator_settings")
