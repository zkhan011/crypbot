from sqlalchemy import MetaData, Table, Column, String, DateTime, Numeric, ForeignKey, UniqueConstraint, JSON, Boolean
from sqlalchemy.sql import func

metadata = MetaData()
organizations = Table(
    "organizations",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)
users = Table(
    "users",
    metadata,
    Column("id", String, primary_key=True),
    Column("organization_id", ForeignKey("organizations.id"), nullable=False, index=True),
    Column("email", String, nullable=False),
    Column("password_hash", String, nullable=False),
    UniqueConstraint("organization_id", "email"),
)
roles = Table("roles", metadata, Column("id", String, primary_key=True), Column("name", String, unique=True, nullable=False))
user_roles = Table(
    "user_roles",
    metadata,
    Column("user_id", ForeignKey("users.id"), primary_key=True),
    Column("role_id", ForeignKey("roles.id"), primary_key=True),
)
exchange_accounts = Table(
    "exchange_accounts",
    metadata,
    Column("id", String, primary_key=True),
    Column("organization_id", ForeignKey("organizations.id"), nullable=False, index=True),
    Column("exchange", String, nullable=False),
    Column("label", String, nullable=False),
    Column("mode", String, nullable=False),
    Column("is_active", Boolean, default=True),
)
encrypted_credentials = Table(
    "encrypted_credentials",
    metadata,
    Column("id", String, primary_key=True),
    Column("organization_id", ForeignKey("organizations.id"), nullable=False, index=True),
    Column("exchange_account_id", ForeignKey("exchange_accounts.id"), nullable=False),
    Column("key_id", String, nullable=False),
    Column("api_key_masked", String, nullable=False),
    Column("ciphertext", String, nullable=False),
    Column("version", String, nullable=False),
)
orders = Table(
    "orders",
    metadata,
    Column("id", String, primary_key=True),
    Column("organization_id", ForeignKey("organizations.id"), nullable=False, index=True),
    Column("exchange_account_id", ForeignKey("exchange_accounts.id"), nullable=False),
    Column("symbol", String, nullable=False),
    Column("side", String, nullable=False),
    Column("quantity", Numeric(38, 18), nullable=False),
    Column("price", Numeric(38, 18)),
    Column("client_order_id", String, nullable=False),
    Column("exchange_order_id", String),
    Column("status", String, nullable=False),
    UniqueConstraint("exchange_account_id", "client_order_id"),
)
audit_events = Table(
    "audit_events",
    metadata,
    Column("id", String, primary_key=True),
    Column("organization_id", ForeignKey("organizations.id"), nullable=False, index=True),
    Column("actor_id", String),
    Column("action", String, nullable=False),
    Column("resource_type", String, nullable=False),
    Column("resource_id", String),
    Column("correlation_id", String),
    Column("before", JSON),
    Column("after", JSON),
    Column("outcome", String, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)
