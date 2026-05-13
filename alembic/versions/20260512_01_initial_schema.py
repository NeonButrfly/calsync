"""initial schema

Revision ID: 20260512_01
Revises:
Create Date: 2026-05-12 16:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260512_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("mfa_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("mfa_enrolled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recovery_codes_json", sa.Text(), nullable=True),
        sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_table(
        "app_state",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "provider_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider_type", sa.String(length=32), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("provider_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_type",
            "provider_account_id",
            name="uq_provider_accounts_provider_identity",
        ),
    )
    op.create_table(
        "provider_calendars",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider_account_pk", sa.String(length=36), nullable=False),
        sa.Column("provider_calendar_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("timezone", sa.String(length=64), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("provider_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_account_pk"],
            ["provider_accounts.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_account_pk",
            "provider_calendar_id",
            name="uq_provider_calendars_provider_identity",
        ),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider_type", sa.String(length=32), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column("provider_calendar_id", sa.String(length=255), nullable=False),
        sa.Column("provider_event_id", sa.String(length=255), nullable=False),
        sa.Column("provider_account_pk", sa.String(length=36), nullable=True),
        sa.Column("provider_calendar_pk", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("all_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="confirmed"),
        sa.Column("source_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["provider_account_pk"],
            ["provider_accounts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["provider_calendar_pk"],
            ["provider_calendars.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider_type",
            "provider_account_id",
            "provider_calendar_id",
            "provider_event_id",
            name="uq_events_provider_identity",
        ),
    )
    op.create_table(
        "published_feeds",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("scope_type", sa.String(length=32), nullable=False),
        sa.Column("scope_key", sa.String(length=255), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("feed_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope_type", "scope_key", name="uq_published_feeds_scope"),
        sa.UniqueConstraint("token"),
    )
    op.create_table(
        "sync_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("provider_account_pk", sa.String(length=36), nullable=True),
        sa.Column("provider_type", sa.String(length=32), nullable=False),
        sa.Column("trigger", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("events_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("events_upserted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_text", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["provider_account_pk"],
            ["provider_accounts.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("sync_logs")
    op.drop_table("published_feeds")
    op.drop_table("events")
    op.drop_table("provider_calendars")
    op.drop_table("provider_accounts")
    op.drop_table("app_state")
    op.drop_table("admin_users")
