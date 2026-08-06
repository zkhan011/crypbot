"""Compliance controls for legitimate fill-based execution accounting."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.trading_types import Side
from app.exchanges.interfaces import Fill


class SelfTradePreventionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ControlledOrder:
    account_id: str
    symbol: str
    side: Side
    price: Decimal | None


class SelfTradePreventionService:
    """Blocks crossing orders between accounts controlled by this platform."""

    def validate(self, candidate: ControlledOrder, resting: list[ControlledOrder]) -> None:
        for order in resting:
            if order.symbol != candidate.symbol or order.side == candidate.side:
                continue
            if order.price is None or candidate.price is None:
                raise SelfTradePreventionError("opposing controlled market order may self-trade")
            crosses = candidate.price >= order.price if candidate.side == Side.BUY else candidate.price <= order.price
            if crosses:
                raise SelfTradePreventionError("order would cross an opposing controlled order")


@dataclass
class FillVolumeLedger:
    buy_volume: Decimal = Decimal("0")
    sell_volume: Decimal = Decimal("0")
    gross_volume: Decimal = Decimal("0")
    net_quantity: Decimal = Decimal("0")
    maker_fees: Decimal = Decimal("0")
    taker_fees: Decimal = Decimal("0")

    def record(self, fill: Fill) -> None:
        notional = fill.price * fill.quantity
        self.gross_volume += notional
        if fill.side == Side.BUY:
            self.buy_volume += notional
            self.net_quantity += fill.quantity
        else:
            self.sell_volume += notional
            self.net_quantity -= fill.quantity
        if fill.maker is True:
            self.maker_fees += fill.fee
        else:
            self.taker_fees += fill.fee


@dataclass
class CancellationRatioGuard:
    maximum_ratio: Decimal
    submitted: int = 0
    cancelled: int = 0

    def __post_init__(self) -> None:
        if self.maximum_ratio < 0 or self.maximum_ratio > 1:
            raise ValueError("maximum cancellation ratio must be between 0 and 1")

    def record_submission(self) -> None:
        self.submitted += 1

    def record_cancellation(self) -> None:
        self.cancelled += 1

    @property
    def ratio(self) -> Decimal:
        return Decimal(self.cancelled) / Decimal(self.submitted) if self.submitted else Decimal("0")

    def allow_opening_order(self) -> bool:
        return self.ratio <= self.maximum_ratio


def spread_bps(best_bid: Decimal, best_ask: Decimal) -> Decimal:
    if best_bid <= 0 or best_ask <= 0 or best_ask < best_bid:
        raise ValueError("invalid best bid/ask")
    midpoint = (best_bid + best_ask) / Decimal(2)
    return (best_ask - best_bid) / midpoint * Decimal(10_000)


@dataclass(frozen=True)
class VolumeOrderContext:
    symbol: str
    quantity: Decimal
    price: Decimal
    resulting_position_notional: Decimal
    daily_loss: Decimal
    fees_used: Decimal
    spread_bps: Decimal
    slippage_bps: Decimal
    depth_notional: Decimal
    volatility: Decimal
    market_data_fresh: bool


@dataclass(frozen=True)
class VolumeSafetyLimits:
    allowed_symbols: frozenset[str]
    maximum_order_quantity: Decimal
    maximum_order_notional: Decimal
    maximum_position_notional: Decimal
    maximum_daily_loss: Decimal
    maximum_fee_budget: Decimal
    maximum_spread_bps: Decimal
    maximum_slippage_bps: Decimal
    minimum_depth_notional: Decimal
    volatility_limit: Decimal


class VolumeExecutionRiskService:
    def validate(self, context: VolumeOrderContext, limits: VolumeSafetyLimits, cancellations: CancellationRatioGuard) -> None:
        if context.symbol not in limits.allowed_symbols:
            raise ValueError("volume symbol is not allowed")
        if not context.market_data_fresh:
            raise ValueError("volume market data is stale")
        if context.quantity <= 0 or context.quantity > limits.maximum_order_quantity:
            raise ValueError("volume order quantity limit")
        if context.quantity * context.price > limits.maximum_order_notional:
            raise ValueError("volume order notional limit")
        if context.resulting_position_notional > limits.maximum_position_notional:
            raise ValueError("volume position exposure limit")
        if context.daily_loss >= limits.maximum_daily_loss or context.fees_used >= limits.maximum_fee_budget:
            raise ValueError("volume loss or fee budget reached")
        if context.spread_bps > limits.maximum_spread_bps or context.slippage_bps > limits.maximum_slippage_bps:
            raise ValueError("volume spread or slippage limit")
        if context.depth_notional < limits.minimum_depth_notional or context.volatility > limits.volatility_limit:
            raise ValueError("volume liquidity or volatility limit")
        if not cancellations.allow_opening_order():
            raise ValueError("volume cancellation ratio limit")
