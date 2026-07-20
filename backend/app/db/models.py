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

# Durable SaaS control-plane schema. Financial values use explicit Numeric
# precision and every customer-owned row is tenant scoped.
tenants = Table(
    "tenants",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String, nullable=False, unique=True),
    Column("is_active", Boolean, nullable=False, server_default="true"),
    Column("version", Numeric(10, 0), nullable=False, server_default="1"),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now()),
)
user_sessions = Table(
    "user_sessions",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", ForeignKey("tenants.id"), nullable=False, index=True),
    Column("user_id", ForeignKey("users.id"), nullable=False, index=True),
    Column("token_hash", String, nullable=False, unique=True),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)
refresh_tokens = Table(
    "refresh_tokens",
    metadata,
    Column("id", String, primary_key=True),
    Column("session_id", ForeignKey("user_sessions.id"), nullable=False, index=True),
    Column("token_hash", String, nullable=False, unique=True),
    Column("family_id", String, nullable=False, index=True),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("used_at", DateTime(timezone=True)),
    Column("revoked_at", DateTime(timezone=True)),
)
bot_instances = Table(
    "bot_instances",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", ForeignKey("tenants.id"), nullable=False, index=True),
    Column("name", String, nullable=False),
    Column("mode", String, nullable=False),
    Column("status", String, nullable=False),
    Column("version", Numeric(10, 0), nullable=False, server_default="1"),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now()),
    UniqueConstraint("tenant_id", "name"),
)
bot_user_assignments = Table(
    "bot_user_assignments",
    metadata,
    Column("bot_id", ForeignKey("bot_instances.id"), primary_key=True),
    Column("user_id", ForeignKey("users.id"), primary_key=True),
)
system_settings = Table(
    "system_settings",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", ForeignKey("tenants.id"), nullable=False, index=True),
    Column("key", String, nullable=False),
    Column("value", JSON, nullable=False),
    Column("version", Numeric(10, 0), nullable=False, server_default="1"),
    Column("updated_by", String),
    Column("updated_at", DateTime(timezone=True), server_default=func.now()),
    UniqueConstraint("tenant_id", "key"),
)
risk_settings = Table(
    "risk_settings",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", ForeignKey("tenants.id"), nullable=False, index=True),
    Column("bot_id", ForeignKey("bot_instances.id"), nullable=False, index=True),
    Column("settings", JSON, nullable=False),
    Column("version", Numeric(10, 0), nullable=False, server_default="1"),
    Column("updated_by", String),
    Column("updated_at", DateTime(timezone=True), server_default=func.now()),
    UniqueConstraint("bot_id"),
)
strategies = Table(
    "strategies",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", ForeignKey("tenants.id"), nullable=False, index=True),
    Column("bot_id", ForeignKey("bot_instances.id"), nullable=False, index=True),
    Column("strategy_type", String, nullable=False),
    Column("status", String, nullable=False),
    Column("configuration", JSON, nullable=False),
    Column("version", Numeric(10, 0), nullable=False, server_default="1"),
    Column("approved_by", String),
    Column("mock_tested_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)
ai_generated_strategies = Table(
    "ai_generated_strategies",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", ForeignKey("tenants.id"), nullable=False, index=True),
    Column("requested_by", ForeignKey("users.id"), nullable=False),
    Column("prompt_redacted", String, nullable=False),
    Column("draft", JSON, nullable=False),
    Column("status", String, nullable=False),
    Column("approved_by", String),
    Column("mock_tested_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)
audit_log_chain = Table(
    "audit_log_chain",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", ForeignKey("tenants.id"), nullable=False, index=True),
    Column("sequence", Numeric(20, 0), nullable=False),
    Column("previous_hash", String(64), nullable=False),
    Column("entry_hash", String(64), nullable=False),
    Column("event", JSON, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    UniqueConstraint("tenant_id", "sequence"),
)
notifications = Table(
    "notifications",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", ForeignKey("tenants.id"), nullable=False, index=True),
    Column("event_type", String, nullable=False),
    Column("provider", String, nullable=False),
    Column("status", String, nullable=False),
    Column("payload_redacted", JSON, nullable=False),
    Column("attempts", Numeric(10, 0), nullable=False, server_default="0"),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
)
background_jobs = Table(
    "background_jobs",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", ForeignKey("tenants.id"), nullable=True, index=True),
    Column("job_type", String, nullable=False),
    Column("status", String, nullable=False),
    Column("error_code", String),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now()),
)
exchange_credentials = Table(
    "exchange_credentials",
    metadata,
    Column("id", String, primary_key=True),
    Column("tenant_id", ForeignKey("tenants.id"), nullable=False, index=True),
    Column("exchange", String, nullable=False),
    Column("api_key_masked", String, nullable=False),
    Column("key_id", String, nullable=False),
    Column("ciphertext", String, nullable=False),
    Column("is_active", Boolean, nullable=False, server_default="true"),
    Column("verified_at", DateTime(timezone=True)),
    Column("verification_status", String, nullable=False, server_default="PENDING"),
    Column("withdrawal_permission_verified", Boolean),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now()),
    UniqueConstraint("tenant_id", "exchange", "api_key_masked"),
)
