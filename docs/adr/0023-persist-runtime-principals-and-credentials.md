# ADR 0023: Persist Runtime Principals and independent Runtime credentials

## Status

Accepted.

## Decision

Introduce a dedicated `runtime_identity` bounded context. A durable Runtime Principal has a stable
UUID and an immutable exact Tenant plus Agent binding. Independent credentials have UUIDs,
optional bounded labels and expiry, permanent revocation, and a peppered HMAC-SHA256 secret
verifier. The Runtime-specific pepper is distinct from Management secrets, is never persisted, and
the high-entropy `valor_runtime_...` bearer is returned only at issuance.

Only active Management Principals with `can_manage_principals` may create, inspect, issue, revoke,
or terminally disable these identities. Creation includes an initial credential. Each successful
mutation and its secret-free canonical fingerprint are appended to `management_audit` in the same
PostgreSQL transaction. Revoking the last credential is legal; there is no Runtime bootstrap or
last-credential protection.

Phase 5.0A deliberately provisions before cutover. Persisted Runtime credentials are not accepted
by Runtime Gateway, and static configured Runtime Principals remain the sole invocation authority.
Phase 5.0B will replace that authority in one explicit change and migrate usage-limit truth at the
same boundary. OIDC, mTLS, federation, MFA, dashboards, alerting, and generic IAM are deferred.

## Consequences

Operators gain durable, auditable rotation and disablement primitives without dual authentication
authority. Until Phase 5.0B, those primitives do not reduce live static Runtime bearer replay risk.
Downgrading below migration 0018 destroys the inactive provisioning state but does not affect
current static Runtime authentication.
