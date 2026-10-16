"""Central fail-closed evidence gate for production and LIVE opening orders."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ReadinessSeverity(StrEnum):
    STARTUP_FATAL = "STARTUP_FATAL"
    TRADING_PAUSE = "TRADING_PAUSE"


@dataclass(frozen=True)
class ReadinessCheck:
    check_id: str
    passed: bool
    severity: ReadinessSeverity
    explanation: str


@dataclass(frozen=True)
class ProductionReadinessEvidence:
    correct_environment: bool = False
    postgres_reachable: bool = False
    migrations_current: bool = False
    demo_users_disabled: bool = False
    durable_identity_active: bool = False
    encryption_provider_healthy: bool = False
    credentials_verified: bool = False
    credentials_not_revoked: bool = False
    withdrawal_control_approved: bool = False
    account_binding_valid: bool = False
    strategy_version_approved: bool = False
    risk_profile_version_approved: bool = False
    final_confirmation_valid: bool = False
    audit_persistence_healthy: bool = False
    audit_chain_valid: bool = False
    worker_lease_acquired: bool = False
    reconciliation_complete: bool = False
    market_data_fresh: bool = False
    clock_synchronized: bool = False
    kill_switches_inactive: bool = False
    monitoring_healthy: bool = False


class ProductionReadinessGate:
    """Evaluates server-derived evidence; it has no environment bypass."""

    _CHECKS: tuple[tuple[str, ReadinessSeverity, str], ...] = (
        ("correct_environment", ReadinessSeverity.STARTUP_FATAL, "production environment and LIVE execution mode must agree"),
        ("postgres_reachable", ReadinessSeverity.STARTUP_FATAL, "PostgreSQL must be reachable"),
        ("migrations_current", ReadinessSeverity.STARTUP_FATAL, "database migrations must be at the expected head"),
        ("demo_users_disabled", ReadinessSeverity.STARTUP_FATAL, "demo-user seeding must be disabled"),
        ("durable_identity_active", ReadinessSeverity.STARTUP_FATAL, "durable identity and sessions must be active"),
        ("encryption_provider_healthy", ReadinessSeverity.STARTUP_FATAL, "credential encryption provider must be healthy"),
        ("credentials_verified", ReadinessSeverity.TRADING_PAUSE, "BingX credentials require read-only verification"),
        ("credentials_not_revoked", ReadinessSeverity.TRADING_PAUSE, "bound credentials must not be revoked"),
        ("withdrawal_control_approved", ReadinessSeverity.TRADING_PAUSE, "withdrawal-disabled evidence or manual approval is required"),
        ("account_binding_valid", ReadinessSeverity.TRADING_PAUSE, "tenant bot account binding must be valid"),
        ("strategy_version_approved", ReadinessSeverity.TRADING_PAUSE, "the exact strategy version must be approved"),
        ("risk_profile_version_approved", ReadinessSeverity.TRADING_PAUSE, "the exact risk profile version must be approved"),
        ("final_confirmation_valid", ReadinessSeverity.TRADING_PAUSE, "component-bound final LIVE confirmation is required"),
        ("audit_persistence_healthy", ReadinessSeverity.STARTUP_FATAL, "append-only audit persistence must be writable"),
        ("audit_chain_valid", ReadinessSeverity.TRADING_PAUSE, "audit hash chain must verify"),
        ("worker_lease_acquired", ReadinessSeverity.TRADING_PAUSE, "the account worker lease must be acquired"),
        ("reconciliation_complete", ReadinessSeverity.TRADING_PAUSE, "startup reconciliation must complete without unresolved incidents"),
        ("market_data_fresh", ReadinessSeverity.TRADING_PAUSE, "market data must be fresh"),
        ("clock_synchronized", ReadinessSeverity.TRADING_PAUSE, "exchange clock drift must be within tolerance"),
        ("kill_switches_inactive", ReadinessSeverity.TRADING_PAUSE, "global, tenant, account, and bot kill switches must be inactive"),
        ("monitoring_healthy", ReadinessSeverity.TRADING_PAUSE, "required monitoring must be healthy"),
    )

    def evaluate(self, evidence: ProductionReadinessEvidence) -> tuple[ReadinessCheck, ...]:
        return tuple(
            ReadinessCheck(check_id, bool(getattr(evidence, check_id)), severity, explanation)
            for check_id, severity, explanation in self._CHECKS
        )

    def opening_orders_allowed(self, evidence: ProductionReadinessEvidence) -> bool:
        return all(check.passed for check in self.evaluate(evidence))

    def startup_fatal(self, evidence: ProductionReadinessEvidence) -> bool:
        return any(not check.passed and check.severity == ReadinessSeverity.STARTUP_FATAL for check in self.evaluate(evidence))

    def public_report(self, evidence: ProductionReadinessEvidence) -> dict[str, object]:
        checks = self.evaluate(evidence)
        return {
            "state": "LIVE_READY" if all(check.passed for check in checks) else "LIVE_PAUSED",
            "opening_orders_allowed": all(check.passed for check in checks),
            "startup_fatal": any(not check.passed and check.severity == ReadinessSeverity.STARTUP_FATAL for check in checks),
            "checks": [
                {
                    "id": check.check_id,
                    "passed": check.passed,
                    "severity": check.severity.value,
                    "explanation": check.explanation,
                }
                for check in checks
            ],
        }
