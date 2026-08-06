# Production readiness traceability

| Requirement | Implementation | Automated evidence | Current status |
|---|---|---|---|
| Central fail-closed LIVE gate | `app/services/production_readiness.py` | `tests/test_production_readiness.py` | Implemented |
| Machine-readable check IDs/severity | `ProductionReadinessGate.public_report` | per-check parameterized test | Implemented |
| No demo control plane in production | conditional construction in `app/main.py` | production configuration tests | Implemented |
| No MOCK trading runtime in LIVE | conditional construction in `app/main.py` | runtime guard tests pending | Implemented, test gap |
| Durable identity/session runtime | repository schema foundations | PostgreSQL integration tests | Not implemented |
| Credential verification lifecycle | encrypted facade and adapter reads | verification integration tests | Partial |
| Strategy/risk approval versions | schema foundations | repository integration tests | Partial |
| Durable worker leases | background-job schema only | concurrency integration tests | Not implemented |
| Startup reconciliation evidence | reconciliation service foundations | fake exchange tests | Partial |
| Audit persistence/integrity | hash-chain and schema foundations | tamper unit tests | Partial |
| Penetration test | external engagement | signed report | External, not complete |
| Restore drill | operator procedure | dated restore evidence | External, not complete |
| BingX account approval | exchange/operator evidence | credential verification record | External, not complete |
| Regulatory/compliance review | qualified review | signed approval | External, not complete |

`LIVE_READY` is emitted only when all gate checks pass. Current missing durable
providers deliberately keep their checks false, so this repository remains a
controlled implementation foundation rather than a production certification.
