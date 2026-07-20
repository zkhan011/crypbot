"""Add tenant-scoped exchange credential lifecycle records."""

from alembic import op
import sqlalchemy as sa

revision = "0003_exchange_credentials"
down_revision = "0002_durable_control_plane"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exchange_credentials",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("tenant_id", sa.String(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("exchange", sa.String(), nullable=False),
        sa.Column("api_key_masked", sa.String(), nullable=False),
        sa.Column("key_id", sa.String(), nullable=False),
        sa.Column("ciphertext", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("verification_status", sa.String(), nullable=False, server_default="PENDING"),
        sa.Column("withdrawal_permission_verified", sa.Boolean()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "exchange", "api_key_masked"),
    )
    op.create_index("ix_exchange_credentials_tenant_id", "exchange_credentials", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("exchange_credentials")
