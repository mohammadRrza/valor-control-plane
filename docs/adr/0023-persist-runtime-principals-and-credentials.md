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

Phase 5.0A deliberately provisioned before cutover. Phase 5.0B persists an all-or-none daily usage
limit and per-invocation allowance on each Runtime Principal. New Principals require both values;
legacy rows may initialize them exactly once. Readiness means active, configured, and backed by at
least one non-revoked, unexpired credential, but does not imply live acceptance. Persisted Runtime
credentials are not accepted by Runtime Gateway, and static configured Runtime Principals remain
the sole authentication and usage-limit authority. Phase 5.0C will replace both authorities in one
explicit change. OIDC, mTLS, federation, MFA, dashboards, alerting, and generic IAM are deferred.

Phase 5.0B.1 addresses a cutover blocker: legacy static Principal IDs are arbitrary strings while
persisted IDs are UUIDs. Each persisted Principal may therefore acquire one immutable historical
legacy ID, and each legacy ID may be claimed once. The operator explicitly selects both identities;
Tenant/Agent matching never chooses a Principal. A read-only preflight verifies current static
configuration, bindings, historical and canonical Invocation consistency, equal usage limits, and
credential readiness. Binding repeats those checks under locks and appends an atomic audit record.

Historical Invocation IDs are not rewritten. This preserves evidence, avoids racing live static
traffic, and requires no traffic freeze. Phase 5.0C will use the bounded set containing the
canonical UUID string and optional single legacy ID for usage aggregation and historical read
isolation. The alias is identity metadata only and never authenticates a bearer.

## Consequences

Operators gain durable, auditable rotation and disablement primitives without dual authentication
authority. Through Phase 5.0B, those primitives do not reduce live static Runtime bearer replay
risk. Migration 0019 preserves 5.0A rows without inventing limits; downgrade to 0018 discards only
usage-limit preparation and its initialization audits.
Migration 0020 adds nullable continuity metadata without guessing mappings. Downgrading to 0019
loses continuity preparation and its binding audits but does not rewrite Invocation evidence.
Downgrading below migration 0018 destroys the inactive provisioning state but does not affect
current static Runtime authentication.
