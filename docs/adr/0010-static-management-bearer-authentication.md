# ADR-0010: Static bearer authentication for the initial management plane

**Status:** Superseded by ADR-0019

## Context

Runtime admission is default-deny, but anonymous callers could change an Agent-to-Model
permission to `ALLOW`. Tenant, Agent, Model, and Policy APIs are control-plane operations and
must establish who is calling before richer authorization is introduced.

## Decision

All current management-plane routes require one environment-configured static bearer
credential. Possession authenticates a single stable, non-secret management principal ID. The
credential is represented as a secret setting, compared in constant time, and is never used as
an identity, persisted, logged, or returned. Missing configuration fails application startup.

Health routes remain public. Runtime routes do not accept the management credential as a runtime
identity and retain their existing authentication behavior. This prevents conflating a platform
operator with a future workload or runtime-client principal.

## Consequences

Anonymous callers can no longer create or inspect managed resources or grant runtime access.
Every management caller currently shares one credential and principal, so this establishes
authentication but not tenant-scoped authorization, individual accountability, rotation, or
revocation. TLS and secure secret injection are deployment responsibilities.

The intended evolution is static management bearer authentication, explicit authenticated
principals, tenant-aware authorization, then OIDC or enterprise identity integration. The
principal contract is deliberately independent of FastAPI and any identity provider.

## Alternatives considered

Continuing anonymous management was rejected because it defeats default-deny governance. Users,
passwords, sessions, API-key lifecycle infrastructure, and an OAuth/OIDC issuer were rejected as
premature identity-platform scope. Reusing this credential for runtime calls was rejected because
management operators and runtime workloads are distinct trust domains.
