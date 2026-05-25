"""add break glass admin mfa bypass flag

Revision ID: 20260525_01_break_glass_admin
Revises: 20260524_02
Create Date: 2026-05-25 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260525_01_break_glass_admin"
down_revision = "20260524_02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "admin_users",
        sa.Column(
            "mfa_bypass_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("admin_users", "mfa_bypass_enabled")
