from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CRYPBOT_", case_sensitive=False)
    app_name: str = "Crypbot"
    environment: str = "development"
    execution_mode: str = "MOCK"
    database_url: str = "postgresql+psycopg://crypbot:crypbot@postgres:5432/crypbot"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: str = Field(default="change-me-only-for-local-development")
    credential_master_key: str = Field(default="")
    enable_live_trading: bool = False
    live_trading_env_enabled: bool = False  # Deprecated compatibility flag; canonical gate is CRYPBOT_ENABLE_LIVE_TRADING.
    seed_demo_users: bool = True
    production_bootstrap_admin_email: str = ""
    bingx_base_url: str = "https://open-api.bingx.com"
    bingx_environment: str = "DEMO"
    bingx_default_product: str = "USDT_M_PERPETUAL"
    bingx_dry_run: bool = True
    bingx_live_confirmation: bool = False
    bingx_timeout_seconds: int = 10
    bingx_max_retries: int = 2
    bingx_recv_window_ms: int = 5_000
    bingx_rule_cache_ttl_seconds: int = 900
    bingx_websocket_stale_seconds: int = 15
    bingx_reconciliation_interval_seconds: int = 30
    bingx_public_websocket_url: str = "wss://open-api-swap.bingx.com/swap-market"
    bingx_private_websocket_url: str = "wss://open-api-swap.bingx.com/swap-market"

    def validate_startup_security(self) -> None:
        if self.environment in {"production", "staging"}:
            insecure = {"", "change-me-only-for-local-development", "dev-master-key"}
            if self.jwt_secret in insecure or self.credential_master_key in insecure:
                raise RuntimeError("insecure startup secret configuration")
            if self.seed_demo_users:
                raise RuntimeError("production startup forbids demo user seeding")
            if not self.production_bootstrap_admin_email:
                raise RuntimeError("production startup requires a bootstrap administrator email")
        if self.execution_mode == "LIVE" and not self.enable_live_trading:
            raise RuntimeError("LIVE mode requires CRYPBOT_ENABLE_LIVE_TRADING=true")
        if self.execution_mode == "LIVE" and not self.credential_master_key:
            raise RuntimeError("LIVE mode requires an encryption master key")
        if self.execution_mode == "LIVE" and self.bingx_environment != "LIVE":
            raise RuntimeError("LIVE mode requires CRYPBOT_BINGX_ENVIRONMENT=LIVE")
        if self.execution_mode == "LIVE" and self.bingx_dry_run:
            raise RuntimeError("LIVE mode requires CRYPBOT_BINGX_DRY_RUN=false")
        if self.execution_mode == "LIVE" and not self.bingx_live_confirmation:
            raise RuntimeError("LIVE mode requires CRYPBOT_BINGX_LIVE_CONFIRMATION=true")
        if self.bingx_timeout_seconds < 1 or self.bingx_timeout_seconds > 60:
            raise RuntimeError("BingX timeout must be between 1 and 60 seconds")
        if self.bingx_max_retries < 0 or self.bingx_max_retries > 5:
            raise RuntimeError("BingX retries must be between 0 and 5")


settings = Settings()
