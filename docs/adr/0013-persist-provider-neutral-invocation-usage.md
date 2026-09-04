# ADR-0013: Persist provider-neutral Invocation usage

**Status:** Accepted

## Context

Invocation status and timestamps establish that provider execution occurred, but do not preserve
the usage facts or provider-side identity needed for later reliability and cost attribution. Logs
alone are transient and cannot serve as governed Invocation evidence. OpenAI exposes a response ID
and optional input, output, and total token counts, while future providers may use different names
for equivalent consumption units.

## Decision

Store normalized optional `input_units`, `output_units`, and `total_units`, an optional safe
`provider_response_id`, and integer `duration_ms` directly on Invocation. Duration covers the
application lifecycle from handler entry, before input/resource and policy evaluation, through
final success, failure, or denial and is derived once from existing timestamps.

The provider port returns only provider-neutral `InvocationUsage` and response correlation. The
OpenAI adapter translates its typed `Response.usage` token fields and `Response.id`; SDK objects do
not leave infrastructure. Invalid optional provider usage or response identity is discarded rather
than converting an otherwise successful generation into failure. No raw response, headers, error
body, credentials, or arbitrary metadata are persisted.

Migration 0009 uses nullable columns so older Invocation records remain readable and providers may
honestly omit telemetry. Database checks enforce non-negative values. Denied and failed outcomes
record duration but do not fabricate provider usage or response identity.

## Consequences

Invocation records provide durable facts for future reliability and cost analysis without a
telemetry backend. Provider units intentionally do not assert that every future provider bills in
tokens, and total units are not assumed to equal input plus output.

Usage persistence does not calculate prices, enforce budgets or quotas, export metrics, introduce
distributed tracing, or solve sensitive input/output retention. Those require separate use cases
and decisions.

## Alternatives considered

A separate telemetry table was rejected because this slice has one small one-to-one fact set.
OpenAI-specific token objects were rejected because they would leak adapter semantics into the
core. Logs-only telemetry was rejected because it is not durable governed evidence. A generic
observability framework and pricing model were rejected as unjustified scope.
