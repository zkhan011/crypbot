from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table("roles", sa.Column("id", sa.String(), primary_key=True), sa.Column("name", sa.String(), nullable=False, unique=True))
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.UniqueConstraint("organization_id", "email"),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role_id", sa.String(), sa.ForeignKey("roles.id"), primary_key=True),
    )
    op.create_table(
        "exchange_accounts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("exchange", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), default=True),
    )
    op.create_index("ix_exchange_accounts_organization_id", "exchange_accounts", ["organization_id"])
    op.create_table(
        "encrypted_credentials",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("exchange_account_id", sa.String(), sa.ForeignKey("exchange_accounts.id"), nullable=False),
        sa.Column("key_id", sa.String(), nullable=False),
        sa.Column("api_key_masked", sa.String(), nullable=False),
        sa.Column("ciphertext", sa.String(), nullable=False),
        sa.Column("version", sa.String(), nullable=False),
    )
    op.create_index("ix_encrypted_credentials_organization_id", "encrypted_credentials", ["organization_id"])
    op.create_table(
        "orders",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("exchange_account_id", sa.String(), sa.ForeignKey("exchange_accounts.id"), nullable=False),
        sa.Column("symbol", sa.String(), nullable=False),
        sa.Column("side", sa.String(), nullable=False),
        sa.Column("quantity", sa.Numeric(38, 18), nullable=False),
        sa.Column("price", sa.Numeric(38, 18)),
        sa.Column("client_order_id", sa.String(), nullable=False),
        sa.Column("exchange_order_id", sa.String()),
        sa.Column("status", sa.String(), nullable=False),
        sa.UniqueConstraint("exchange_account_id", "client_order_id"),
    )
    op.create_index("ix_orders_organization_id", "orders", ["organization_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("organization_id", sa.String(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("actor_id", sa.String()),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=False),
        sa.Column("resource_id", sa.String()),
        sa.Column("correlation_id", sa.String()),
        sa.Column("before", sa.JSON()),
        sa.Column("after", sa.JSON()),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"])


def downgrade():
    for t in ["audit_events", "orders", "encrypted_credentials", "exchange_accounts", "user_roles", "users", "roles", "organizations"]:
        op.drop_table(t)
