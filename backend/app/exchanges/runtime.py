"""Secret-safe BingX credential loading and environment mismatch guards."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Mapping


class BingXEnvironment(StrEnum):
    DEMO = "DEMO"
    LIVE = "LIVE"


@dataclass(frozen=True, repr=False)
class BingXCredentials:
    api_key: str
    api_secret: str

    def __repr__(self) -> str:
        return "BingXCredentials(api_key=***REDACTED***, api_secret=***REDACTED***)"


class BingXCredentialProvider:
    """Reads exact environment variable names; never treats a secret as a name."""

    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = environ if environ is not None else os.environ

    def load(self, *, required: bool) -> BingXCredentials | None:
        api_key = self._environ.get("BINGX_API_KEY", "")
        api_secret = self._environ.get("BINGX_API_SECRET", "")
        if not api_key and not api_secret and not required:
            return None
        if not api_key or not api_secret:
            raise RuntimeError("BingX credentials are incomplete")
        return BingXCredentials(api_key=api_key, api_secret=api_secret)

    def environment(self, *, default: BingXEnvironment = BingXEnvironment.DEMO) -> BingXEnvironment:
        raw = self._environ.get("BINGX_ENVIRONMENT", default.value).upper()
        try:
            return BingXEnvironment(raw)
        except ValueError as exc:
            raise RuntimeError("BINGX_ENVIRONMENT must be DEMO or LIVE") from exc

    def base_url(self, *, required: bool) -> str | None:
        value = self._environ.get("BINGX_BASE_URL", "").rstrip("/")
        if required and not value:
            raise RuntimeError("BINGX_BASE_URL is required")
        return value or None

    def recv_window(self, *, default: int = 5_000) -> int:
        raw = self._environ.get("BINGX_RECV_WINDOW", str(default))
        try:
            value = int(raw)
        except ValueError as exc:
            raise RuntimeError("BINGX_RECV_WINDOW must be an integer") from exc
        if value <= 0:
            raise RuntimeError("BINGX_RECV_WINDOW must be positive")
        return value


@dataclass(frozen=True)
class BingXEnvironmentGuard:
    environment: BingXEnvironment = BingXEnvironment.DEMO
    dry_run: bool = True
    live_trading_enabled: bool = False
    live_confirmation: bool = False
    production_base_urls: frozenset[str] = frozenset()
    demo_base_urls: frozenset[str] = frozenset()

    def validate(self, base_url: str, *, automated_test: bool = False) -> None:
        normalized_url = base_url.rstrip("/")
        if not normalized_url.startswith("https://"):
            raise RuntimeError("BingX network target must use HTTPS")
        allowlist = self.demo_base_urls if self.environment == BingXEnvironment.DEMO else self.production_base_urls
        if normalized_url not in allowlist:
            raise RuntimeError("BingX base URL is not allowlisted for the configured environment")
        if self.environment == BingXEnvironment.DEMO:
            if not self.dry_run:
                raise RuntimeError("demo environment must remain dry-run until demo certification is explicitly enabled")
            return
        if automated_test:
            raise RuntimeError("automated tests may not enable BingX LIVE orders")
        if self.dry_run or not self.live_trading_enabled or not self.live_confirmation:
            raise RuntimeError("BingX LIVE environment is blocked by dry-run and confirmation gates")
