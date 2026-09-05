# ADR-0017: Enforce Tenant Daily Estimated-Cost Budget from Invocation Snapshots

## Status

Accepted

## Decision

Before provider execution, enforce one static USD estimated-cost budget per Tenant over the UTC
calendar day. Policy admission runs first, followed by the existing Runtime Principal usage limit,
then this monetary check. Missing budget configuration or a failed cost-ledger read fails closed.

The consumption source is the exact sum of persisted Invocation `cost_total` snapshots in the
half-open UTC-day window. Current pricing is never used to reprice history. The preflight rule is:

```text
known attributed cost + per-invocation allowance <= daily budget
```

The allowance represents expected exposure for one request; it is not a provider cap. A rejected
attempt is persisted as `cost_limited` with the evaluated cost, allowance, limit, and window.

Configuration remains static because this slice does not require budget CRUD or a budget database
table. Tenant scope matches the ownership and reporting boundary, and USD matches existing cost
attribution.

## Consequences

- Sequential requests are deterministically stopped before provider execution at the configured
  boundary.
- Missing cost attribution is excluded rather than fabricated, so known cost can understate actual
  provider spend.
- One request may cost more than its allowance and overshoot the budget; actual attributed cost is
  still persisted without truncation.
- Concurrent requests can observe the same total and collectively overshoot. A reservation ledger,
  distributed locks, or transactions held across provider I/O are explicitly deferred.
- This is estimated-cost governance, not billing or an authoritative provider invoice limit.
