from dataclasses import fields, replace

import pytest

from app.services.production_readiness import ProductionReadinessEvidence, ProductionReadinessGate, ReadinessSeverity


def complete_evidence() -> ProductionReadinessEvidence:
    return ProductionReadinessEvidence(**{field.name: True for field in fields(ProductionReadinessEvidence)})


@pytest.mark.parametrize("missing", [field.name for field in fields(ProductionReadinessEvidence)])
def test_every_readiness_prerequisite_independently_blocks_opening_orders(missing: str) -> None:
    gate = ProductionReadinessGate()
    evidence = replace(complete_evidence(), **{missing: False})
    report = gate.public_report(evidence)
    assert report["opening_orders_allowed"] is False
    check = next(item for item in report["checks"] if item["id"] == missing)
    assert check["passed"] is False
    assert check["explanation"]


def test_complete_server_evidence_is_live_ready_without_a_bypass_flag() -> None:
    gate = ProductionReadinessGate()
    report = gate.public_report(complete_evidence())
    assert report["state"] == "LIVE_READY"
    assert report["opening_orders_allowed"] is True
    assert report["startup_fatal"] is False


def test_startup_fatal_and_trading_pause_failures_are_distinguished() -> None:
    gate = ProductionReadinessGate()
    startup = replace(complete_evidence(), postgres_reachable=False)
    paused = replace(complete_evidence(), reconciliation_complete=False)
    assert gate.startup_fatal(startup)
    assert not gate.startup_fatal(paused)
    checks = {check.check_id: check for check in gate.evaluate(paused)}
    assert checks["reconciliation_complete"].severity == ReadinessSeverity.TRADING_PAUSE
