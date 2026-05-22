"""event trust and groups

Revision ID: 20260522_01
Revises: 20260514_01
Create Date: 2026-05-22 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260522_01"
down_revision = "20260514_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_groups",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("display_title", sa.String(length=255), nullable=False),
        sa.Column("preferred_starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("preferred_ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("preferred_location", sa.String(length=255), nullable=True),
        sa.Column("preferred_event_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["preferred_event_id"], ["events.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )

    with op.batch_alter_table("events") as batch_op:
        batch_op.add_column(
            sa.Column(
                "event_visibility_state",
                sa.String(length=32),
                nullable=False,
                server_default="active",
            )
        )
        batch_op.add_column(
            sa.Column("last_seen_upstream_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("removed_upstream_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("canonical_group_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_events_canonical_group_id_event_groups",
            "event_groups",
            ["canonical_group_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_check_constraint(
            "ck_events_visibility_state",
            "event_visibility_state IN ('active', 'cancelled', 'deleted_upstream', 'hidden_duplicate', 'stale_unverified')",
        )
        batch_op.create_check_constraint(
            "ck_events_active_not_removed",
            "event_visibility_state != 'active' OR removed_upstream_at IS NULL",
        )
        batch_op.create_check_constraint(
            "ck_events_deleted_requires_removed_at",
            "event_visibility_state != 'deleted_upstream' OR removed_upstream_at IS NOT NULL",
        )

    op.execute(
        sa.text(
            """
            UPDATE events
            SET last_seen_upstream_at = COALESCE(updated_at, created_at)
            WHERE last_seen_upstream_at IS NULL
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("events") as batch_op:
        batch_op.drop_constraint(
            "ck_events_deleted_requires_removed_at",
            type_="check",
        )
        batch_op.drop_constraint(
            "ck_events_active_not_removed",
            type_="check",
        )
        batch_op.drop_constraint("ck_events_visibility_state", type_="check")
        batch_op.drop_constraint("fk_events_canonical_group_id_event_groups", type_="foreignkey")
        batch_op.drop_column("canonical_group_id")
        batch_op.drop_column("removed_upstream_at")
        batch_op.drop_column("last_seen_upstream_at")
        batch_op.drop_column("event_visibility_state")

    op.drop_table("event_groups")
