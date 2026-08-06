from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import uuid4

from app.domain.types import OrderStatus, OrderType, Side


class Mode(StrEnum):
    MOCK = "MOCK"
    LIVE = "LIVE"


class BotState(StrEnum):
    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    EMERGENCY_STOPPED = "EMERGENCY_STOPPED"


class StrategyName(StrEnum):
    COPY = "COPY"
    VOLUME = "VOLUME"


class StrategyState(StrEnum):
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"


class SignalAction(StrEnum):
    OPEN = "OPEN"
    CLOSE = "CLOSE"


class MockScenario(StrEnum):
    NORMAL_MARKET = "Normal market"
    BULLISH_VOLUME_BREAKOUT = "Bullish volume breakout"
    BEARISH_VOLUME_BREAKDOWN = "Bearish volume breakdown"
    LEAD_TRADER_OPENS_LONG = "Lead trader opens long"
    LEAD_TRADER_OPENS_SHORT = "Lead trader opens short"
    LEAD_TRADER_CLOSES_POSITION = "Lead trader closes position"
    STOP_LOSS_HIT = "Stop-loss hit"
    TAKE_PROFIT_HIT = "Take-profit hit"
    DAILY_LOSS_LIMIT_HIT = "Daily-loss limit hit"
    API_CONNECTION_FAILURE = "API connection failure"
    ORDER_REJECTION = "Order rejection"
    HIGH_SPREAD_NO_TRADE = "High spread / no trade"
    OPPOSITE_STRATEGY_CONFLICT = "Opposite strategy conflict"
    EMERGENCY_STOP = "Emergency stop"


@dataclass(frozen=True)
class Candle:
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    timestamp: str


@dataclass(frozen=True)
class OrderBook:
    symbol: str
    bid: Decimal
    ask: Decimal
    bid_size: Decimal
    ask_size: Decimal


@dataclass(frozen=True)
class Balance:
    total: Decimal
    available: Decimal
    asset: str = "USDT"


@dataclass(frozen=True)
class TradeSignal:
    id: str
    strategy: StrategyName
    symbol: str
    side: Side
    action: SignalAction
    confidence: Decimal
    reason: str
    created_at: str


@dataclass
class SimulatedOrder:
    id: str
    symbol: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    price: Decimal
    status: OrderStatus
    strategy: StrategyName
    created_at: str


@dataclass
class SimulatedPosition:
    id: str
    symbol: str
    side: Side
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal
    stop_loss: Decimal
    take_profit: Decimal
    trailing_stop: Decimal | None
    strategy: StrategyName
    opened_at: str

    @property
    def notional(self) -> Decimal:
        return self.mark_price * self.quantity

    @property
    def unrealized_pnl(self) -> Decimal:
        direction = Decimal("1") if self.side == Side.BUY else Decimal("-1")
        return (self.mark_price - self.entry_price) * self.quantity * direction


@dataclass(frozen=True)
class NotificationRecord:
    id: str
    channel: str
    event: str
    message: str
    sent: bool
    created_at: str


@dataclass(frozen=True)
class RiskEvent:
    id: str
    reason_code: str
    explanation: str
    created_at: str


@dataclass(frozen=True)
class BotConfig:
    mode: Mode = Mode.MOCK
    enable_live_trading: bool = False
    trading_pairs: tuple[str, ...] = ("BTC-USDT", "ETH-USDT", "SOL-USDT")
    risk_per_trade: Decimal = Decimal("0.01")
    max_daily_loss: Decimal = Decimal("250")
    max_drawdown: Decimal = Decimal("0.10")
    max_open_positions: int = 3
    max_position_size: Decimal = Decimal("1500")
    max_leverage: Decimal = Decimal("3")
    mandatory_stop_loss_percent: Decimal = Decimal("0.02")
    take_profit_percent: Decimal = Decimal("0.04")
    trailing_stop_percent: Decimal = Decimal("0.015")
    min_liquidity: Decimal = Decimal("10")
    max_spread_percent: Decimal = Decimal("0.15")
    volume_spike_multiplier: Decimal = Decimal("2")
    conflict_policy: str = "REJECT_NEW_SIGNAL"


@dataclass
class BotRuntimeState:
    bot_state: BotState = BotState.RUNNING
    copy_state: StrategyState = StrategyState.RUNNING
    volume_state: StrategyState = StrategyState.RUNNING
    scenario: MockScenario = MockScenario.NORMAL_MARKET
    api_connected: bool = True
    daily_realized_pnl: Decimal = Decimal("42.18")
    peak_equity: Decimal = Decimal("10000")
    notifications: list[NotificationRecord] = field(default_factory=list)
    signals: list[TradeSignal] = field(default_factory=list)
    orders: list[SimulatedOrder] = field(default_factory=list)
    positions: list[SimulatedPosition] = field(default_factory=list)
    closed_trades: list[dict[str, str]] = field(default_factory=list)
    risk_events: list[RiskEvent] = field(default_factory=list)
    error_logs: list[dict[str, str]] = field(default_factory=list)
    audit_logs: list[dict[str, str]] = field(default_factory=list)


class ExchangeAdapter(Protocol):
    def get_balance(self) -> Balance: ...
    def get_price(self, symbol: str) -> Decimal: ...
    def get_candles(self, symbol: str) -> list[Candle]: ...
    def get_order_book(self, symbol: str) -> OrderBook: ...
    def get_open_positions(self) -> list[SimulatedPosition]: ...
    def place_order(self, signal: TradeSignal, quantity: Decimal, price: Decimal) -> SimulatedOrder: ...
    def cancel_order(self, order_id: str) -> SimulatedOrder | None: ...
    def get_order_status(self, order_id: str) -> OrderStatus | None: ...


class MarketDataProvider(Protocol):
    def price(self, symbol: str) -> Decimal: ...
    def candles(self, symbol: str) -> list[Candle]: ...
    def order_book(self, symbol: str) -> OrderBook: ...


class OrderExecutor(Protocol):
    def execute(self, signal: TradeSignal) -> SimulatedOrder | None: ...


class PositionManager(Protocol):
    def open_from_order(self, order: SimulatedOrder) -> SimulatedPosition | None: ...
    def close_position(self, position_id: str, reason: str) -> dict[str, str] | None: ...


class CopySignalProvider(Protocol):
    def next_signal(self) -> TradeSignal | None: ...


class NotificationProvider(Protocol):
    def notify(self, event: str, message: str) -> NotificationRecord: ...


class StorageProvider(Protocol):
    def snapshot(self) -> dict[str, object]: ...


class RiskManager(Protocol):
    def approve(self, signal: TradeSignal, quantity: Decimal, price: Decimal) -> tuple[bool, str, str]: ...


class StrategyEngine(Protocol):
    def evaluate(self) -> list[TradeSignal]: ...


class MockExchangeAdapter:
    def __init__(self, state: BotRuntimeState) -> None:
        self.state = state

    def get_balance(self) -> Balance:
        equity = Decimal("10000") + self.state.daily_realized_pnl + sum((p.unrealized_pnl for p in self.state.positions), Decimal("0"))
        reserved = sum((p.notional / Decimal("10") for p in self.state.positions), Decimal("0"))
        return Balance(total=equity, available=max(Decimal("0"), equity - reserved))

    def get_price(self, symbol: str) -> Decimal:
        base = {"BTC-USDT": Decimal("65000"), "ETH-USDT": Decimal("3500"), "SOL-USDT": Decimal("155")}.get(symbol, Decimal("100"))
        scenario_shift = {
            MockScenario.BULLISH_VOLUME_BREAKOUT: Decimal("1.015"),
            MockScenario.BEARISH_VOLUME_BREAKDOWN: Decimal("0.985"),
            MockScenario.STOP_LOSS_HIT: Decimal("0.970"),
            MockScenario.TAKE_PROFIT_HIT: Decimal("1.045"),
        }.get(self.state.scenario, Decimal("1"))
        tick = Decimal(datetime.now(UTC).second % 10) / Decimal("10000")
        return (base * scenario_shift * (Decimal("1") + tick)).quantize(Decimal("0.01"))

    def get_candles(self, symbol: str) -> list[Candle]:
        price = self.get_price(symbol)
        volume = Decimal("500")
        if self.state.scenario in {MockScenario.BULLISH_VOLUME_BREAKOUT, MockScenario.BEARISH_VOLUME_BREAKDOWN}:
            volume = Decimal("1800")
        candles = []
        for i in range(20):
            candle_volume = volume if i == 0 else Decimal("500") + Decimal(i * 5)
            candles.append(
                Candle(
                    symbol,
                    price - Decimal(i),
                    price + Decimal("2"),
                    price - Decimal("3"),
                    price,
                    candle_volume,
                    datetime.now(UTC).isoformat(),
                )
            )
        return candles

    def get_order_book(self, symbol: str) -> OrderBook:
        price = self.get_price(symbol)
        spread = Decimal("0.0005") if self.state.scenario != MockScenario.HIGH_SPREAD_NO_TRADE else Decimal("0.01")
        bid = (price * (Decimal("1") - spread)).quantize(Decimal("0.01"))
        ask = (price * (Decimal("1") + spread)).quantize(Decimal("0.01"))
        return OrderBook(symbol, bid, ask, Decimal("20"), Decimal("18"))

    def get_open_positions(self) -> list[SimulatedPosition]:
        return self.state.positions

    def place_order(self, signal: TradeSignal, quantity: Decimal, price: Decimal) -> SimulatedOrder:
        status = OrderStatus.REJECTED if self.state.scenario == MockScenario.ORDER_REJECTION else OrderStatus.FILLED
        order = SimulatedOrder(
            str(uuid4()),
            signal.symbol,
            signal.side,
            OrderType.MARKET,
            quantity,
            price,
            status,
            signal.strategy,
            datetime.now(UTC).isoformat(),
        )
        self.state.orders.insert(0, order)
        return order

    def cancel_order(self, order_id: str) -> SimulatedOrder | None:
        for order in self.state.orders:
            if order.id == order_id:
                order.status = OrderStatus.CANCELLED
                return order
        return None

    def get_order_status(self, order_id: str) -> OrderStatus | None:
        for order in self.state.orders:
            if order.id == order_id:
                return order.status
        return None


class BingXLiveExchangeAdapter:
    def __init__(self, enable_live_trading: bool) -> None:
        self.enable_live_trading = enable_live_trading
        if not enable_live_trading:
            raise RuntimeError("LIVE adapter is blocked until ENABLE_LIVE_TRADING=true")


class MockMarketDataProvider:
    def __init__(self, exchange: MockExchangeAdapter) -> None:
        self.exchange = exchange

    def price(self, symbol: str) -> Decimal:
        return self.exchange.get_price(symbol)

    def candles(self, symbol: str) -> list[Candle]:
        return self.exchange.get_candles(symbol)

    def order_book(self, symbol: str) -> OrderBook:
        return self.exchange.get_order_book(symbol)


class LiveMarketDataProvider:
    def __init__(self, live_adapter: BingXLiveExchangeAdapter) -> None:
        self.live_adapter = live_adapter


class MockCopySignalProvider:
    def __init__(self, state: BotRuntimeState) -> None:
        self.state = state

    def next_signal(self) -> TradeSignal | None:
        mapping = {
            MockScenario.LEAD_TRADER_OPENS_LONG: (Side.BUY, SignalAction.OPEN, "lead trader opened long"),
            MockScenario.LEAD_TRADER_OPENS_SHORT: (Side.SELL, SignalAction.OPEN, "lead trader opened short"),
            MockScenario.LEAD_TRADER_CLOSES_POSITION: (Side.SELL, SignalAction.CLOSE, "lead trader closed position"),
        }
        if self.state.scenario not in mapping or self.state.copy_state == StrategyState.PAUSED:
            return None
        side, action, reason = mapping[self.state.scenario]
        return TradeSignal(
            str(uuid4()), StrategyName.COPY, "BTC-USDT", side, action, Decimal("0.90"), reason, datetime.now(UTC).isoformat()
        )


class ExternalSignalProvider:
    def __init__(self) -> None:
        self.source = "external_authenticated_api"


class VolumeMomentumEngine:
    def __init__(self, state: BotRuntimeState, market_data: MarketDataProvider, config: BotConfig) -> None:
        self.state = state
        self.market_data = market_data
        self.config = config

    def evaluate(self) -> list[TradeSignal]:
        if self.state.volume_state == StrategyState.PAUSED:
            return []
        symbol = "BTC-USDT"
        candles = self.market_data.candles(symbol)
        order_book = self.market_data.order_book(symbol)
        spread_percent = (order_book.ask - order_book.bid) / order_book.bid * Decimal("100")
        avg_volume = sum((c.volume for c in candles[1:]), Decimal("0")) / Decimal(len(candles[1:]))
        latest = candles[0]
        volume_spike = latest.volume >= avg_volume * self.config.volume_spike_multiplier
        high_spread = spread_percent > self.config.max_spread_percent
        if high_spread:
            self.state.risk_events.insert(
                0, RiskEvent(str(uuid4()), "MAX_SPREAD", "high spread blocked volume signal", datetime.now(UTC).isoformat())
            )
            return []
        if self.state.scenario == MockScenario.BULLISH_VOLUME_BREAKOUT and volume_spike:
            return [
                TradeSignal(
                    str(uuid4()),
                    StrategyName.VOLUME,
                    symbol,
                    Side.BUY,
                    SignalAction.OPEN,
                    Decimal("0.82"),
                    "mock bullish volume breakout",
                    datetime.now(UTC).isoformat(),
                )
            ]
        if self.state.scenario == MockScenario.BEARISH_VOLUME_BREAKDOWN and volume_spike:
            return [
                TradeSignal(
                    str(uuid4()),
                    StrategyName.VOLUME,
                    symbol,
                    Side.SELL,
                    SignalAction.OPEN,
                    Decimal("0.82"),
                    "mock bearish volume breakdown",
                    datetime.now(UTC).isoformat(),
                )
            ]
        return []


class SharedRiskManager:
    def __init__(self, state: BotRuntimeState, exchange: MockExchangeAdapter, config: BotConfig) -> None:
        self.state = state
        self.exchange = exchange
        self.config = config

    def approve(self, signal: TradeSignal, quantity: Decimal, price: Decimal) -> tuple[bool, str, str]:
        if self.state.bot_state == BotState.EMERGENCY_STOPPED:
            return self._reject("EMERGENCY_STOP", "emergency stop is active")
        if self.state.scenario == MockScenario.API_CONNECTION_FAILURE:
            self.state.api_connected = False
            return self._reject("API_CONNECTION_FAILURE", "mock API connection failure")
        if self.state.daily_realized_pnl <= -self.config.max_daily_loss or self.state.scenario == MockScenario.DAILY_LOSS_LIMIT_HIT:
            return self._reject("DAILY_LOSS_LIMIT", "daily loss limit reached")
        if len(self.state.positions) >= self.config.max_open_positions:
            return self._reject("MAX_OPEN_POSITIONS", "maximum simultaneous positions reached")
        if price * quantity > self.config.max_position_size:
            return self._reject("MAX_POSITION_SIZE", "position size exceeds configured maximum")
        for position in self.state.positions:
            if position.symbol == signal.symbol and position.side != signal.side:
                if self.config.conflict_policy == "REJECT_NEW_SIGNAL":
                    return self._reject("STRATEGY_CONFLICT", "opposite signal conflicts with existing position")
        return True, "ACCEPTED", "risk accepted"

    def _reject(self, code: str, explanation: str) -> tuple[bool, str, str]:
        self.state.risk_events.insert(0, RiskEvent(str(uuid4()), code, explanation, datetime.now(UTC).isoformat()))
        return False, code, explanation


class MockOrderExecutor:
    def __init__(
        self, state: BotRuntimeState, exchange: MockExchangeAdapter, risk: RiskManager, notifications: NotificationProvider
    ) -> None:
        self.state = state
        self.exchange = exchange
        self.risk = risk
        self.notifications = notifications

    def execute(self, signal: TradeSignal) -> SimulatedOrder | None:
        price = self.exchange.get_price(signal.symbol)
        quantity = Decimal("0.01") if signal.strategy == StrategyName.COPY else Decimal("0.02")
        approved, reason, explanation = self.risk.approve(signal, quantity, price)
        self.state.signals.insert(0, signal)
        if not approved:
            self.notifications.notify("Risk rejection", f"{signal.strategy} {signal.symbol}: {reason} - {explanation}")
            return None
        order = self.exchange.place_order(signal, quantity, price)
        if order.status == OrderStatus.REJECTED:
            self.state.risk_events.insert(
                0, RiskEvent(str(uuid4()), "ORDER_REJECTED", "mock exchange rejected order", datetime.now(UTC).isoformat())
            )
            self.notifications.notify("Order rejected", f"Mock exchange rejected {signal.symbol}")
        else:
            self.notifications.notify("Trade opened", f"{signal.strategy} opened {signal.side} {signal.symbol} in mock mode")
        return order


class LiveOrderExecutor:
    def __init__(self, live_adapter: BingXLiveExchangeAdapter) -> None:
        self.live_adapter = live_adapter


class MockPositionManager:
    def __init__(self, state: BotRuntimeState, exchange: MockExchangeAdapter, config: BotConfig) -> None:
        self.state = state
        self.exchange = exchange
        self.config = config

    def open_from_order(self, order: SimulatedOrder) -> SimulatedPosition | None:
        if order.status != OrderStatus.FILLED:
            return None
        if any(position.symbol == order.symbol and position.strategy == order.strategy for position in self.state.positions):
            return None
        stop_loss = (order.price * (Decimal("1") - self.config.mandatory_stop_loss_percent)).quantize(Decimal("0.01"))
        take_profit = (order.price * (Decimal("1") + self.config.take_profit_percent)).quantize(Decimal("0.01"))
        if order.side == Side.SELL:
            stop_loss = (order.price * (Decimal("1") + self.config.mandatory_stop_loss_percent)).quantize(Decimal("0.01"))
            take_profit = (order.price * (Decimal("1") - self.config.take_profit_percent)).quantize(Decimal("0.01"))
        position = SimulatedPosition(
            str(uuid4()),
            order.symbol,
            order.side,
            order.quantity,
            order.price,
            order.price,
            stop_loss,
            take_profit,
            None,
            order.strategy,
            datetime.now(UTC).isoformat(),
        )
        self.state.positions.insert(0, position)
        return position

    def close_position(self, position_id: str, reason: str) -> dict[str, str] | None:
        for position in list(self.state.positions):
            if position.id == position_id:
                self.state.positions.remove(position)
                realized = position.unrealized_pnl.quantize(Decimal("0.01"))
                self.state.daily_realized_pnl += realized
                closed = {
                    "position_id": position.id,
                    "symbol": position.symbol,
                    "reason": reason,
                    "realized_pnl": str(realized),
                    "closed_at": datetime.now(UTC).isoformat(),
                }
                self.state.closed_trades.insert(0, closed)
                return closed
        return None


class MockNotificationProvider:
    def __init__(self, state: BotRuntimeState) -> None:
        self.state = state

    def notify(self, event: str, message: str) -> NotificationRecord:
        record = NotificationRecord(str(uuid4()), "MOCK_PREVIEW", event, message, False, datetime.now(UTC).isoformat())
        self.state.notifications.insert(0, record)
        return record


class TelegramNotificationProvider:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled

    def notify(self, event: str, message: str) -> NotificationRecord:
        if not self.enabled:
            return NotificationRecord(str(uuid4()), "TELEGRAM_DISABLED", event, message, False, datetime.now(UTC).isoformat())
        return NotificationRecord(
            str(uuid4()), "TELEGRAM", event, "message redacted for provider handoff", True, datetime.now(UTC).isoformat()
        )


class InMemoryMockStorageProvider:
    def __init__(self, state: BotRuntimeState) -> None:
        self.state = state

    def snapshot(self) -> dict[str, object]:
        return serialize_state(self.state)


class DatabaseStorageProvider:
    def __init__(self) -> None:
        self.provider = "database"


class TradingApplication:
    def __init__(self, config: BotConfig | None = None) -> None:
        self.config = config or BotConfig()
        self.state = BotRuntimeState()
        self.exchange = MockExchangeAdapter(self.state)
        self.market_data = MockMarketDataProvider(self.exchange)
        self.notifications = MockNotificationProvider(self.state)
        self.risk = SharedRiskManager(self.state, self.exchange, self.config)
        self.order_executor = MockOrderExecutor(self.state, self.exchange, self.risk, self.notifications)
        self.position_manager = MockPositionManager(self.state, self.exchange, self.config)
        self.copy_signals = MockCopySignalProvider(self.state)
        self.volume_engine = VolumeMomentumEngine(self.state, self.market_data, self.config)
        self.storage = InMemoryMockStorageProvider(self.state)
        self.notifications.notify("Bot started", "Mock bot runtime initialized")

    def apply_scenario(self, scenario: MockScenario) -> dict[str, object]:
        self.state.scenario = scenario
        self.state.api_connected = scenario != MockScenario.API_CONNECTION_FAILURE
        self.state.audit_logs.insert(
            0, {"action": "SCENARIO_APPLIED", "scenario": scenario.value, "created_at": datetime.now(UTC).isoformat()}
        )
        if scenario == MockScenario.EMERGENCY_STOP:
            self.emergency_stop()
        elif scenario == MockScenario.LEAD_TRADER_CLOSES_POSITION and self.state.positions:
            self.position_manager.close_position(self.state.positions[0].id, "lead trader closes position")
        else:
            self.run_once()
        return self.dashboard_snapshot()

    def run_once(self) -> None:
        if self.state.bot_state != BotState.RUNNING:
            return
        signals: list[TradeSignal] = []
        copy_signal = self.copy_signals.next_signal()
        if copy_signal:
            signals.append(copy_signal)
            self.notifications.notify("Copy signal received", copy_signal.reason)
        signals.extend(self.volume_engine.evaluate())
        for signal in signals:
            if self._is_duplicate_signal(signal):
                self.state.risk_events.insert(
                    0, RiskEvent(str(uuid4()), "DUPLICATE_SIGNAL", "duplicate mock signal ignored", datetime.now(UTC).isoformat())
                )
                continue
            order = self.order_executor.execute(signal)
            if order:
                self.position_manager.open_from_order(order)
        self._apply_mock_exit_scenarios()

    def _is_duplicate_signal(self, signal: TradeSignal) -> bool:
        return any(
            existing.strategy == signal.strategy and existing.symbol == signal.symbol and existing.reason == signal.reason
            for existing in self.state.signals[:5]
        )

    def _apply_mock_exit_scenarios(self) -> None:
        if not self.state.positions:
            return
        if self.state.scenario == MockScenario.STOP_LOSS_HIT:
            self.notifications.notify("Stop-loss triggered", "Mock stop-loss event closed the oldest position")
            self.position_manager.close_position(self.state.positions[0].id, "stop-loss hit")
        if self.state.scenario == MockScenario.TAKE_PROFIT_HIT:
            self.notifications.notify("Take-profit triggered", "Mock take-profit event closed the oldest position")
            self.position_manager.close_position(self.state.positions[0].id, "take-profit hit")

    def start(self) -> dict[str, object]:
        self.state.bot_state = BotState.RUNNING
        self.notifications.notify("Bot started", "Bot started in mock mode")
        return self.dashboard_snapshot()

    def stop(self) -> dict[str, object]:
        self.state.bot_state = BotState.STOPPED
        self.notifications.notify("Bot stopped", "Bot stopped by operator")
        return self.dashboard_snapshot()

    def pause_strategy(self, strategy: StrategyName) -> dict[str, object]:
        if strategy == StrategyName.COPY:
            self.state.copy_state = StrategyState.PAUSED
        if strategy == StrategyName.VOLUME:
            self.state.volume_state = StrategyState.PAUSED
        self.notifications.notify("Strategy paused", f"{strategy} strategy paused")
        return self.dashboard_snapshot()

    def resume_strategy(self, strategy: StrategyName) -> dict[str, object]:
        if strategy == StrategyName.COPY:
            self.state.copy_state = StrategyState.RUNNING
        if strategy == StrategyName.VOLUME:
            self.state.volume_state = StrategyState.RUNNING
        self.notifications.notify("Strategy resumed", f"{strategy} strategy resumed")
        return self.dashboard_snapshot()

    def emergency_stop(self) -> dict[str, object]:
        self.state.bot_state = BotState.EMERGENCY_STOPPED
        for position in list(self.state.positions):
            self.position_manager.close_position(position.id, "emergency close-all")
        self.notifications.notify("Emergency shutdown", "Emergency stop activated and mock positions closed")
        return self.dashboard_snapshot()

    def dashboard_snapshot(self) -> dict[str, object]:
        self.run_once()
        return serialize_state(self.state) | {
            "config": serialize_config(self.config),
            "balance": serialize_balance(self.exchange.get_balance()),
            "scenario_options": [scenario.value for scenario in MockScenario],
            "reports": self.reports(),
        }

    def reports(self) -> dict[str, object]:
        realized = self.state.daily_realized_pnl.quantize(Decimal("0.01"))
        unrealized = sum((p.unrealized_pnl for p in self.state.positions), Decimal("0")).quantize(Decimal("0.01"))
        return {
            "daily_pnl_report": {
                "realized": str(realized),
                "unrealized": str(unrealized),
                "total": str((realized + unrealized).quantize(Decimal("0.01"))),
            },
            "strategy_performance_report": {
                "copy_open_positions": str(sum(1 for p in self.state.positions if p.strategy == StrategyName.COPY)),
                "volume_open_positions": str(sum(1 for p in self.state.positions if p.strategy == StrategyName.VOLUME)),
            },
            "trade_history_report": self.state.closed_trades[:20],
            "risk_event_report": [event.__dict__ for event in self.state.risk_events[:20]],
            "mock_demo_report": {
                "scenario": self.state.scenario.value,
                "orders": len(self.state.orders),
                "signals": len(self.state.signals),
            },
        }


def serialize_decimal(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def serialize_balance(balance: Balance) -> dict[str, str]:
    return {"asset": balance.asset, "total": serialize_decimal(balance.total), "available": serialize_decimal(balance.available)}


def serialize_config(config: BotConfig) -> dict[str, object]:
    return {
        "mode": config.mode.value,
        "enable_live_trading": config.enable_live_trading,
        "trading_pairs": list(config.trading_pairs),
        "risk_per_trade": str(config.risk_per_trade),
        "max_daily_loss": str(config.max_daily_loss),
        "max_drawdown": str(config.max_drawdown),
        "max_open_positions": config.max_open_positions,
        "max_position_size": str(config.max_position_size),
        "max_leverage": str(config.max_leverage),
        "conflict_policy": config.conflict_policy,
    }


def serialize_state(state: BotRuntimeState) -> dict[str, object]:
    return {
        "bot_state": state.bot_state.value,
        "copy_state": state.copy_state.value,
        "volume_state": state.volume_state.value,
        "scenario": state.scenario.value,
        "api_connected": state.api_connected,
        "open_positions": [serialize_position(position) for position in state.positions[:20]],
        "closed_trades": state.closed_trades[:20],
        "signals": [
            signal.__dict__ | {"strategy": signal.strategy.value, "side": signal.side.value, "action": signal.action.value}
            for signal in state.signals[:20]
        ],
        "orders": [serialize_order(order) for order in state.orders[:20]],
        "notifications": [record.__dict__ for record in state.notifications[:20]],
        "risk_events": [event.__dict__ for event in state.risk_events[:20]],
        "error_logs": state.error_logs[:20],
        "audit_logs": state.audit_logs[:20],
    }


def serialize_order(order: SimulatedOrder) -> dict[str, str]:
    return {
        "id": order.id,
        "symbol": order.symbol,
        "side": order.side.value,
        "order_type": order.order_type.value,
        "quantity": str(order.quantity),
        "price": serialize_decimal(order.price),
        "status": order.status.value,
        "strategy": order.strategy.value,
        "created_at": order.created_at,
    }


def serialize_position(position: SimulatedPosition) -> dict[str, str]:
    return {
        "id": position.id,
        "symbol": position.symbol,
        "side": position.side.value,
        "quantity": str(position.quantity),
        "entry_price": serialize_decimal(position.entry_price),
        "mark_price": serialize_decimal(position.mark_price),
        "notional": serialize_decimal(position.notional),
        "unrealized_pnl": serialize_decimal(position.unrealized_pnl),
        "stop_loss": serialize_decimal(position.stop_loss),
        "take_profit": serialize_decimal(position.take_profit),
        "trailing_stop": str(position.trailing_stop) if position.trailing_stop else "",
        "strategy": position.strategy.value,
        "opened_at": position.opened_at,
    }
