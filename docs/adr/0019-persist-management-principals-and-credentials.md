# ADR-0019: Persist Management Principals and rotate independent bearer credentials

## Status

Accepted.

## Decision

Ordinary Management authentication uses persisted `ManagementPrincipal` identities and separate
`ManagementCredential` records. A Principal has a stable UUID, display label, exact persisted
Tenant scopes, terminal disabled state, and one explicit global `can_manage_principals`
capability. Empty scope is allowed but grants no Tenant access. This capability is deliberately not
a generic role or policy system.

A credential has its own UUID, optional label and expiry, and permanent revocation timestamp.
Issuance generates at least 256 random bits and returns a parseable bearer token exactly once.
Only an HMAC-SHA256 verifier keyed by a deployment-provided pepper is persisted. Authentication
looks up the public credential UUID, checks credential and Principal lifecycle state, then compares
the verifier in constant time. Rotation is overlapping issuance followed by old-credential
revocation; Principal identity and audit correlation remain stable.

The first manager and credential are created atomically through a one-time bootstrap endpoint. A
PostgreSQL transaction advisory lock serializes competing attempts. Once any Principal exists,
bootstrap remains unavailable and never reactivates. The first Principal is a principal manager.
Mutations protect the last recoverable active manager with a usable credential.

The former static Management token is removed as an ordinary authentication authority. Historical
audit actor strings remain unchanged; new records use persisted Principal UUID strings. Runtime
Principal authentication remains separate. OIDC, SSO, MFA, passwords, generic RBAC, automatic
rotation, and break-glass recovery are deferred until concrete integration requirements exist.

Principal and credential lifecycle audit records are control-plane-global, so their audit
`tenant_id` is null; their canonical Principal fingerprint contains the sorted exact Tenant scope.
Tenant-owned permission audit records remain non-null and Tenant-queryable. Bootstrap emits no
audit row because fabricating a persisted actor before the first Principal exists would be false.

## Consequences

Operators and automation no longer share one required credential, compromise can be contained by
revocation, and rotation preserves actor identity. Bearer secrets remain replayable if stolen. The
pepper and database must be backed up and protected; pepper loss invalidates all credentials.
Downgrading migration 0015 deletes persisted access configuration and is operationally destructive.
