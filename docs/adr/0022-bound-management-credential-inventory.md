# ADR 0022: Bound Management credential inventory

## Status

Accepted.

## Decision

Expose a principal-manager-only read model for credentials belonging to exactly one persisted
Management Principal. Return only credential and Principal UUIDs, label, lifecycle timestamps,
derived usability, and a small state enum. Order deterministically by creation time and UUID,
accept a limit from 1 to 100, fetch one extra row, and report truncation without cursor pagination.

State precedence is `principal_disabled`, `revoked`, `expired`, then `active`; `usable` is the
authoritative operational fact and is computed with the injected clock. Previously issued bearer
secrets and stored verifiers have no retrieval path.

The existing `principal_id` index supports the query, so no schema migration is added. Inventory
reads do not append governance audit records and do not include authentication-evidence facts.

## Consequences

Operators can complete safe manual issue–deploy–verify–revoke rotation and retain historical
revocation/expiry metadata. They cannot recover secrets, obtain last-use or attempt counts, browse
all credentials, or automate rotation through this endpoint.
