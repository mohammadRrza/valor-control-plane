# Architecture Decision Records

ADRs record decisions at the time they are made. Supersede rather than silently rewriting accepted decisions.

- [ADR-0001](0001-ddd-modular-monolith.md) — DDD-oriented modular monolith
- [ADR-0002](0002-fastapi-python.md) — FastAPI and Python
- [ADR-0003](0003-postgresql.md) — PostgreSQL
- [ADR-0004](0004-explicit-unit-of-work.md) — explicit Unit of Work
- [ADR-0005](0005-domain-events-outbox-later.md) — domain events and later outbox
- [ADR-0006](0006-selective-cqrs.md) — selective CQRS
- [ADR-0007](0007-avoid-global-event-sourcing.md) — avoid global event sourcing
- [ADR-0008](0008-infrastructure-extraction.md) — extraction criteria
- [ADR-0009](0009-default-deny-runtime-admission.md) — default-deny Agent-to-Model runtime admission
- [ADR-0010](0010-static-management-bearer-authentication.md) — interim static management bearer authentication
- [ADR-0011](0011-tenant-scoped-management-authorization.md) — fail-closed Tenant-scoped management authorization
- [ADR-0012](0012-separate-runtime-principal-authentication.md) — separate runtime workload authentication
- [ADR-0013](0013-persist-provider-neutral-invocation-usage.md) — persisted provider-neutral Invocation usage
- [ADR-0014](0014-utc-daily-runtime-principal-usage-limit.md) — UTC daily Runtime Principal usage pre-check
- [ADR-0015](0015-snapshot-configured-pricing-for-invocation-cost.md) — immutable configured pricing and estimated cost snapshot
- [ADR-0016](0016-aggregate-tenant-runtime-reporting.md) — bounded Tenant Runtime aggregation from Invocation evidence
- [ADR-0017](0017-enforce-tenant-daily-estimated-cost-budget.md) — fail-closed Tenant daily estimated-cost governance
- [ADR-0018](0018-atomic-management-governance-audit.md) — atomic fingerprint-only Management governance audit
- [ADR-0019](0019-persist-management-principals-and-credentials.md) — persisted Management principals and independent bearer credential rotation
- [ADR-0020](0020-bound-management-credential-use-evidence.md) — bounded Management credential-use authentication evidence
