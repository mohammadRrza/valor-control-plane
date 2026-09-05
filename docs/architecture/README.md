# Architecture

## System context

```mermaid
flowchart LR
  A[Applications / AI Agents] --> V[VALOR Control Plane]
  V --> L[LLM Providers]
  V --> M[MCP Servers]
  V --> T[Enterprise Tools]
  V --> D[Databases / APIs]
  O[Platform Operators] --> V
```

VALOR is the governance and evidence boundary between callers and AI/tool dependencies. Phase 0 established the operational shell; Phase 1 added Tenant, Agent, and governed Model reference slices. Phase 2 has one synchronous OpenAI path governed by explicit default-deny Agent-to-Model permission decisions, with interim bearer authentication around management APIs. Phase 3 begins with persisted provider-neutral Invocation usage facts; VALOR is neither a complete gateway nor a telemetry, policy, or identity platform.

## Current container and component view

```mermaid
flowchart TB
  C[HTTP Client] --> API[FastAPI presentation]
  API --> APP[Application ports]
  BOOT[Composition root] --> API
  BOOT --> INFRA[SQLAlchemy infrastructure]
  INFRA -. implements .-> APP
  INFRA --> PG[(PostgreSQL)]
  APP --> TENANT[Identity & Tenancy domain]
  INFRA -. implements tenant ports .-> TENANT
  APP --> ASSET[AI Asset Registry domain]
  INFRA -. implements asset ports .-> ASSET
  APP --> RUNTIME[Runtime Gateway domain]
  INFRA -. implements runtime ports .-> RUNTIME
  INFRA --> OPENAI[OpenAI Responses API]
  APP --> POLICY[Policy & Risk domain]
  INFRA -. implements policy ports .-> POLICY
  OP[Management operator] -->|Bearer credential| SEC[Management authentication]
  SEC --> API
```

The application is one deployable process. Operational routes are outside domain APIs. PostgreSQL is the only runtime dependency. The domain remains synchronous; async appears at I/O boundaries.

## Bounded-context map

| Context | Responsibility | Principal relationships |
|---|---|---|
| Identity & Tenancy | principals, tenant isolation, ownership | upstream identity source for every context |
| AI Asset Registry | agents, models, prompts, tools and versions | assets referenced by gateway, policy, evaluation |
| Runtime Gateway | invocation and provider/tool routing | emits facts to observability, policy and FinOps |
| Policy & Risk | authorization and risk decisions | evaluates runtime intent and asset metadata |
| Evaluation | offline/online quality evidence | gates asset and routing changes |
| Observability | traces, metrics and operational signals | consumes runtime facts; avoids owning business truth |
| FinOps | usage attribution, cost and budgets | consumes invocation usage per tenant/asset |
| Incident Management | detection and response lifecycle | consumes violations, SLOs and evaluation failures |
| Compliance & Audit | immutable decision evidence | consumes explicit integration events/contracts |

These are domain boundaries, not services. Identity & Tenancy supports Tenant creation/retrieval; AI Asset Registry supports Agent and Model registration/retrieval; Runtime Gateway supports one synchronous OpenAI Invocation; Policy & Risk supports one exact Agent-to-Model permission and decision history. Each context owns its architectural layers. Cross-context access uses explicit contracts rather than imports into another context's internals.

### Tenant slice decisions

Tenant identity is an application-generated UUID and does not depend on persistence. A tenant name is trimmed, internal whitespace is collapsed, and the canonical value is limited to 100 characters. Names are globally unique for this slice under a case-folded canonical comparison; PostgreSQL enforces the normalized key so concurrent requests cannot bypass uniqueness. This global rule can be revisited only if a future, explicit tenancy hierarchy changes the domain meaning.

Tenant management is authenticated and Tenant-scoped. Runtime identity is separately authenticated
through configuration-backed workload principals; neither boundary is production-complete IAM.

### Agent registry and tenant boundary

```mermaid
flowchart LR
  T[Identity & Tenancy] -->|tenant identity / existence boundary| A[AI Asset Registry]
  A --> I[Governed Agent Identity]
  I -. future reference only .-> R[Runtime invocations]
  I -. future reference only .-> P[Policies / evaluations / telemetry]
```

An AI Asset Registry Agent is a governed workload identity known to VALOR. It contains no executable agent code, model configuration, prompts, tools, credentials, or runtime behavior. A configured Runtime Principal binds one credential identity to its Tenant and Agent IDs; the registry still does not execute Agents or own credentials.

AI Asset Registry represents ownership with its local `OwningTenantId` value object. Its application layer asks only `TenantExistencePort.exists()`. The PostgreSQL adapter reads the published persistence identity `tenants.id` without importing the Tenant aggregate, repository, or ORM model. Registration checks existence for a clear error before opening the Agent write Unit of Work. The `agents.tenant_id` foreign key remains authoritative if state changes between the check and flush; that violation maps to the same `OwningTenantNotFound` application failure.

Agent names use the same intentionally small canonicalization policy independently: trim/collapse whitespace, a 100-character canonical limit, and `casefold()` for comparison. The database composite constraint makes normalized names unique within an owning tenant, while allowing the same name in different tenants.

### Model registry decisions

A governed Model is a tenant-owned VALOR identity referencing an external provider model. It records `ModelId`, local ownership, a governance name, an explicit provider value, the opaque provider model reference, and registration time. It is not a provider client or runtime configuration: no credentials are stored, no provider connection is attempted, and registration does not prove the provider-side reference exists. Agents and Models are intentionally not linked in this slice.

Model names are trimmed, internal whitespace is collapsed, and the canonical value is limited to 100 characters. PostgreSQL enforces case-folded normalized-name uniqueness within each tenant. The same provider and provider-model reference may appear in multiple governed Model records because the VALOR name, rather than an external identifier, defines this slice's governance identity.

`Provider` is a Python string enum stored in a 50-character varchar. This gives API callers an explicit supported vocabulary while avoiding a PostgreSQL enum migration whenever that vocabulary grows. Provider model references are treated as opaque trimmed strings of at most 255 characters; provider-specific syntax and live validation are deferred until an actual provider-integration use case exists.

Model registration reuses the AI Asset Registry's `TenantExistencePort` and local `OwningTenantId`. A pre-check produces a useful error, while the `models.tenant_id` foreign key remains authoritative under races. Model persistence has its own repository and Unit of Work surface; no generic AI-asset repository or service hierarchy was introduced.

### First Runtime Gateway slice

```mermaid
flowchart LR
  C[Client] --> RG[Runtime Gateway]
  RG --> A[Admission projections]
  A --> PG[(Shared PostgreSQL)]
  RG --> O[OpenAI Responses adapter]
  O --> OA[OpenAI Responses API]
  RG --> I[(Final Invocation outcome)]
```

An Invocation is a VALOR-owned UUID plus Tenant, Agent, and Model IDs, final `succeeded`, `failed`, or `denied` status, text input, optional successful output, timezone-aware start/completion timestamps, integer lifecycle duration, optional provider-neutral usage units, and optional safe provider response correlation. Provider response identity is not the Invocation identity. Invocation has no monetary cost, retry, trace/span, tool, or evaluation fields.

Runtime admission uses local identity/projection types and three narrow application ports. A PostgreSQL adapter queries only the published fields required from `tenants`, `agents`, and `models`; Runtime Gateway domain/application code imports no owning-context aggregates, repositories, ORM rows, or infrastructure. This is deliberate shared-schema coupling in the modular monolith. PostgreSQL foreign keys from `invocations` to all three records provide final referential protection without ORM relationships.

The POST request supplies only `ModelId` and input. Tenant and Agent identities come exclusively from the authenticated Runtime Principal, eliminating caller-controlled identity claims. Any Model belonging to that Tenant reaches policy evaluation; missing resources and cross-Tenant ownership mismatches use the same non-disclosing response. Only the `openai` provider is executable.

The OpenAI infrastructure adapter uses the current Responses API for one plain string input and reads provider-neutral `output_text`. It requests `store=false`, uses an environment-supplied credential and bounded timeout, and translates SDK/upstream failures without exposing raw details. SDK types do not cross the infrastructure boundary.

Admission reads occur before policy evaluation. After resource ownership succeeds, Runtime Gateway creates InvocationId and asks its narrow policy-decision port. Policy & Risk atomically resolves the current permission, persists the decision, and commits before any provider call. Default or explicit DENY then creates a linked denied Invocation and returns 403 without contacting the provider. Explicit ALLOW permits provider execution, after which a short Invocation Unit of Work persists success or failure. No database transaction spans provider I/O and no distributed transaction is attempted.

Invocation persistence records the non-secret runtime principal ID in addition to Tenant and Agent,
but never stores the credential. GET requires all three identities to match and returns 404 for
cross-principal access. Legacy rows without authenticated principal evidence are not returned.
Input and successful output remain persisted but never logged; retention, redaction,
classification, encryption policy, credential lifecycle, and rate controls remain technical debt.

`duration_ms` is derived once from `completed_at - started_at` and covers Runtime application
processing from handler entry, before input/resource and policy evaluation, through final denial
or provider completion/failure. The provider port carries only `InvocationUsage` and
an optional provider response ID. OpenAI infrastructure maps typed input/output/total token counts
to provider-neutral units and maps the response ID; malformed optional metadata becomes
unavailable without failing a successful response. Denied and failed Invocations record duration
but no fabricated usage or provider response ID. Nullable telemetry keeps legacy rows readable.
These persisted facts support later reliability and cost attribution, but there is no aggregation,
exporter, tracing backend, dashboard, alerting, pricing, budget, quota, or rate enforcement.

### Runtime Principal daily usage limit

Every configured Runtime Principal carries a positive UTC-daily `usage_limit` and positive
`per_invocation_allowance`. After resource validation and policy ALLOW, a narrow Runtime-owned
reader executes one PostgreSQL aggregate over that principal's known `total_units`, using
`started_at` in the half-open UTC calendar-day window. Provider execution requires `consumed +
allowance <= limit`. Policy DENY remains independent and runs first.

Limited attempts have explicit `limited` status, no provider telemetry, and a persisted snapshot of
consumption, limit, allowance, and window. They return 429 and remain retrievable only by the same
Runtime Principal. Invocation rows remain the sole usage ledger; no mutable counter exists. A
database read failure fails closed. The aggregate read does not hold a transaction across provider
I/O.

This is sequential-request containment, not strict concurrent quota accounting. Concurrent calls
may observe the same total and both proceed. Unknown provider usage cannot be counted, and actual
usage may exceed the configured allowance because it is not a provider generation cap.

### Invocation cost attribution

After provider success, Runtime Gateway resolves optional static pricing by exact provider and
provider-model reference. Complete input/output usage plus matching pricing produces an estimated
USD cost using exact Decimal arithmetic. The Invocation stores component costs, total, currency,
pricing version, basis, and input/output rates as an immutable snapshot. GET reads this snapshot;
it never consults current pricing, so configuration changes do not rewrite history.

Missing pricing or usage leaves cost null, as do failed, denied, and limited outcomes. API cost
values are decimal strings. Configured estimates are not provider invoice truth: there is no
pricing database or synchronization, invoice reconciliation, FX, billing, aggregation, monetary
budget, or cost-based blocking.

### Tenant Runtime reporting

An authenticated Management Principal can request one aggregate report for an authorized,
existing Tenant over a required UTC-aware `[start, end)` range of at most 31 days. A narrow
application read model calls a PostgreSQL adapter that aggregates by `tenant_id` and `started_at`;
it never loads Invocation rows into application memory and never uses the write Unit of Work.

Status counts cover succeeded, failed, denied, and limited outcomes. Usage totals include only
complete persisted usage tuples, with provider-executed, attributed, and unavailable counts.
Estimated USD cost sums persisted snapshots and exposes attributed/unavailable success counts;
different historical pricing versions may therefore contribute to one total.

The same endpoint includes fixed Top 10 Agent and Model breakdowns. PostgreSQL groups directly on
Invocation `agent_id` and `model_id`, ranks by persisted estimated cost descending, and uses the ID
ascending as the deterministic tie-break. Each row includes invocation count, known total units,
and usage/cost completeness. Eleven rows are fetched to determine accurate truncation flags, then
only ten are exposed. No asset lookup or N+1 query is performed. The response omits prompts,
outputs, Invocation IDs, names, and provider metadata. Configurable rankings, reporting tables,
repricing, billing, dashboards, exports, and an analytics store are intentionally absent.

### Default-deny Agent-to-Model admission

Policy & Risk owns one `AgentModelPermission` per Tenant/Agent/Model tuple. PUT atomically creates or replaces the current `ALLOW`/`DENY` effect while preserving PermissionId and creation time. There are no conditions, wildcards, inheritance, rule precedence, versions, assignments, RBAC/ABAC, or external policy engine.

Each evaluated attempt creates a PolicyDecision with DecisionId, InvocationId, exact resource IDs, effect, timestamp, and optional PermissionId. A null PermissionId with DENY means default deny; a present PermissionId identifies explicit allow or deny. `invocations.policy_decision_id` links the runtime result back to that fact. The reverse Decision `invocation_id` is a unique indexed correlation value rather than a foreign key because the decision must commit before the provider call and before the final Invocation row exists.

The permission-management application independently validates Tenant existence and Agent/Model ownership using Policy-local ports/projections. Its shared-database adapter imports no owning-context aggregate or ORM row, and foreign keys remain authoritative against races. Runtime Gateway imports no Policy & Risk internals; a Policy infrastructure adapter implements the Runtime-owned decision port at composition time.

Default deny materially improves runtime safety. Policy management requires the management credential and exact Tenant scope. Runtime execution separately requires a credential bound to the Tenant and Agent before policy evaluation. See ADR-0009 through ADR-0012.

### Management authentication boundary

Tenant, Agent, Model, and Policy routes are management-plane APIs and share one FastAPI authentication dependency. It validates an environment-supplied bearer credential in constant time and produces a framework-independent `AuthenticatedPrincipal` containing the stable configured principal ID, `management` kind, and a finite immutable set of manageable Tenant UUIDs. Missing or invalid credentials receive the same sanitized 401 Problem Details response and `WWW-Authenticate: Bearer`.

The credential is a `SecretStr`, is unwrapped only during validation, and is never an audit identity, persistence value, response field, or logging field. Authentication proves possession; a separate framework-independent rule authorizes exact Tenant UUID membership. Empty scope grants nothing, malformed or missing scope fails startup, and no wildcard/global authority exists.

Tenant GET authorizes its path identity before loading. Agent, Model, and Permission creation/mutation authorizes the supplied Tenant before business work; retrieval authorizes the aggregate's owning Tenant before presentation. Denials reuse each resource's existing 404 response, preventing cross-Tenant enumeration. Tenant creation alone remains an authenticated provisioning exception: it creates no grant, so configuration and application restart are required before the generated Tenant can be managed.

Health endpoints remain public. Runtime endpoints use a separate bearer dependency and never
interpret the management credential as Agent identity; runtime credentials likewise fail
management authentication. Static principals are configured only after generated Agent IDs exist.
Future evolution may add managed issuance/rotation/revocation and workload identity or mTLS when
deployment requirements justify them.

## Dependency and transaction rules

`presentation → application → domain`; infrastructure points inward by implementing application/domain ports. Domain and shared-kernel code cannot import FastAPI, Pydantic, SQLAlchemy, infrastructure, or presentation. Application cannot import presentation, SQLAlchemy, or concrete infrastructure. The architecture test resolves absolute and relative imports and enforces these rules recursively for architectural layers anywhere below `src/valor`; violations fail CI.

Commands own an explicit Unit of Work. Repositories persist aggregates but never commit. A handler explicitly commits after all invariants and writes succeed; exceptions roll back. Queries may use optimized read paths when justified and do not masquerade as aggregate repositories.

Domain failures contain domain language, never HTTP codes. Application failures remain protocol-independent. Presentation maps them to RFC 9457-style problem details. Unexpected failures do not disclose internal details.

## Events, CQRS, and evolution

Domain aggregates may record in-process domain events. Durable publication evolves only when required:

```mermaid
flowchart LR
  E[Domain event] --> TX[Same database transaction]
  TX --> O[(Transactional outbox)]
  O --> B[Broker]
```

No broker is deployed. CQRS is selective: commands change state; separate query views appear only where read/write models materially differ. Global event sourcing is rejected; append-only event storage may later suit narrow audit workloads.

A module may be extracted only with evidence for independent scaling, failure or latency isolation, security isolation, distinct storage/workload characteristics, independent deployment cadence, or stable team ownership. Extraction requires an owned API/event contract, data ownership, observability, failure semantics, and migration plan. Microservices are an option, not a destination.

## Logging and sensitive data

Logs are structured and prepared for request/correlation context through `structlog.contextvars`. Log allow-listed identifiers, decision outcomes, timing, and safe error classes. Never log API keys, tokens, passwords, connection strings, raw prompts/responses, tool arguments/results, personal data, or credentials. Redaction must occur before the logger boundary; production transports and retention policies are deferred.

The [initial threat model](../security/threat-model.md) records the current assets, trust
boundaries, STRIDE-oriented risks, and prioritized security work. It is a living description of
implemented controls and residual risk, not a claim of production security.
