# ADR-0012: Separate runtime principal authentication from management authentication

**Status:** Accepted

## Context

Runtime requests previously supplied Tenant and Agent IDs without proving the caller represented
either identity. A caller could claim an Agent with an ALLOW permission, and knowing an Invocation
UUID was sufficient to retrieve its persisted input/output. Reusing the management credential
would conflate platform administration with workload identity.

Agent IDs are generated during registration, so a static credential cannot be bound until the
Agent has been provisioned.

## Decision

Runtime routes use a dedicated bearer-authentication dependency and configuration-backed
principals. Each principal has a unique non-secret ID, exactly one Tenant UUID, exactly one Agent
UUID, and one secret credential. Duplicate IDs, credentials, and Tenant/Agent bindings are rejected;
a runtime credential may not equal the management credential.

POST Invocation accepts only Model ID and input. Tenant and Agent identity come exclusively from
the authenticated RuntimePrincipal. Existing ownership admission and exact default-deny policy
remain independent requirements.

Invocation persists the runtime principal ID, but never the credential. GET requires exact
principal ID, Tenant, and Agent correlation and returns the existing non-disclosing 404 otherwise.
Migration 0008 leaves the new column nullable for existing rows; legacy rows without authenticated
principal evidence are not retrievable through the Runtime API. No foreign key exists because
runtime principals are configuration-backed.

## Consequences

Callers cannot override Tenant or Agent identity in JSON, management/runtime credentials are
isolated, and Invocation reads are isolated by authenticated workload identity. Provisioning is
manual: register an Agent, add its generated IDs and credential to runtime configuration, then
restart the application.

Static bearer credentials remain replayable and have no issuance, rotation, revocation, or expiry.
Linear constant-time comparisons are acceptable for the intentionally small configured principal
set.

## Alternatives considered

Management-token reuse was rejected because operators are not workloads. Retaining caller identity
claims was rejected because redundant untrusted fields add mismatch paths. Caller-supplied Agent IDs
were rejected to preserve registry identity generation. A credential database, JWT, OIDC, and mTLS
were rejected until lifecycle and deployment requirements justify them.
