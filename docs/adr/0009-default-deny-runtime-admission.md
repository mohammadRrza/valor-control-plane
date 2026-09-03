# ADR-0009: Default-deny runtime Agent-to-Model admission

**Status:** Accepted

## Context

Tenant ownership prevents cross-tenant invocation but does not answer whether a particular Agent may use a particular Model. Continuing to allow every same-tenant combination would make absence of governance indistinguishable from approval.

## Decision

Runtime admission is default-deny. Provider execution requires one explicit `ALLOW` permission for the exact Tenant, Agent, and Model tuple. An explicit `DENY` or no matching permission prevents provider execution. Every evaluated attempt receives a persisted policy Decision and denied attempts are persisted as Invocations linked to that Decision.

## Consequences

New Agent/Model combinations cannot run until explicitly allowed. Audit records distinguish default denial (`permission_id` absent) from explicit denial. Policy decisions commit before provider I/O, so an allow decision remains durable even if the provider later fails. The current unauthenticated permission-management API is security-sensitive and must not be exposed to untrusted networks.

## Alternatives considered

Default allow was rejected because missing governance would authorize execution. A general policy engine, wildcard permissions, RBAC/ABAC, and a separate Agent-to-Model assignment model were rejected as premature. Encoding permission directly on Agent or Model was rejected because the relationship has its own identity and lifecycle.
