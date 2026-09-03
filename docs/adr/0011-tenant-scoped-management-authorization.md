# ADR-0011: Tenant-scoped management authorization

**Status:** Accepted

## Context

Static bearer authentication establishes one management principal, but possession of that global
credential previously implied authority over every Tenant. Authentication alone cannot prevent a
valid management caller from inspecting or mutating another Tenant's Agents, Models, or runtime
permissions.

Tenant creation presents a bootstrap constraint: its generated UUID cannot be configured as an
authorized scope before it exists.

## Decision

The management principal carries an immutable, finite set of configured Tenant UUIDs. Every
operation involving an existing Tenant authorizes the owning Tenant through one small,
framework-independent rule. Empty scope authorizes nothing; missing or malformed configuration
fails startup. There is no wildcard or implicit global access.

Cross-Tenant reads and mutations reuse the resource's existing 404 response so callers cannot
distinguish an inaccessible resource from an absent one. Agent, Model, and Permission retrieval
authorizes the ownership of the aggregate already returned by its application handler. Mutations
authorize the explicitly supplied Tenant before any business write.

Authenticated Tenant creation remains a narrow provisioning exception because no existing Tenant
can scope it. Creation does not grant access or mutate configuration. An operator must add the new
Tenant UUID to `VALOR_SECURITY__MANAGEMENT_TENANT_IDS` and restart the application before managing
or retrieving it.

Runtime callers remain a separate trust domain. Management Tenant scopes do not change runtime
admission, which remains exact Agent-to-Model default-deny.

## Consequences

A valid management credential no longer grants hidden global Tenant authority. Static
configuration is deliberately operationally awkward: scope changes require configuration rollout,
and one principal still represents every management caller. No authorization records or management
audit events exist yet.

The expected evolution is configured scopes, multiple authenticated principals, persisted Tenant
grants, then role semantics and enterprise identity only when justified.

## Alternatives considered

A wildcard/super-admin scope was rejected because absence of scope must never mean global access.
Automatic access to newly created Tenants was rejected because it would turn runtime configuration
into an implicit dynamic grant store. Caller-supplied Tenant IDs were rejected to preserve the
current aggregate creation contract. Persisted grants, memberships, and RBAC were rejected until
their lifecycle requirements are known.
