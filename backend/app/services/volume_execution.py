from dataclasses import dataclass
from decimal import Decimal

from app.domain.types import Side, quantize_down


@dataclass(frozen=True)
class VolumeExecutionPlan:
    symbol: str
    side: Side
    target_quantity: Decimal
    slices: int
    observed_market_volume: Decimal
    max_participation_rate: Decimal
    objective: str
    min_child_quantity: Decimal = Decimal("0")
    max_child_quantity: Decimal | None = None


@dataclass(frozen=True)
class VolumeChildOrder:
    slice: int
    quantity: Decimal
    max_market_volume_quantity: Decimal


class VolumeExecutionStrategy:
    """Builds participation-capped execution slices for legitimate execution only.

    This service is deliberately not a fake-volume generator. It caps child order size as a
    fraction of observed market volume and requires a legitimate execution objective.
    """

    def build_child_orders(self, plan: VolumeExecutionPlan, quantity_step: Decimal) -> list[VolumeChildOrder]:
        self._validate(plan)
        per_slice_target = plan.target_quantity / Decimal(plan.slices)
        participation_cap = plan.observed_market_volume * plan.max_participation_rate / Decimal(plan.slices)
        raw_child_quantity = min(per_slice_target, participation_cap)
        if plan.max_child_quantity is not None:
            raw_child_quantity = min(raw_child_quantity, plan.max_child_quantity)
        raw_child_quantity = max(raw_child_quantity, plan.min_child_quantity)
        child_quantity = quantize_down(raw_child_quantity, quantity_step)
        return [
            VolumeChildOrder(
                slice=index + 1,
                quantity=child_quantity,
                max_market_volume_quantity=quantize_down(participation_cap, quantity_step),
            )
            for index in range(plan.slices)
        ]

    @staticmethod
    def _validate(plan: VolumeExecutionPlan) -> None:
        if not plan.objective.strip():
            raise ValueError("legitimate execution objective is required")
        if plan.slices <= 0:
            raise ValueError("slices must be positive")
        if plan.target_quantity <= 0:
            raise ValueError("target quantity must be positive")
        if plan.observed_market_volume <= 0:
            raise ValueError("observed market volume must be positive")
        if plan.max_participation_rate <= 0 or plan.max_participation_rate > Decimal("0.2"):
            raise ValueError("max participation rate must be between 0 and 0.2")
