# ADR-0021: Expose a bounded Management authentication evidence query

## Status

Accepted.

## Decision

Principal managers may read authentication evidence through one metadata-only endpoint. Every query
must select exactly one credential UUID or Principal UUID, provide a timezone-aware half-open
`[start, end)` range no longer than 31 days, and request at most 100 rows. The default limit is 50.
Results are ordered by first observation descending with credential UUID and outcome tie-breakers.

Unknown filters return an empty list. Callers without `can_manage_principals` receive the same
non-disclosing Management identity 404 used by lifecycle operations. The response exposes only
credential UUID, Principal UUID, outcome, UTC-hour bucket, and first-observed timestamp. It does not
expose request context, network metadata, secrets, verifiers, headers, or exact attempt counts.

Two focused indexes support credential/time and Principal/time access. No broad unfiltered query,
pagination, aggregation, export, dashboard, alerting, SIEM integration, or generic security-event
query language is introduced.

## Consequences

Authorized operators can use Phase 4.2 evidence without direct database access. The fixed limit and
mandatory identity filter bound response size and query scope. There is no complete-history paging,
cross-Principal search, outcome filtering, Tenant delegation, or read-access audit in this slice.
