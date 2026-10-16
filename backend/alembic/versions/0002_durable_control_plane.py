"""Add durable tenant-scoped control-plane foundations.

This migration intentionally adds data structures only. Runtime migration from
the legacy in-memory demo store is an explicit deployment task; it must not
silently invent customer identity or trading state.
"""

from alembic import op
import sqlalchemy as sa

revision = "0002_durable_control_plane"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("version", sa.Numeric(10, 0), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_user_sessions_tenant_id", "user_sessions", ["tenant_id"])
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("session_id", sa.String(), sa.ForeignKey("user_sessions.id"), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False, unique=True),
        sa.Column("family_id", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"])
    op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"])
    op.create_table(
        "bot_instances",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("version", sa.Numeric(10, 0), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name"),
    )
    op.create_index("ix_bot_instances_tenant_id", "bot_instances", ["tenant_id"])
    op.create_table(
        "bot_user_assignments",
        sa.Column("bot_id", sa.String(), sa.ForeignKey("bot_instances.id"), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
    )
    for table_name, unique_fields in (("system_settings", ["tenant_id", "key"]), ("risk_settings", ["bot_id"])):
        columns = [
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
            sa.Column("bot_id", sa.String(), sa.ForeignKey("bot_instances.id"), nullable=False)
            if table_name == "risk_settings"
            else sa.Column("key", sa.String(), nullable=False),
            sa.Column("settings", sa.JSON(), nullable=False)
            if table_name == "risk_settings"
            else sa.Column("value", sa.JSON(), nullable=False),
            sa.Column("version", sa.Numeric(10, 0), nullable=False, server_default="1"),
            sa.Column("updated_by", sa.String()),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.UniqueConstraint(*unique_fields),
        ]
        op.create_table(table_name, *columns)
        op.create_index(f"ix_{table_name}_tenant_id", table_name, ["tenant_id"])
    op.create_table(
        "strategies",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("bot_id", sa.String(), sa.ForeignKey("bot_instances.id"), nullable=False),
        sa.Column("strategy_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("version", sa.Numeric(10, 0), nullable=False, server_default="1"),
        sa.Column("approved_by", sa.String()),
        sa.Column("mock_tested_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_strategies_tenant_id", "strategies", ["tenant_id"])
    op.create_index("ix_strategies_bot_id", "strategies", ["bot_id"])
    op.create_table(
        "ai_generated_strategies",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("requested_by", sa.String(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("prompt_redacted", sa.String(), nullable=False),
        sa.Column("draft", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("approved_by", sa.String()),
        sa.Column("mock_tested_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_generated_strategies_tenant_id", "ai_generated_strategies", ["tenant_id"])
    op.create_table(
        "audit_log_chain",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("sequence", sa.Numeric(20, 0), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=False),
        sa.Column("entry_hash", sa.String(length=64), nullable=False),
        sa.Column("event", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "sequence"),
    )
    op.create_index("ix_audit_log_chain_tenant_id", "audit_log_chain", ["tenant_id"])
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("payload_redacted", sa.JSON(), nullable=False),
        sa.Column("attempts", sa.Numeric(10, 0), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_tenant_id", "notifications", ["tenant_id"])
    op.create_table(
        "background_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id")),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_code", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_background_jobs_tenant_id", "background_jobs", ["tenant_id"])


def downgrade() -> None:
    for table_name in (
        "background_jobs",
        "notifications",
        "audit_log_chain",
        "ai_generated_strategies",
        "strategies",
        "risk_settings",
        "system_settings",
        "bot_user_assignments",
        "bot_instances",
        "refresh_tokens",
        "user_sessions",
        "tenants",
    ):
        op.drop_table(table_name)
