from dataclasses import dataclass
from decimal import Decimal
from app.domain.trading_types import Side, notional


@dataclass(frozen=True)
class RiskProfile:
    bot_enabled: bool = True
    min_equity: Decimal = Decimal("100")
    max_order_value: Decimal = Decimal("1000")
    max_leverage: Decimal = Decimal("5")
    allowed_symbols: frozenset[str] = frozenset({"BTC-USDT", "ETH-USDT"})
    blocked_symbols: frozenset[str] = frozenset()
    account_kill_switch: bool = False
    org_kill_switch: bool = False
    dry_run: bool = True
    expected_environment: str = "MOCK"
    max_symbol_exposure: Decimal = Decimal("5000")
    max_total_exposure: Decimal = Decimal("10000")
    max_open_positions: int = 5
    max_daily_loss: Decimal = Decimal("500")
    max_drawdown: Decimal = Decimal("1000")
    max_fee_budget: Decimal = Decimal("100")
    max_spread_bps: Decimal = Decimal("50")
    max_slippage_bps: Decimal = Decimal("50")


@dataclass(frozen=True)
class RiskDecision:
    accepted: bool
    reason_code: str
    explanation: str


@dataclass(frozen=True)
class RiskOrder:
    symbol: str
    side: Side
    quantity: Decimal
    price: Decimal
    leverage: Decimal
    equity: Decimal
    environment: str = "MOCK"
    position_reducing: bool = False
    resulting_symbol_exposure: Decimal = Decimal("0")
    resulting_total_exposure: Decimal = Decimal("0")
    open_positions: int = 0
    daily_loss: Decimal = Decimal("0")
    drawdown: Decimal = Decimal("0")
    fees_used: Decimal = Decimal("0")
    spread_bps: Decimal = Decimal("0")
    slippage_bps: Decimal = Decimal("0")
    market_data_fresh: bool = True
    api_circuit_open: bool = False
    duplicate_signal: bool = False
    account_paused: bool = False
    strategy_paused: bool = False
    symbol_paused: bool = False


class RiskEngine:
    def evaluate(self, order: RiskOrder, profile: RiskProfile) -> RiskDecision:
        if order.position_reducing:
            return RiskDecision(True, "RISK_REDUCTION_ALLOWED", "position-reducing action remains available")
        if not profile.bot_enabled:
            return RiskDecision(False, "BOT_DISABLED", "bot is disabled")
        if profile.org_kill_switch:
            return RiskDecision(False, "ORG_KILL_SWITCH", "organization kill switch is active")
        if profile.account_kill_switch:
            return RiskDecision(False, "ACCOUNT_KILL_SWITCH", "account kill switch is active")
        if order.environment != profile.expected_environment:
            return RiskDecision(False, "ENVIRONMENT_MISMATCH", "order environment differs from risk configuration")
        if order.account_paused or order.strategy_paused or order.symbol_paused:
            return RiskDecision(False, "TRADING_PAUSED", "account, strategy, or symbol is paused")
        if not order.market_data_fresh:
            return RiskDecision(False, "STALE_MARKET_DATA", "required market data is stale")
        if order.api_circuit_open:
            return RiskDecision(False, "API_CIRCUIT_OPEN", "exchange API circuit is open")
        if order.duplicate_signal:
            return RiskDecision(False, "DUPLICATE_SIGNAL", "signal has already been processed")
        if order.symbol in profile.blocked_symbols or order.symbol not in profile.allowed_symbols:
            return RiskDecision(False, "SYMBOL_NOT_ALLOWED", "symbol is not permitted")
        if order.equity < profile.min_equity:
            return RiskDecision(False, "MIN_EQUITY", "account equity is below minimum")
        if order.leverage > profile.max_leverage:
            return RiskDecision(False, "LEVERAGE_LIMIT", "requested leverage exceeds maximum")
        if notional(order.price, order.quantity) > profile.max_order_value:
            return RiskDecision(False, "ORDER_VALUE_LIMIT", "order notional exceeds maximum")
        if order.resulting_symbol_exposure > profile.max_symbol_exposure:
            return RiskDecision(False, "SYMBOL_EXPOSURE_LIMIT", "resulting symbol exposure exceeds maximum")
        if order.resulting_total_exposure > profile.max_total_exposure:
            return RiskDecision(False, "TOTAL_EXPOSURE_LIMIT", "resulting account exposure exceeds maximum")
        if order.open_positions >= profile.max_open_positions:
            return RiskDecision(False, "OPEN_POSITION_LIMIT", "maximum concurrent positions reached")
        if order.daily_loss >= profile.max_daily_loss:
            return RiskDecision(False, "DAILY_LOSS_LIMIT", "maximum daily loss reached")
        if order.drawdown >= profile.max_drawdown:
            return RiskDecision(False, "DRAWDOWN_LIMIT", "maximum drawdown reached")
        if order.fees_used >= profile.max_fee_budget:
            return RiskDecision(False, "FEE_BUDGET", "maximum fee budget reached")
        if order.spread_bps > profile.max_spread_bps:
            return RiskDecision(False, "SPREAD_LIMIT", "market spread exceeds maximum")
        if order.slippage_bps > profile.max_slippage_bps:
            return RiskDecision(False, "SLIPPAGE_LIMIT", "expected slippage exceeds maximum")
        return RiskDecision(True, "ACCEPTED", "order accepted by pre-trade risk")
