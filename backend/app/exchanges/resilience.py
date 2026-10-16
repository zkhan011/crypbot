"""Contract-independent time, throttling, and circuit-breaker primitives."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class RateLimitScope(StrEnum):
    MARKET_DATA = "market_data"
    ACCOUNT = "account"
    ORDER_CREATE = "order_create"
    ORDER_CANCEL = "order_cancel"
    POSITION_CONTROL = "position_control"
    COPY_TRADING = "copy_trading"
    ORDER = "order_create"  # compatibility alias
    CANCELLATION = "order_cancel"  # compatibility alias


class UnverifiedRateLimitError(RuntimeError):
    pass


@dataclass(frozen=True)
class RateLimit:
    requests: int
    period_seconds: Decimal

    def __post_init__(self) -> None:
        if self.requests <= 0 or self.period_seconds <= 0:
            raise ValueError("rate limit values must be positive")


class EndpointRateLimiter:
    """Process-local token buckets; unknown scopes fail closed for openings."""

    def __init__(self, limits: dict[RateLimitScope, RateLimit] | None = None) -> None:
        self._limits = limits or {}
        self._buckets: dict[RateLimitScope, tuple[Decimal, Decimal]] = {}
        self._throttled: dict[RateLimitScope, int] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _now() -> Decimal:
        return Decimal(str(time.monotonic()))

    async def acquire(self, scope: RateLimitScope, *, risk_reducing: bool = False, timeout_seconds: Decimal = Decimal("0")) -> None:
        limit = self._limits.get(scope)
        if limit is None:
            if risk_reducing and scope in {RateLimitScope.ORDER_CANCEL, RateLimitScope.POSITION_CONTROL}:
                return
            raise UnverifiedRateLimitError(f"{scope.value} rate limit is unverified; opening operation disabled")
        deadline = self._now() + timeout_seconds
        while True:
            async with self._lock:
                now = self._now()
                last, tokens = self._buckets.get(scope, (now, Decimal(limit.requests)))
                refill = (now - last) / limit.period_seconds * Decimal(limit.requests)
                tokens = min(Decimal(limit.requests), tokens + refill)
                if tokens >= 1:
                    self._buckets[scope] = (now, tokens - 1)
                    return
                self._buckets[scope] = (now, tokens)
                self._throttled[scope] = self._throttled.get(scope, 0) + 1
            if self._now() >= deadline:
                raise UnverifiedRateLimitError(f"{scope.value} process-local capacity exhausted")
            await asyncio.sleep(0.01)

    async def metrics(self, scope: RateLimitScope) -> dict[str, Decimal | int]:
        async with self._lock:
            limit = self._limits.get(scope)
            remaining = self._buckets.get(scope, (Decimal("0"), Decimal(limit.requests) if limit else Decimal("0")))[1]
            return {"remaining": remaining, "throttled": self._throttled.get(scope, 0)}


class BingXTimeSynchronizer:
    """Atomic midpoint-offset calculator driven by a verified time-fetch callback."""

    def __init__(
        self,
        wall_clock_ms: Callable[[], int] | None = None,
        monotonic_clock: Callable[[], Decimal] | None = None,
        refresh_seconds: Decimal = Decimal("30"),
    ) -> None:
        if refresh_seconds <= 0:
            raise ValueError("refresh_seconds must be positive")
        self._wall_clock_ms = wall_clock_ms or (lambda: time.time_ns() // 1_000_000)
        self._monotonic_clock = monotonic_clock or (lambda: Decimal(str(time.monotonic())))
        self._refresh_seconds = refresh_seconds
        self._offset_ms = 0
        self._last_sync: Decimal | None = None
        self._lock = asyncio.Lock()

    def now_ms(self) -> int:
        return self._wall_clock_ms() + self._offset_ms

    async def synchronize(self, fetch_server_time_ms: Callable[[], Awaitable[int]], *, force: bool = False) -> int:
        async with self._lock:
            now = self._monotonic_clock()
            if not force and self._last_sync is not None and now - self._last_sync < self._refresh_seconds:
                return self._offset_ms
            started = self._wall_clock_ms()
            server_time = await fetch_server_time_ms()
            completed = self._wall_clock_ms()
            if not isinstance(server_time, int) or server_time <= 0:
                raise ValueError("server time response must be a positive millisecond integer")
            midpoint = started + ((completed - started) // 2)
            self._offset_ms = server_time - midpoint
            self._last_sync = self._monotonic_clock()
            return self._offset_ms


class CircuitOpenError(RuntimeError):
    pass


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_seconds: Decimal = Decimal("30")) -> None:
        if failure_threshold < 1 or recovery_seconds <= 0:
            raise ValueError("invalid circuit breaker configuration")
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self._failures = 0
        self._opened_at: Decimal | None = None
        self._lock = asyncio.Lock()

    @staticmethod
    def _now() -> Decimal:
        return Decimal(str(time.monotonic()))

    async def require_available(self, *, risk_reducing: bool = False) -> None:
        async with self._lock:
            if self._opened_at is None or risk_reducing:
                return
            if self._now() - self._opened_at < self.recovery_seconds:
                raise CircuitOpenError("BingX circuit is open; exposure-increasing operation blocked")
            self._failures = 0
            self._opened_at = None

    async def record_success(self) -> None:
        async with self._lock:
            self._failures = 0
            self._opened_at = None

    async def record_failure(self) -> None:
        async with self._lock:
            self._failures += 1
            if self._failures >= self.failure_threshold:
                self._opened_at = self._now()
