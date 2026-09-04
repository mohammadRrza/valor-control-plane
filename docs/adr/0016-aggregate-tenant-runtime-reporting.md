# ADR-0016: Aggregate Tenant Runtime Reporting from Invocation Evidence

## Status

Accepted

## Decision

Provide one read-only Management endpoint that aggregates persisted Invocation evidence for one
authorized Tenant over an explicit UTC `[start, end)` interval of at most 31 days. Invocation rows
remain the source of truth; PostgreSQL performs the aggregation and a `(tenant_id, started_at)`
index supports its mandatory filter.

Reports sum persisted Invocation-level cost snapshots without resolving current pricing or
repricing history. They expose completeness counts alongside known usage and cost totals. The
response contains aggregates only, with no prompts, outputs, Invocation IDs, or asset lookups.

## Consequences

- Tenant scope is enforced with existing non-disclosing Management authorization semantics.
- Operators can inspect usage and cost posture without reading sensitive Invocation content.
- Explicit bounded intervals prevent accidental all-history scans.
- Totals can combine pricing versions and remain estimates rather than invoice truth.
- No reporting table, analytics store, dashboard, export, billing, or budget mechanism is added.
