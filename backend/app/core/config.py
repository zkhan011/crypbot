from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Crypbot"
    environment: str = "development"
    execution_mode: str = "MOCK"
    database_url: str = "postgresql+psycopg://crypbot:crypbot@postgres:5432/crypbot"
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: str = Field(default="change-me-only-for-local-development")
    credential_master_key: str = Field(default="")
    live_trading_env_enabled: bool = False
    bingx_base_url: str = "https://open-api.bingx.com"

    def validate_startup_security(self) -> None:
        if self.environment in {"production", "staging"}:
            insecure = {"", "change-me-only-for-local-development", "dev-master-key"}
            if self.jwt_secret in insecure or self.credential_master_key in insecure:
                raise RuntimeError("insecure startup secret configuration")
        if self.execution_mode == "LIVE" and not self.live_trading_env_enabled:
            raise RuntimeError("LIVE mode requires CRYPBOT_LIVE_TRADING_ENV_ENABLED=true")


settings = Settings()
