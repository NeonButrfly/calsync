"""add provider type to calendar connections

Revision ID: 20260529_02
Revises: 20260529_01
Create Date: 2026-05-29 03:55:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260529_02"
down_revision = "20260529_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "apple_calendar_connections",
        sa.Column(
            "provider_type",
            sa.String(length=32),
            nullable=False,
            server_default="icloud_caldav",
        ),
    )


def downgrade() -> None:
    op.drop_column("apple_calendar_connections", "provider_type")
