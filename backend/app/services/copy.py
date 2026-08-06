from dataclasses import dataclass
from decimal import Decimal
from app.domain.types import CopyInstructionState, Side, quantize_down
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
