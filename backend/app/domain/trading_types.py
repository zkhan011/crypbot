from decimal import Decimal, ROUND_DOWN
from enum import StrEnum


class Side(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"
    TRIGGER_LIMIT = "TRIGGER_LIMIT"
    TRIGGER_MARKET = "TRIGGER_MARKET"
    TRAILING_STOP_MARKET = "TRAILING_STOP_MARKET"


class PositionSide(StrEnum):
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


class TimeInForce(StrEnum):
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    POST_ONLY = "POST_ONLY"


class MarginType(StrEnum):
    ISOLATED = "ISOLATED"
    CROSSED = "CROSSED"


class OrderStatus(StrEnum):
    NEW = "NEW"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    UNKNOWN = "UNKNOWN"


class ExecutionMode(StrEnum):
    MOCK = "MOCK"
    PAPER = "PAPER"
    DEMO = "DEMO"
    LIVE = "LIVE"


class CopyInstructionState(StrEnum):
    RECEIVED = "RECEIVED"
    VALIDATING = "VALIDATING"
    RISK_REJECTED = "RISK_REJECTED"
    READY = "READY"
    SUBMITTING = "SUBMITTING"
    SUBMITTED = "SUBMITTED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


def quantize_down(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ValueError("step must be positive")
    return (value / step).to_integral_value(rounding=ROUND_DOWN) * step


def notional(price: Decimal, quantity: Decimal) -> Decimal:
    return price * quantity
