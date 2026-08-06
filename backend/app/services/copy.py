from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from app.domain.trading_types import CopyInstructionState, Side, quantize_down
from app.services.risk import RiskEngine, RiskOrder, RiskProfile, RiskDecision


@dataclass
class CopyInstruction:
    id: str
    master_event_id: str
    follower_account_id: str
    symbol: str
    side: Side
    target_quantity: Decimal
    state: CopyInstructionState = CopyInstructionState.RECEIVED
    risk_reason: str | None = None


class CopySizingMode(StrEnum):
    FIXED_QUANTITY = "FIXED_QUANTITY"
    FIXED_USDT = "FIXED_USDT"
    BALANCE_PERCENTAGE = "BALANCE_PERCENTAGE"
    LEADER_QUANTITY_RATIO = "LEADER_QUANTITY_RATIO"
    LEADER_EQUITY_RATIO = "LEADER_EQUITY_RATIO"
    MULTIPLIER = "MULTIPLIER"


@dataclass(frozen=True)
class CopySizingRequest:
    mode: CopySizingMode
    price: Decimal
    follower_balance: Decimal
    leader_quantity: Decimal
    leader_equity: Decimal
    fixed_quantity: Decimal = Decimal("0")
    fixed_usdt: Decimal = Decimal("0")
    balance_percentage: Decimal = Decimal("0")
    ratio: Decimal = Decimal("0")
    multiplier: Decimal = Decimal("1")


class CopySizingService:
    def calculate(self, request: CopySizingRequest, quantity_step: Decimal) -> Decimal:
        if request.price <= 0 or quantity_step <= 0:
            raise ValueError("price and quantity step must be positive")
        values = {
            CopySizingMode.FIXED_QUANTITY: request.fixed_quantity,
            CopySizingMode.FIXED_USDT: request.fixed_usdt / request.price,
            CopySizingMode.BALANCE_PERCENTAGE: request.follower_balance * request.balance_percentage / request.price,
            CopySizingMode.LEADER_QUANTITY_RATIO: request.leader_quantity * request.ratio,
            CopySizingMode.LEADER_EQUITY_RATIO: request.follower_balance / request.leader_equity * request.leader_quantity
            if request.leader_equity > 0
            else Decimal("0"),
            CopySizingMode.MULTIPLIER: request.leader_quantity * request.multiplier,
        }
        quantity = quantize_down(values[request.mode], quantity_step)
        if quantity <= 0:
            raise ValueError("copy sizing normalized to zero")
        return quantity


class CopyEventDeduplicator:
    def __init__(self) -> None:
        self._seen: set[str] = set()

    def accept(self, source_event_id: str) -> bool:
        if source_event_id in self._seen:
            return False
        self._seen.add(source_event_id)
        return True


class CopyStateMachine:
    allowed = {
        CopyInstructionState.RECEIVED: {CopyInstructionState.VALIDATING},
        CopyInstructionState.VALIDATING: {CopyInstructionState.READY, CopyInstructionState.RISK_REJECTED, CopyInstructionState.FAILED},
        CopyInstructionState.READY: {CopyInstructionState.SUBMITTING},
        CopyInstructionState.SUBMITTING: {
            CopyInstructionState.SUBMITTED,
            CopyInstructionState.FAILED,
            CopyInstructionState.RECONCILIATION_REQUIRED,
        },
        CopyInstructionState.SUBMITTED: {
            CopyInstructionState.PARTIALLY_FILLED,
            CopyInstructionState.FILLED,
            CopyInstructionState.CANCELLED,
            CopyInstructionState.RECONCILIATION_REQUIRED,
        },
        CopyInstructionState.PARTIALLY_FILLED: {
            CopyInstructionState.FILLED,
            CopyInstructionState.CANCELLED,
            CopyInstructionState.RECONCILIATION_REQUIRED,
        },
    }

    def transition(self, instruction: CopyInstruction, new_state: CopyInstructionState) -> None:
        if new_state not in self.allowed.get(instruction.state, set()):
            raise ValueError(f"invalid transition {instruction.state}->{new_state}")
        instruction.state = new_state


class CopyTradingEngine:
    def __init__(self, risk: RiskEngine):
        self.risk = risk
        self.sm = CopyStateMachine()

    def create_instruction(
        self, event_id: str, follower_id: str, symbol: str, side: Side, master_qty: Decimal, multiplier: Decimal, step: Decimal
    ) -> CopyInstruction:
        qty = quantize_down(master_qty * multiplier, step)
        return CopyInstruction(f"copy-{event_id}-{follower_id}", event_id, follower_id, symbol, side, qty)

    def validate(
        self, instruction: CopyInstruction, price: Decimal, leverage: Decimal, equity: Decimal, profile: RiskProfile
    ) -> RiskDecision:
        self.sm.transition(instruction, CopyInstructionState.VALIDATING)
        decision = self.risk.evaluate(
            RiskOrder(instruction.symbol, instruction.side, instruction.target_quantity, price, leverage, equity), profile
        )
        if decision.accepted:
            self.sm.transition(instruction, CopyInstructionState.READY)
        else:
            instruction.risk_reason = decision.reason_code
            self.sm.transition(instruction, CopyInstructionState.RISK_REJECTED)
        return decision
