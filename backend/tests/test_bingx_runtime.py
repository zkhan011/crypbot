import asyncio
from decimal import Decimal

import pytest

from app.exchanges.account_types import AccountType, AccountTypeParseError, parse_account_balance
from app.exchanges.resilience import (
    BingXTimeSynchronizer,
    CircuitBreaker,
    CircuitOpenError,
    EndpointRateLimiter,
    RateLimit,
    RateLimitScope,
    UnverifiedRateLimitError,
)
from app.exchanges.runtime import BingXCredentialProvider, BingXEnvironment, BingXEnvironmentGuard


def test_sopt_account_type_preserves_raw_and_uses_decimal() -> None:
    parsed = parse_account_balance({"accountType": "sopt", "usdtBalance": "0.00000000"})
    assert parsed.raw_account_type == "sopt"
    assert parsed.account_type == AccountType.SPOT
    assert parsed.usdt_balance == Decimal("0.00000000")


@pytest.mark.parametrize(
    ("payload", "expected_raw", "expected_type"),
    [
        ({"usdtBalance": "1.2"}, None, AccountType.MISSING),
        ({"accountType": None, "usdtBalance": "1.2"}, None, AccountType.MISSING),
        ({"accountType": "", "usdtBalance": "1.2"}, "", AccountType.MISSING),
        ({"accountType": "future-product", "usdtBalance": "1.2"}, "future-product", AccountType.UNKNOWN),
        ({"accountType": "spot", "usdtBalance": "1.2"}, "spot", AccountType.SPOT),
        ({"accountType": "swap", "usdtBalance": "1.2"}, "swap", AccountType.SWAP),
        ({"accountType": "perpetual", "usdtBalance": "1.2"}, "perpetual", AccountType.SWAP),
        ({"accountType": "fund", "usdtBalance": "1.2"}, "fund", AccountType.FUND),
    ],
)
def test_account_type_unknown_and_missing_are_safe(payload, expected_raw, expected_type) -> None:
    parsed = parse_account_balance(payload)
    assert parsed.raw_account_type == expected_raw
    assert parsed.account_type == expected_type


def test_account_type_rejects_non_decimal_balance() -> None:
    with pytest.raises(AccountTypeParseError):
        parse_account_balance({"accountType": "sopt", "usdtBalance": "not-money"})


def test_unknown_account_type_observer_receives_bounded_sanitized_value() -> None:
    observed: list[str] = []
    parse_account_balance(
        {"accountType": "future\nproduct-with-a-very-long-value", "usdtBalance": "0"},
        unknown_observer=observed.append,
    )
    assert observed == ["future?product-with-a-very-long-"]


def test_credential_provider_uses_exact_names_and_redacts_repr() -> None:
    credentials = BingXCredentialProvider({"BINGX_API_KEY": "test-key", "BINGX_API_SECRET": "test-secret"}).load(required=True)
    assert credentials is not None
    assert credentials.api_key == "test-key"
    assert "test-key" not in repr(credentials)
    assert "test-secret" not in repr(credentials)
    with pytest.raises(RuntimeError, match="incomplete"):
        BingXCredentialProvider({"BINGX_API_KEY": "test-key"}).load(required=True)


def test_environment_guard_rejects_mismatch_and_automated_live() -> None:
    demo = BingXEnvironmentGuard(
        environment=BingXEnvironment.DEMO,
        demo_base_urls=frozenset({"https://demo.invalid"}),
    )
    demo.validate("https://demo.invalid")
    with pytest.raises(RuntimeError, match="not allowlisted"):
        demo.validate("https://live.invalid")
    live = BingXEnvironmentGuard(
        environment=BingXEnvironment.LIVE,
        dry_run=False,
        live_trading_enabled=True,
        live_confirmation=True,
        production_base_urls=frozenset({"https://live.invalid"}),
    )
    with pytest.raises(RuntimeError, match="automated tests"):
        live.validate("https://live.invalid", automated_test=True)


@pytest.mark.asyncio
async def test_time_sync_positive_and_negative_midpoint_offsets() -> None:
    ticks = iter([1_000, 1_100, 2_000, 2_100, 2_200])
    synchronizer = BingXTimeSynchronizer(wall_clock_ms=lambda: next(ticks))

    async def ahead() -> int:
        return 1_250

    async def behind() -> int:
        return 2_000

    assert await synchronizer.synchronize(ahead, force=True) == 200
    assert synchronizer.now_ms() == 2_200
    assert await synchronizer.synchronize(behind, force=True) == -150


@pytest.mark.asyncio
async def test_time_sync_single_flight_and_malformed_response() -> None:
    calls = 0
    synchronizer = BingXTimeSynchronizer(wall_clock_ms=lambda: 1_000)

    async def fetch() -> int:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0)
        return 1_100

    assert await asyncio.gather(*(synchronizer.synchronize(fetch) for _ in range(5))) == [100] * 5
    assert calls == 1

    async def malformed() -> int:
        return 0

    with pytest.raises(ValueError, match="positive"):
        await synchronizer.synchronize(malformed, force=True)

    async def timeout() -> int:
        raise TimeoutError("sanitized timeout")

    with pytest.raises(TimeoutError, match="sanitized"):
        await synchronizer.synchronize(timeout, force=True)


@pytest.mark.asyncio
async def test_unknown_rate_limit_blocks_opening_but_preserves_cancel_capacity() -> None:
    limiter = EndpointRateLimiter()
    with pytest.raises(UnverifiedRateLimitError, match="unverified"):
        await limiter.acquire(RateLimitScope.ORDER)
    await limiter.acquire(RateLimitScope.CANCELLATION, risk_reducing=True)

    configured = EndpointRateLimiter({RateLimitScope.MARKET_DATA: RateLimit(1, Decimal("60"))})
    await configured.acquire(RateLimitScope.MARKET_DATA)
    with pytest.raises(UnverifiedRateLimitError, match="capacity exhausted"):
        await configured.acquire(RateLimitScope.MARKET_DATA)


@pytest.mark.asyncio
async def test_circuit_breaker_blocks_openings_but_not_reductions() -> None:
    circuit = CircuitBreaker(failure_threshold=2, recovery_seconds=Decimal("60"))
    await circuit.record_failure()
    await circuit.record_failure()
    with pytest.raises(CircuitOpenError):
        await circuit.require_available()
    await circuit.require_available(risk_reducing=True)
