# Initial threat model

**Status:** Initial, living document
**Scope:** Implemented VALOR management plane, Runtime Gateway, Policy & Risk, PostgreSQL,
and OpenAI provider boundary through Phase 2.3

This document describes current trust boundaries and risks. Planned controls are not described as
implemented. Revisit it whenever identity, data retention, provider routing, or deployment
boundaries materially change.

## System and assets

```mermaid
flowchart LR
  MC[Management client] -->|Management bearer token| MP[Management API]
  RC[Authenticated runtime principal] -->|Distinct runtime bearer| RG[Runtime Gateway]
  MP --> D[(PostgreSQL)]
  RG --> PR[Policy admission]
  PR --> D
  RG -->|Server-side credential| OA[OpenAI]
  RG --> D
```

The primary assets are:

- governance configuration: Tenants, Agents, Models, and Agent-to-Model permissions;
- provider credentials, which grant external access and can create financial cost;
- Invocation input/output, identity references, status, and timestamps;
- PolicyDecision evidence connecting an attempted Invocation to ALLOW or DENY;
- management principal identity, bearer credential, and configured Tenant scopes.

Invocation input and output can contain customer data, personal information, confidential data,
regulated data, or credentials accidentally placed in prompts. They are high-value assets even
though the current model treats them as plain text.

## Security assumptions

- Deployment provides TLS and protects traffic before it reaches FastAPI.
- Environment variables and database credentials are injected through a trusted deployment path.
- PostgreSQL and its administrative access are not exposed to untrusted clients.
- Host, container runtime, dependency, and CI compromise are outside the application's current
  controls but can invalidate every trust boundary below.
- Static runtime credentials require TLS and secure injection; they have no rotation or revocation.

## Trust boundaries

### Management client to management API

Implemented controls:

- constant-time validation of a static management bearer credential;
- one stable, non-secret management principal identity;
- explicit finite Tenant UUID scopes with empty scope failing closed;
- non-disclosing 404 responses for cross-Tenant resources;
- exact Tenant ownership enforcement for Agent, Model, and Policy management.

Tenant creation is an authenticated provisioning exception. It does not automatically grant scope.

Residual threats include bearer theft and replay, one shared principal, lack of credential rotation,
lack of individual accountability, and lack of a policy-change audit trail.

### Runtime client to Runtime Gateway

Runtime routes now require a credential from a separate configuration-backed trust domain. Each
credential resolves to exactly one Tenant and Agent; POST accepts no caller-controlled Tenant or
Agent claims. GET requires exact runtime principal, Tenant, and Agent correlation. This mitigates
the original Agent-spoofing and known-Invocation-ID disclosure paths.

Residual risks remain significant: credentials are static and replayable, have no expiry,
rotation, dynamic revocation, issuance workflow, rate limit, or workload-attestation mechanism.

### Runtime Gateway to provider

Implemented controls:

- provider credentials remain server-side environment secrets;
- the OpenAI SDK is isolated in infrastructure;
- provider calls occur only after ownership admission and an explicit policy ALLOW;
- provider errors are sanitized;
- provider timeout is bounded;
- the OpenAI request sets `store=false`.

Residual threats include credential theft, provider outage, malicious output, latency, unbounded
usage, and cost abuse. VALOR persists its provider-neutral output text, though it does not persist a
raw SDK response object.

### Application to PostgreSQL

PostgreSQL constraints protect ownership foreign keys, unique identities, permission tuples, and
Invocation/Decision relationships. Explicit Units of Work own commit and rollback.

Residual threats include application defects, compromised database credentials, direct database
mutation, audit-record tampering, backup disclosure, and plaintext application-level storage of
Invocation input/output.

### Policy configuration to runtime enforcement

Management authentication and Tenant authorization prevent anonymous or cross-Tenant policy
mutation. Runtime admission remains default-deny: absence of permission and explicit DENY prevent
provider execution.

Residual threats include a stolen authorized credential, repudiation because permission changes
have no durable management actor record, and lack of permission history or approval workflow.

## STRIDE-oriented threat register

| Category | Threat | Current control | Residual severity | Next control |
|---|---|---|---|---|
| Spoofing | Caller claims another Agent/Tenant at runtime | Identity derives from a credential bound to one Tenant/Agent | Mitigated; credential theft remains High | Rotation/revocation and workload identity |
| Spoofing | Management principal impersonation | Static bearer authentication, constant-time comparison | High | Rotation and multiple federated principals |
| Tampering | Unauthorized policy mutation | Management auth, exact Tenant scope, DB constraints | Medium | Management mutation audit/history |
| Tampering | Direct Invocation/Decision changes | DB access boundary and constraints | High if DB compromised | Restricted DB roles and tamper-evident evidence |
| Repudiation | Operator denies changing a permission | Stable principal exists only in request boundary | Medium | Persist management action evidence |
| Information disclosure | Cross-principal Runtime GET reveals prompt/response | Exact principal/Tenant/Agent correlation and non-disclosing 404 | Mitigated; stored-data risk remains High/Medium | Retention, redaction, encryption policy |
| Information disclosure | Database/backup reveals prompt/response | Infrastructure access boundary | High/Medium | Retention, redaction, classification, encryption policy |
| Denial of service | Runtime exhausts connections/provider capacity | Provider timeout | High/Medium | Identity-aware limits and concurrency controls |
| Cost abuse | Stolen runtime credential incurs provider spend | Runtime authentication plus default-deny model policy | High/Medium | Rotation, rate limits, quotas/budgets |
| Elevation of privilege | Caller claims a more privileged Agent | Request identity removed; credential binds exact Tenant/Agent | Mitigated; stolen credential remains High | Managed workload identity lifecycle |

## Highest-priority attack scenario

Before Phase 2.4, if Agent A could use Model X while Agent B could not, an unauthenticated caller
could submit Agent A's ID. VALOR validated that Agent A belonged to the Tenant and had ALLOW, but
could not establish that the caller was Agent A. This was an identity-spoofing path through an
otherwise correct authorization decision that could cause data disclosure and direct provider cost.

Phase 2.4 mitigates this scenario with a distinct Runtime Principal, removal of caller-controlled
Tenant/Agent fields, independent policy enforcement, and principal-isolated reads. Static
credential theft/replay now replaces unauthenticated identity claims as the principal residual
runtime identity risk.

## Current posture

Implemented strengths:

- management authentication and explicit Tenant-scoped authorization;
- separate Runtime authentication bound to an exact Tenant and Agent;
- non-disclosing Runtime read isolation by principal, Tenant, and Agent;
- Tenant ownership and non-disclosing cross-Tenant management failures;
- default-deny Agent-to-Model runtime admission;
- persisted PolicyDecision and Invocation records;
- provider-secret isolation and sanitized upstream failures;
- PostgreSQL integrity constraints and explicit transactions.

Material gaps:

1. Static runtime credential lifecycle, theft, replay, rotation, and revocation — High.
2. Sensitive Invocation data retention/redaction policy — High/Medium.
3. Identity-aware rate, concurrency, and budget controls — Medium.
4. Individual management accountability and policy-change audit — Medium.

## Recommended sequence

```text
Managed runtime credential issuance/rotation/revocation
  → Usage metadata and observability
  → Per-principal rate/budget controls
  → Sensitive-data retention and redaction
  → Management mutation audit
  → Enterprise identity/OIDC when justified
```

The next slice should not introduce an OAuth server, OIDC federation, RBAC, OPA, Vault, mTLS,
rate-limiting platform, WAF, SIEM, or generalized encryption framework. Those controls require
separate evidence and design decisions.
