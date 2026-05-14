"""provider onboarding configuration and account secrets

Revision ID: 20260514_01
Revises: 20260512_01
Create Date: 2026-05-14 10:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260514_01"
down_revision = "20260512_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_configurations",
        sa.Column("provider_type", sa.String(length=64), nullable=False),
        sa.Column("public_config_json", sa.JSON(), nullable=True),
        sa.Column("secret_config_encrypted", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("provider_type"),
    )
    op.add_column(
        "provider_accounts",
        sa.Column("credential_secret_encrypted", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("provider_accounts", "credential_secret_encrypted")
    op.drop_table("provider_configurations")
