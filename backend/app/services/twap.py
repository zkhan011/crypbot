from dataclasses import dataclass
from decimal import Decimal
from app.domain.types import Side, quantize_down


@dataclass(frozen=True)
class TwapPlan:
    symbol: str
    side: Side
    total_quantity: Decimal
    slices: int
    min_slice: Decimal
    max_slice: Decimal
    objective: str
    live_confirmed: bool = False


class TwapStrategy:
    def build_slices(self, plan: TwapPlan, step: Decimal) -> list[Decimal]:
        if not plan.objective:
            raise ValueError("legitimate execution objective is required")
        if plan.slices <= 0:
            raise ValueError("slices must be positive")
        raw = plan.total_quantity / Decimal(plan.slices)
        qty = min(max(raw, plan.min_slice), plan.max_slice)
        rounded = quantize_down(qty, step)
        return [rounded for _ in range(plan.slices)]
