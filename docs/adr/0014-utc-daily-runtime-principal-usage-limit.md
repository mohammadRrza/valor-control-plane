# ADR-0014: Enforce Runtime Principal usage with a UTC daily pre-check

**Status:** Accepted

## Context

Phase 3.0 records provider usage only after execution. A pre-provider control cannot know actual
future usage, and checking only whether prior consumption is below a limit permits an arbitrarily
large next request. The first enforcement primitive must remain explicit and auditable without
introducing billing or a generalized quota platform.

## Decision

Every configured Runtime Principal has a required positive daily `usage_limit` and positive
`per_invocation_allowance`, with allowance no greater than the limit. After resource validation
and Agent-to-Model policy ALLOW, Runtime Gateway sums known persisted `total_units` for that
principal whose `started_at` is in `[00:00 UTC, next 00:00 UTC)`. Provider execution is permitted
only when `consumed + allowance <= limit`.

`total_units` is the sole dimension. Invocation records are the source of truth; there is no
mutable balance table. A blocked attempt is persisted as `limited` with the consumed, limit,
allowance, and UTC-window snapshot, then returned as HTTP 429. Usage-reader database failure is
fail-closed and never reaches the provider. Policy DENY remains a separate 403 decision and skips
the usage reader.

The allowance is an accounting guard, not a provider generation limit or reservation. Actual
provider usage is persisted without truncation even when it exceeds the allowance.

## Consequences

Sequential requests receive deterministic daily usage containment and auditable denial evidence.
Null provider usage and legacy rows do not contribute because no estimate is fabricated.

Concurrent requests can read the same prior total and both pass before either actual usage is
persisted. Strict concurrency-safe accounting would require a reservation ledger or another
coordination design; it is explicitly deferred. No database lock is held across provider I/O.

## Alternatives considered

Rolling, local-time, monthly, and configurable windows were rejected for this first deterministic
slice. Input/output dimensions, mutable counters, Redis, provider token caps, monetary pricing,
and generalized quota abstractions were rejected as broader scope.
