from decimal import Decimal
import pytest
from app.core.security import CredentialCipher, redact
from app.domain.types import CopyInstructionState, Side, quantize_down
from app.exchanges.bingx import BingXSigner
from app.exchanges.fake import FakeExchangeClient
from app.exchanges.interfaces import OrderRequest
from app.domain.types import OrderType, OrderStatus
from app.services.copy import CopyTradingEngine
from app.services.orders import OrderService, deterministic_client_order_id
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


def test_reconciliation_mismatches():
    cats = [i.category for i in ReconciliationService().compare_orders({"a"}, {"b"})]
    assert cats == ["Local order missing on exchange", "Exchange order missing locally"]


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
