"""provider roles and capabilities

Revision ID: 20260524_02
Revises: 20260523_01
Create Date: 2026-05-24 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from calsync.models.scheduling import calendar_role_check_constraint


revision = "20260524_02"
down_revision = "20260523_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("provider_accounts") as batch_op:
        batch_op.add_column(
            sa.Column(
                "auth_mode",
                sa.String(length=32),
                nullable=False,
                server_default="oauth",
            )
        )
        batch_op.add_column(
            sa.Column(
                "can_read",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "can_write",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column(
                "requires_reconnect",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    with op.batch_alter_table("provider_calendars") as batch_op:
        batch_op.add_column(
            sa.Column(
                "calendar_role",
                sa.String(length=32),
                nullable=False,
                server_default="personal_reference",
            )
        )
        batch_op.create_check_constraint(
            "ck_provider_calendars_calendar_role",
            calendar_role_check_constraint("calendar_role"),
        )


def downgrade() -> None:
    with op.batch_alter_table("provider_calendars") as batch_op:
        batch_op.drop_constraint("ck_provider_calendars_calendar_role", type_="check")
        batch_op.drop_column("calendar_role")

    with op.batch_alter_table("provider_accounts") as batch_op:
        batch_op.drop_column("requires_reconnect")
        batch_op.drop_column("can_write")
        batch_op.drop_column("can_read")
        batch_op.drop_column("auth_mode")
