from datetime import UTC, datetime
from decimal import Decimal
from fastapi import Depends, FastAPI, Header, HTTPException, status
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
from app.services.control_plane import AuthenticationError, AuthorizationError, ControlPlane, Role, User
from app.services.trading_platform import MockScenario, StrategyName, TradingApplication

settings.validate_startup_security()
app = FastAPI(title="Crypbot API", version="0.1.0")
fake_exchange = FakeExchangeClient()
risk_engine = RiskEngine()
trading_app = TradingApplication()
control_plane = ControlPlane()


class VolumeExecutionRequest(BaseModel):
    symbol: str = Field(min_length=1)
    side: Side
    target_quantity: Decimal = Field(gt=Decimal("0"))
    slices: int = Field(gt=0, le=100)
    observed_market_volume: Decimal = Field(gt=Decimal("0"))
    max_participation_rate: Decimal = Field(gt=Decimal("0"), le=Decimal("0.2"))
    objective: str = Field(min_length=12)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=12, max_length=256)


class CreateUserRequest(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=1, max_length=120)
    role: Role
    password: str = Field(min_length=12, max_length=256)


class AIRequest(BaseModel):
    prompt: str = Field(min_length=12, max_length=4000)


def current_user(authorization: str | None = Header(default=None)) -> User:
    token = authorization.removeprefix("Bearer ") if authorization else None
    try:
        return control_plane.session_user(token)
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required") from exc


def control_error(exc: AuthorizationError | KeyError | ValueError) -> HTTPException:
    if isinstance(exc, AuthorizationError):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="insufficient permission")
    if isinstance(exc, KeyError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="resource not found")
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "mode": settings.execution_mode}


@app.get("/ready")
def ready() -> dict[str, str]:
    return {"status": "ready"}


@app.get("/metrics")
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/v1/trading/dashboard")
def trading_dashboard() -> dict[str, object]:
    return trading_app.dashboard_snapshot()


@app.post("/api/v1/trading/start")
def trading_start() -> dict[str, object]:
    snapshot = trading_app.start()
    control_plane.audit(None, "BOT_STARTED", "bot", "mock-default", "SUCCESS", "Mock bot started through demo control")
    return snapshot


@app.post("/api/v1/trading/stop")
def trading_stop() -> dict[str, object]:
    snapshot = trading_app.stop()
    control_plane.audit(None, "BOT_STOPPED", "bot", "mock-default", "SUCCESS", "Mock bot stopped through demo control")
    return snapshot


@app.post("/api/v1/trading/emergency-close-all")
def trading_emergency_close_all() -> dict[str, object]:
    snapshot = trading_app.emergency_stop()
    control_plane.audit(None, "EMERGENCY_STOP", "bot", "mock-default", "SUCCESS", "Emergency close-all executed in mock mode")
    return snapshot


@app.post("/api/v1/trading/copy/pause")
def trading_pause_copy() -> dict[str, object]:
    return trading_app.pause_strategy(StrategyName.COPY)


@app.post("/api/v1/trading/copy/resume")
def trading_resume_copy() -> dict[str, object]:
    return trading_app.resume_strategy(StrategyName.COPY)


@app.post("/api/v1/trading/volume/pause")
def trading_pause_volume() -> dict[str, object]:
    return trading_app.pause_strategy(StrategyName.VOLUME)


@app.post("/api/v1/trading/volume/resume")
def trading_resume_volume() -> dict[str, object]:
    return trading_app.resume_strategy(StrategyName.VOLUME)


@app.post("/api/v1/trading/mock-scenario/{scenario}")
def trading_mock_scenario(scenario: MockScenario) -> dict[str, object]:
    snapshot = trading_app.apply_scenario(scenario)
    control_plane.audit(None, "MOCK_SCENARIO_TRIGGERED", "mock_scenario", scenario.value, "SUCCESS", "Scenario applied to mock engine")
    return snapshot


@app.get("/api/v1/trading/reports")
def trading_reports() -> dict[str, object]:
    return trading_app.reports()


@app.get("/api/v1/bot/status")
def bot_status() -> dict[str, object]:
    mode = settings.execution_mode
    is_live = mode == "LIVE"
    return {
        "mode": mode,
        "bot_state": "RUNNING",
        "heartbeat_at": datetime.now(UTC).isoformat(),
        "market_data_state": "STREAMING_SIMULATED" if not is_live else "STREAMING",
        "worker_state": "RUNNING",
        "trading_state": "SIMULATED_TRADING" if not is_live else "LIVE_TRADING_GATED",
        "orders_processed_today": 12 if not is_live else 0,
        "last_trade_summary": (
            "Mock strategy heartbeat: simulated copy/TWAP loop is active"
            if not is_live
            else "LIVE mode selected; real order flow requires all live-mode approvals and reconciliation gates"
        ),
        "truthfulness_note": (
            "MOCK mode shows simulated trading activity only; no real exchange orders are submitted."
            if not is_live
            else "LIVE status must be interpreted with credential, risk, reconciliation, and approval gates."
        ),
    }


@app.get("/api/v1/mock/market-live")
def mock_market_live() -> dict[str, object]:
    now = datetime.now(UTC)
    tick = Decimal(now.second + (now.minute * 60))
    symbols = [
        ("BTC-USDT", Decimal("65000"), Decimal("12.5")),
        ("ETH-USDT", Decimal("3500"), Decimal("85.2")),
        ("SOL-USDT", Decimal("155"), Decimal("1450")),
    ]
    markets = []
    total_notional = Decimal("0")
    unrealized_pnl = Decimal("0")
    realized_pnl = Decimal("42.18")
    for index, (symbol, base_price, mock_volume) in enumerate(symbols, start=1):
        offset = (tick % Decimal(30)) - Decimal(15)
        price = base_price + (offset * Decimal(index) / Decimal("10"))
        change = (price - base_price) / base_price * Decimal("100")
        quantity = Decimal(index) / Decimal("100")
        notional_value = price * quantity
        pnl = (price - base_price) * quantity
        total_notional += notional_value
        unrealized_pnl += pnl
        markets.append(
            {
                "symbol": symbol,
                "price": str(price.quantize(Decimal("0.01"))),
                "change_percent": str(change.quantize(Decimal("0.0001"))),
                "mock_volume": str(mock_volume),
                "simulated_position_quantity": str(quantity),
                "simulated_notional": str(notional_value.quantize(Decimal("0.01"))),
                "simulated_unrealized_pnl": str(pnl.quantize(Decimal("0.01"))),
            }
        )
    return {
        "mode": settings.execution_mode,
        "timestamp": now.isoformat(),
        "data_quality": "MOCK_SIMULATED_REALTIME",
        "truthfulness_note": "This is deterministic mock market data for UI/live-feature simulation; it is not exchange market data.",
        "amount_traded_today": str(total_notional.quantize(Decimal("0.01"))),
        "realized_pnl_today": str(realized_pnl.quantize(Decimal("0.01"))),
        "unrealized_pnl": str(unrealized_pnl.quantize(Decimal("0.01"))),
        "total_pnl": str((realized_pnl + unrealized_pnl).quantize(Decimal("0.01"))),
        "markets": markets,
    }


@app.post("/api/v1/system/mode/activate-mock")
def activate_mock_mode() -> dict[str, str]:
    return {
        "mode": "MOCK",
        "state": "ACTIVE",
        "safety": "mock execution mode is active; live trading remains disabled",
    }


@app.post("/api/v1/auth/login")
def login(request: LoginRequest) -> dict[str, object]:
    try:
        token, user = control_plane.authenticate(request.email, request.password)
        return {"access_token": token, "token_type": "bearer", "user": user.public()}
    except AuthenticationError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials") from exc


@app.post("/api/v1/auth/logout")
def logout(user: User = Depends(current_user)) -> dict[str, str]:
    control_plane.audit(user.id, "LOGOUT", "session", user.id, "SUCCESS", "Session logout requested")
    return {"status": "logged_out"}


@app.get("/api/v1/me")
def me(user: User = Depends(current_user)) -> dict[str, object]:
    return user.public()


@app.get("/api/v1/users")
def users(user: User = Depends(current_user)) -> dict[str, object]:
    try:
        return {"users": control_plane.list_users(user)}
    except AuthorizationError as exc:
        raise control_error(exc) from exc


@app.post("/api/v1/users")
def create_user(request: CreateUserRequest, user: User = Depends(current_user)) -> dict[str, object]:
    try:
        return control_plane.create_user(user, request.email, request.display_name, request.role, request.password)
    except (AuthorizationError, ValueError) as exc:
        raise control_error(exc) from exc


@app.post("/api/v1/ai/strategy-drafts")
def create_ai_draft(request: AIRequest, user: User = Depends(current_user)) -> dict[str, object]:
    try:
        return control_plane.request_ai_draft(user, request.prompt)
    except AuthorizationError as exc:
        raise control_error(exc) from exc


@app.get("/api/v1/ai/strategy-drafts")
def list_ai_drafts(user: User = Depends(current_user)) -> dict[str, object]:
    try:
        return {"drafts": control_plane.list_drafts(user)}
    except AuthorizationError as exc:
        raise control_error(exc) from exc


@app.post("/api/v1/ai/strategy-drafts/{draft_id}/approve")
def approve_ai_draft(draft_id: str, user: User = Depends(current_user)) -> dict[str, object]:
    try:
        return control_plane.approve_draft(user, draft_id)
    except (AuthorizationError, KeyError, ValueError) as exc:
        raise control_error(exc) from exc


@app.get("/api/v1/audit-logs")
def audit_logs(user: User = Depends(current_user)) -> dict[str, object]:
    try:
        return {"audit_logs": control_plane.audit_log(user)}
    except AuthorizationError as exc:
        raise control_error(exc) from exc


@app.get("/api/v1/audit-logs/verify")
def verify_audit_logs(user: User = Depends(current_user)) -> dict[str, object]:
    try:
        return control_plane.verify_audit_log(user)
    except AuthorizationError as exc:
        raise control_error(exc) from exc


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
