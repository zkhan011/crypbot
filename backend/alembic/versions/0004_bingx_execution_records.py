"""Add durable BingX execution and reconciliation records."""

from alembic import op
import sqlalchemy as sa

revision = "0004_bingx_execution_records"
down_revision = "0003_exchange_credentials"
branch_labels = None
depends_on = None


def tenant_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "account_states",
        *tenant_columns(),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("environment", sa.String(), nullable=False),
        sa.Column("product", sa.String(), nullable=False),
        sa.Column("state", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "account_id", "environment", "product"),
    )
    op.create_table(
        "market_snapshots",
        *tenant_columns(),
        sa.Column("product", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "trading_rule_snapshots",
        *tenant_columns(),
        sa.Column("product", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("rules", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "source_trade_events",
        *tenant_columns(),
        sa.Column("source_event_id", sa.String(), nullable=False),
        sa.Column("leader_id", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "leader_id", "source_event_id"),
    )
    op.create_table(
        "copy_allocations",
        *tenant_columns(),
        sa.Column("source_event_id", sa.String(), nullable=False),
        sa.Column("follower_account_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(38, 18), nullable=False),
        sa.Column("filled_quantity", sa.Numeric(38, 18), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False),
        sa.UniqueConstraint("tenant_id", "source_event_id", "follower_account_id", "symbol"),
    )
    op.create_table(
        "order_intents",
        *tenant_columns(),
        sa.Column("bot_id", sa.String(), sa.ForeignKey("bot_instances.id"), nullable=False),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("environment", sa.String(), nullable=False),
        sa.Column("product", sa.String(), nullable=False),
        sa.Column("strategy", sa.String(), nullable=False),
        sa.Column("source_event_id", sa.String()),
        sa.Column("client_order_id", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("requested", sa.JSON(), nullable=False),
        sa.Column("normalized", sa.JSON()),
        sa.Column("validation", sa.JSON()),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("retry_state", sa.String(), nullable=False, server_default="NONE"),
        sa.Column("reconciliation_state", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "account_id", "client_order_id"),
    )
    op.create_table(
        "exchange_orders",
        *tenant_columns(),
        sa.Column("order_intent_id", sa.String(), sa.ForeignKey("order_intents.id"), nullable=False),
        sa.Column("exchange_order_id", sa.String()),
        sa.Column("position_id", sa.String()),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("filled_quantity", sa.Numeric(38, 18), nullable=False, server_default="0"),
        sa.Column("average_fill_price", sa.Numeric(38, 18)),
        sa.Column("raw_redacted", sa.JSON(), nullable=False),
        sa.Column("exchange_updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "exchange_order_id"),
    )
    op.create_table(
        "order_fills",
        *tenant_columns(),
        sa.Column("exchange_order_id", sa.String(), sa.ForeignKey("exchange_orders.id"), nullable=False),
        sa.Column("exchange_fill_id", sa.String(), nullable=False),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("price", sa.Numeric(38, 18), nullable=False),
        sa.Column("quantity", sa.Numeric(38, 18), nullable=False),
        sa.Column("fee", sa.Numeric(38, 18), nullable=False, server_default="0"),
        sa.Column("fee_asset", sa.String()),
        sa.Column("maker", sa.Boolean()),
        sa.Column("filled_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "exchange_fill_id"),
    )
    op.create_table(
        "position_snapshots",
        *tenant_columns(),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("product", sa.String(), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("position_id", sa.String()),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "volume_sessions",
        *tenant_columns(),
        sa.Column("bot_id", sa.String(), sa.ForeignKey("bot_instances.id"), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("buy_volume", sa.Numeric(38, 18), nullable=False, server_default="0"),
        sa.Column("sell_volume", sa.Numeric(38, 18), nullable=False, server_default="0"),
        sa.Column("gross_volume", sa.Numeric(38, 18), nullable=False, server_default="0"),
        sa.Column("fees", sa.Numeric(38, 18), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "reconciliation_runs",
        *tenant_columns(),
        sa.Column("account_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("incidents", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for table in (
        "account_states",
        "market_snapshots",
        "trading_rule_snapshots",
        "source_trade_events",
        "copy_allocations",
        "order_intents",
        "exchange_orders",
        "order_fills",
        "position_snapshots",
        "volume_sessions",
        "reconciliation_runs",
    ):
        op.create_index(f"ix_{table}_tenant_id", table, ["tenant_id"])


def downgrade() -> None:
    for table in reversed(
        (
            "account_states",
            "market_snapshots",
            "trading_rule_snapshots",
            "source_trade_events",
            "copy_allocations",
            "order_intents",
            "exchange_orders",
            "order_fills",
            "position_snapshots",
            "volume_sessions",
            "reconciliation_runs",
        )
    ):
        op.drop_table(table)
