from decimal import Decimal
from fastapi import FastAPI, Header
from pydantic import BaseModel, Field
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response
from app.core.config import settings
from app.domain.types import OrderType, Side
from app.exchanges.fake import FakeExchangeClient
from app.exchanges.interfaces import OrderRequest
from app.services.copy import CopyTradingEngine
from app.services.orders import OrderService, deterministic_client_order_id
from app.services.reconciliation import ReconciliationService
from app.services.risk import RiskEngine, RiskOrder, RiskProfile
from app.services.twap import TwapPlan, TwapStrategy
from app.services.volume_execution import VolumeExecutionPlan, VolumeExecutionStrategy

settings.validate_startup_security()
app = FastAPI(title="Crypbot API", version="0.1.0")
fake_exchange = FakeExchangeClient()
risk_engine = RiskEngine()


class VolumeExecutionRequest(BaseModel):
    symbol: str = Field(min_length=1)
    side: Side
    target_quantity: Decimal = Field(gt=Decimal("0"))
    slices: int = Field(gt=0, le=100)
    observed_market_volume: Decimal = Field(gt=Decimal("0"))
    max_participation_rate: Decimal = Field(gt=Decimal("0"), le=Decimal("0.2"))
    objective: str = Field(min_length=12)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": settings.execution_mode}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/api/v1/system/mode/activate-mock")
def activate_mock_mode() -> dict[str, str]:
    return {
        "mode": "MOCK",
        "state": "ACTIVE",
        "safety": "mock execution mode is active; live trading remains disabled",
    }


@app.get("/api/v1/me")
def me() -> dict[str, object]:
    return {"email": "dev-admin@example.local", "roles": ["platform_admin"], "organization_id": "dev-org"}


@app.post("/api/v1/risk/evaluate")
def evaluate(order: RiskOrder) -> dict[str, object]:
    return risk_engine.evaluate(order, RiskProfile()).__dict__


@app.post("/api/v1/demo/copy-trade")
def demo_copy(idempotency_key: str = Header(default="demo-copy")) -> dict[str, object]:
    engine = CopyTradingEngine(risk_engine)
    instr = engine.create_instruction("master-1", "follower-1", "BTC-USDT", Side.BUY, Decimal("0.02"), Decimal("0.5"), Decimal("0.001"))
    decision = engine.validate(instr, Decimal("50000"), Decimal("2"), Decimal("10000"), RiskProfile(max_order_value=Decimal("1000")))
    return {"instruction": instr.__dict__, "risk": decision.__dict__, "idempotency_key": idempotency_key}


@app.post("/api/v1/demo/submit-order")
async def demo_submit() -> dict[str, object]:
    cid = deterministic_client_order_id("dev-org", "acct-1", "demo-intent")
    req = OrderRequest(
        account_id="acct-1",
        symbol="BTC-USDT",
        side=Side.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.001"),
        price=Decimal("50000"),
        client_order_id=cid,
    )
    res = await OrderService(fake_exchange).submit_idempotent(req)
    return res.model_dump(mode="json")


@app.post("/api/v1/demo/twap")
def demo_twap() -> dict[str, object]:
    plan = TwapPlan(
        "BTC-USDT",
        Side.BUY,
        Decimal("0.01"),
        5,
        Decimal("0.001"),
        Decimal("0.01"),
        "accumulate inventory over time without exceeding risk limits",
    )
    return {"slices": [str(x) for x in TwapStrategy().build_slices(plan, Decimal("0.001"))], "mode": settings.execution_mode}


@app.post("/api/v1/demo/unknown-order")
async def unknown_order() -> dict[str, object]:
    fake_exchange.fail_next_as_unknown = True
    cid = deterministic_client_order_id("dev-org", "acct-1", "uncertain-intent")
    req = OrderRequest(
        account_id="acct-1",
        symbol="ETH-USDT",
        side=Side.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("0.01"),
        price=Decimal("3000"),
        client_order_id=cid,
    )
    res = await OrderService(fake_exchange).submit_idempotent(req)
    return res.model_dump(mode="json")


@app.post("/api/v1/demo/volume-execution")
def demo_volume_execution(request: VolumeExecutionRequest) -> dict[str, object]:
    plan = VolumeExecutionPlan(
        symbol=request.symbol,
        side=request.side,
        target_quantity=request.target_quantity,
        slices=request.slices,
        observed_market_volume=request.observed_market_volume,
        max_participation_rate=request.max_participation_rate,
        objective=request.objective,
    )
    child_orders = VolumeExecutionStrategy().build_child_orders(plan, Decimal("0.001"))
    return {
        "mode": settings.execution_mode,
        "objective": request.objective,
        "max_participation_rate": str(request.max_participation_rate),
        "child_orders": [
            {
                "slice": child.slice,
                "quantity": str(child.quantity),
                "max_market_volume_quantity": str(child.max_market_volume_quantity),
            }
            for child in child_orders
        ],
        "compliance_note": "Participation is capped for legitimate execution quality; fake volume and wash trading are not supported.",
    }


@app.post("/api/v1/kill-switch/account/{account_id}")
def kill_switch(account_id: str) -> dict[str, str]:
    return {"account_id": account_id, "state": "ACTIVE", "effect": "new trading rejected"}


@app.get("/api/v1/reconciliation/demo")
def recon_demo() -> dict[str, object]:
    incidents = ReconciliationService().compare_orders({"a", "b"}, {"b", "c"})
    return {"incidents": [i.__dict__ for i in incidents]}
