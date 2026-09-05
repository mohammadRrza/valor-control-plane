# ADR-0018: Atomic Management governance audit evidence

## Status

Accepted.

## Decision

Every successful Agent-to-Model permission PUT appends an immutable `ManagementAuditRecord` in the
same SQLAlchemy Unit of Work and PostgreSQL transaction as the permission upsert. The record stores
the authenticated principal ID, Tenant and resource identities, an explicit action/outcome, UTC
time, and deterministic SHA-256 fingerprints of non-secret canonical permission state. A creation
has no before fingerprint; an idempotent PUT is still evidence and has equal fingerprints.

The dedicated `management_audit` context owns the evidence model, append port, persistence table,
bounded reader, and HTTP read boundary. Policy's coordinated UoW exposes the audit append port so
the two repositories share one transaction; neither repository commits.

Phase 4.0 does not durably record failed attempts. Validation and authorization failures are
security events outside this slice, while writing failures roll back both mutation and evidence.
Database-level WORM controls, export, retention, and external shipping are deferred.

Tenant cost-budget changes are not audited because the current budget is static process
configuration and VALOR exposes no mutation operation. Adding persistent budget CRUD would change
Phase 3.5's runtime source of truth and exceeds this slice's narrow scope.

## Consequences

No successful audited permission mutation can commit without its audit row. This deliberately
couples cross-context infrastructure to one local database transaction while keeping the audit
domain free of Policy types. Database superusers can still mutate evidence. The read API is
Tenant-scoped, requires an aware half-open range of at most 31 days, returns at most 100 newest
records, and has no continuation mechanism yet.
