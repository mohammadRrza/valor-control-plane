# ADR-0015: Snapshot configured pricing for Invocation cost attribution

**Status:** Accepted

## Context

Persisted provider usage supports attribution, but historical monetary estimates cannot be
reconstructed safely from whatever pricing happens to be configured later. Provider invoices may
also differ through discounts, credits, tiers, taxes, or negotiated terms that VALOR does not know.

## Decision

Resolve static validated pricing by exact `(provider, provider_model_reference)` after successful
provider execution. Each entry has separate non-negative input/output USD rates, a positive basis,
and a unique stable pricing version. When both input/output usage and pricing exist, calculate with
exact `Decimal` arithmetic, quantize each component to `0.000000000001 USD` using
`ROUND_HALF_EVEN`, and persist the complete pricing and cost snapshot on Invocation.

Persist component and total cost as `NUMERIC(30,12)`, rates as `NUMERIC(18,12)`, and require the
snapshot to be all present or all null. The total is the sum of the independently quantized input
and output components. Invocation responses expose costs as decimal strings plus USD and pricing
version; basis and rates remain persisted audit evidence.

Missing pricing or incomplete usage leaves attribution unavailable without failing provider
success. Failed, policy-denied, and usage-limited Invocations have no snapshot. Existing rows stay
null and are never backfilled from current configuration.

## Consequences

Historical estimates remain stable when configuration changes and are explainable from their own
snapshot. Values are configured estimates, not provider invoice truth. There is no pricing table,
sync, FX conversion, aggregation API, billing workflow, or monetary enforcement.

## Alternatives considered

Pricing by display name or provider alone was rejected as ambiguous. Binary floating point was
rejected for money. Dynamic GET-time recomputation was rejected because it rewrites history.
Provider pricing APIs, web scraping, and a pricing database were rejected as broader lifecycle
scope.
