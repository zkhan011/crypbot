from decimal import Decimal
import pytest
from app.core.security import CredentialCipher, redact
from app.domain.trading_types import CopyInstructionState, Side, quantize_down
from app.exchanges.bingx import BingXSigner
from app.exchanges.fake import FakeExchangeClient
from app.exchanges.interfaces import Fill, OrderRequest
from app.domain.trading_types import OrderType, OrderStatus
from app.services.copy import CopyTradingEngine
from app.services.orders import OrderService, deterministic_client_order_id, deterministic_strategy_order_id
from app.services.reconciliation import ReconciliationService
from app.services.risk import RiskEngine, RiskOrder, RiskProfile
from app.services.twap import TwapPlan, TwapStrategy
from app.services.volume_execution import VolumeExecutionPlan, VolumeExecutionStrategy


def test_decimal_rounding():
    assert quantize_down(Decimal("1.239"), Decimal("0.01")) == Decimal("1.23")


def test_risk_rejection_order_value():
    d = RiskEngine().evaluate(
        RiskOrder("BTC-USDT", Side.BUY, Decimal("1"), Decimal("50000"), Decimal("2"), Decimal("10000")),
        RiskProfile(max_order_value=Decimal("1000")),
    )
    assert not d.accepted and d.reason_code == "ORDER_VALUE_LIMIT"


def test_kill_switch_rejects():
    d = RiskEngine().evaluate(
        RiskOrder("BTC-USDT", Side.BUY, Decimal("0.01"), Decimal("100"), Decimal("1"), Decimal("10000")),
        RiskProfile(account_kill_switch=True),
    )
    assert d.reason_code == "ACCOUNT_KILL_SWITCH"


def test_risk_reducing_action_survives_kill_switch_but_opening_stale_data_fails():
    engine = RiskEngine()
    reducing = engine.evaluate(
        RiskOrder(
            "BTC-USDT",
            Side.SELL,
            Decimal("0.01"),
            Decimal("100"),
            Decimal("1"),
            Decimal("1000"),
            position_reducing=True,
        ),
        RiskProfile(account_kill_switch=True),
    )
    assert reducing.accepted and reducing.reason_code == "RISK_REDUCTION_ALLOWED"
    stale = engine.evaluate(
        RiskOrder(
            "BTC-USDT",
            Side.BUY,
            Decimal("0.01"),
            Decimal("100"),
            Decimal("1"),
            Decimal("1000"),
            market_data_fresh=False,
        ),
        RiskProfile(),
    )
    assert not stale.accepted and stale.reason_code == "STALE_MARKET_DATA"


def test_copy_state_machine_risk():
    e = CopyTradingEngine(RiskEngine())
    instr = e.create_instruction("e1", "f1", "BTC-USDT", Side.BUY, Decimal("0.01"), Decimal("1"), Decimal("0.001"))
    d = e.validate(instr, Decimal("100"), Decimal("1"), Decimal("1000"), RiskProfile())
    assert d.accepted and instr.state == CopyInstructionState.READY


def test_twap_requires_objective_and_slices():
    slices = TwapStrategy().build_slices(
        TwapPlan("BTC-USDT", Side.BUY, Decimal("0.010"), 5, Decimal("0.001"), Decimal("0.01"), "portfolio rebalance"), Decimal("0.001")
    )
    assert slices == [Decimal("0.002")] * 5


def test_cipher_redaction():
    c = CredentialCipher("x" * 32)
    enc = c.encrypt_json({"api_key": "abc", "api_secret": "supersecret"})
    assert c.decrypt_json(enc)["api_secret"] == "supersecret"
    assert redact({"api_secret": "supersecret"})["api_secret"] == "***REDACTED***"


def test_bingx_signature_fixture():
    qs = BingXSigner.canonical_query({"symbol": "BTC-USDT", "timestamp": 1700000000000})
    assert qs == "symbol=BTC-USDT&timestamp=1700000000000"
    assert BingXSigner.sign("secret", qs) == "597100c6e227a531fa1a21cde9be131e13e3d57e16418878e055193218c3c5a1"


@pytest.mark.asyncio
async def test_unknown_order_reconciles_after_timeout():
    ex = FakeExchangeClient()
    ex.fail_next_as_unknown = True
    cid = deterministic_client_order_id("o", "a", "i")
    req = OrderRequest(
        account_id="a",
        symbol="BTC-USDT",
        side=Side.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.001"),
        client_order_id=cid,
        price=Decimal("100"),
    )
    res = await OrderService(ex).submit_idempotent(req)
    assert res.status == OrderStatus.FILLED


@pytest.mark.asyncio
async def test_timeout_recovers_from_confirmed_fills_without_resubmit():
    class AmbiguousExchange(FakeExchangeClient):
        async def submit_order(self, request):
            raise TimeoutError("ambiguous")

        async def get_order_by_client_id(self, account_id, client_order_id):
            return None

        async def open_orders(self, symbol=None):
            return []

        async def order_history(self, symbol=None):
            return []

        async def fills(self, symbol=None):
            return [
                Fill(
                    fill_id="fill",
                    order_id="exchange-order",
                    client_order_id="client-id",
                    symbol="BTC-USDT",
                    side=Side.BUY,
                    price=Decimal("100"),
                    quantity=Decimal("0.01"),
                )
            ]

    request = OrderRequest(
        account_id="account",
        symbol="BTC-USDT",
        side=Side.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        client_order_id="client-id",
    )
    result = await OrderService(AmbiguousExchange()).submit_idempotent(request)
    assert result.status == OrderStatus.FILLED
    assert result.exchange_order_id == "exchange-order"
    assert result.reason == "RECOVERED_FROM_FILLS_AFTER_TIMEOUT"


def test_reconciliation_mismatches():
    cats = [i.category for i in ReconciliationService().compare_orders({"a"}, {"b"})]
    assert cats == ["Local order missing on exchange", "Exchange order missing locally"]


def test_strategy_client_order_id_is_deterministic_and_sequence_unique():
    first = deterministic_strategy_order_id("COPY", "account", "source", "BTC-USDT", "OPEN_LONG", 1)
    assert first == deterministic_strategy_order_id("COPY", "account", "source", "BTC-USDT", "OPEN_LONG", 1)
    assert first != deterministic_strategy_order_id("COPY", "account", "source", "BTC-USDT", "OPEN_LONG", 2)


def test_volume_execution_caps_participation():
    plan = VolumeExecutionPlan(
        symbol="BTC-USDT",
        side=Side.BUY,
        target_quantity=Decimal("1"),
        slices=4,
        observed_market_volume=Decimal("10"),
        max_participation_rate=Decimal("0.01"),
        objective="Legitimate inventory accumulation with capped participation",
    )
    child_orders = VolumeExecutionStrategy().build_child_orders(plan, Decimal("0.001"))
    assert [order.quantity for order in child_orders] == [Decimal("0.025")] * 4
    assert all(order.max_market_volume_quantity == Decimal("0.025") for order in child_orders)


def test_volume_execution_rejects_missing_objective():
    plan = VolumeExecutionPlan(
        symbol="BTC-USDT",
        side=Side.BUY,
        target_quantity=Decimal("1"),
        slices=4,
        observed_market_volume=Decimal("10"),
        max_participation_rate=Decimal("0.01"),
        objective="",
    )
    with pytest.raises(ValueError, match="legitimate execution objective"):
        VolumeExecutionStrategy().build_child_orders(plan, Decimal("0.001"))
