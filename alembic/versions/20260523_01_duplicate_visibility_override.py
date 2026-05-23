"""persist duplicate visibility overrides

Revision ID: 20260523_01
Revises: 20260522_01
Create Date: 2026-05-23 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260523_01"
down_revision = "20260522_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("events") as batch_op:
        batch_op.add_column(
            sa.Column(
                "duplicate_visibility_override",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_column("duplicate_visibility_override")
