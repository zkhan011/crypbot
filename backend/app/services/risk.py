from dataclasses import dataclass
from decimal import Decimal
from app.domain.types import Side, notional


@dataclass(frozen=True)
class RiskProfile:
    min_equity: Decimal = Decimal("100")
    max_order_value: Decimal = Decimal("1000")
    max_leverage: Decimal = Decimal("5")
    allowed_symbols: frozenset[str] = frozenset({"BTC-USDT", "ETH-USDT"})
    blocked_symbols: frozenset[str] = frozenset()
    account_kill_switch: bool = False
    org_kill_switch: bool = False


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


class RiskEngine:
    def evaluate(self, order: RiskOrder, profile: RiskProfile) -> RiskDecision:
        if profile.org_kill_switch:
            return RiskDecision(False, "ORG_KILL_SWITCH", "organization kill switch is active")
        if profile.account_kill_switch:
            return RiskDecision(False, "ACCOUNT_KILL_SWITCH", "account kill switch is active")
        if order.symbol in profile.blocked_symbols or order.symbol not in profile.allowed_symbols:
            return RiskDecision(False, "SYMBOL_NOT_ALLOWED", "symbol is not permitted")
        if order.equity < profile.min_equity:
            return RiskDecision(False, "MIN_EQUITY", "account equity is below minimum")
        if order.leverage > profile.max_leverage:
            return RiskDecision(False, "LEVERAGE_LIMIT", "requested leverage exceeds maximum")
        if notional(order.price, order.quantity) > profile.max_order_value:
            return RiskDecision(False, "ORDER_VALUE_LIMIT", "order notional exceeds maximum")
        return RiskDecision(True, "ACCEPTED", "order accepted by pre-trade risk")
