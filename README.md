# VALOR Control Plane

**Verifiable Agent Lifecycle, Observability & Risk (VALOR)** is a self-hostable control-plane project for organizations operating LLM applications and autonomous agents. It is intended to govern and explain requests crossing from applications and agents to model providers, MCP servers, enterprise tools, databases, and APIs.

VALOR is not an agent framework, chatbot, LLM provider, generic API gateway, monitoring replacement, Kubernetes replacement, or microservices demonstration.

## Status

**Current phase: Phase 4 — Management governance evidence (in progress).**

Implemented: the Phase 0 engineering foundation; Tenant create/get; AI Asset Registry Agent and governed Model reference register/get; one synchronous OpenAI Runtime Gateway path; Policy & Risk Agent-to-Model ALLOW/DENY permissions with default-deny enforcement, persisted decisions, and denied runtime outcomes; static management authentication and Tenant authorization; separate static Runtime Principal authentication with Invocation read isolation; persisted Invocation duration, normalized provider usage, safe provider response correlation, immutable estimated-cost snapshots; bounded Tenant-scoped Runtime usage/cost reporting; and sequential Tenant daily estimated-cost budget enforcement.

Successful Agent-to-Model permission PUTs append actor-correlated, fingerprint-only Management
audit evidence in the same PostgreSQL transaction. Static Tenant budget file changes remain outside
VALOR's observable Management API and are not audited.

Each Runtime Principal also requires an explicit UTC-daily total-unit limit and per-invocation
allowance. After policy ALLOW, provider execution requires `known consumed total_units + allowance
<= limit`. A rejection is persisted as a distinct `limited` Invocation and returned as 429. This
provides deterministic sequential-request enforcement only; concurrent requests may overshoot.

Successful Invocations with complete input/output usage and matching static pricing also persist an
immutable estimated USD cost snapshot. Pricing resolves by provider plus exact provider model
reference. Costs use 12-decimal exact precision and remain stable when configuration changes.
These values are configured attribution estimates, not reconciled provider invoice amounts.

Planned: dynamic management grants, managed runtime credential rotation/revocation, richer conditional policy, human approval, tool/MCP governance, runtime routing and additional providers, evaluation, telemetry export, FinOps, incident, and compliance capabilities. Billing, budgets, rate limits, dashboards, exports, alerts, tracing backends, analytics warehouses, and retention/redaction are not implemented. No bounded context, policy engine, identity platform, or LLM gateway is complete.

Experimental: none.

## Architecture

VALOR begins as a DDD-oriented modular monolith using hexagonal boundaries. Domain code is framework-independent; application code coordinates use cases and owns ports; infrastructure implements ports; presentation translates HTTP. Modules are candidates for services only when measured operational or organizational needs justify extraction. See [architecture](docs/architecture/README.md) and [ADRs](docs/adr/).

## Local development

Prerequisites: Python 3.13, [uv](https://docs.astral.sh/uv/), and optionally Docker.

```bash
cp .env.example .env
# Supply a stable management principal ID, a long random token, and an explicit
# JSON array of manageable Tenant UUIDs. An empty array grants no Tenant access.
# After registering Agents, configure distinct runtime principals as a JSON array;
# each entry binds identity and credential plus usage_limit and per_invocation_allowance.
# Replace every example credential before any non-local use.
uv sync --frozen
uv run uvicorn valor.main:create_app --factory --reload
```

Real OpenAI invocations require `VALOR_PROVIDER__OPENAI_API_KEY`. The adapter uses the OpenAI Responses API with a 30-second default timeout and requests `store=false`. Registry and health functionality can run without provider credentials; attempting an OpenAI runtime invocation without them returns a sanitized upstream-failure response.

Useful commands:

```bash
make lint              # Ruff lint and format check
make typecheck         # strict mypy
make test              # all tests
make architecture      # dependency rules
make migrate           # Alembic upgrade
make build             # wheel and source distribution
make docker-up         # API + PostgreSQL
make docker-down
```

The API listens on port 8000. Operational endpoints are `/health/live` and `/health/ready` and remain public. Send the management bearer credential to Tenant, Agent, Model, and Policy routes; existing-Tenant operations also require configured Tenant scope. Runtime routes require a distinct Runtime Principal bearer credential. Management and runtime credentials are mutually rejected.

```text
POST /api/v1/tenants
GET  /api/v1/tenants/{tenant_id}
POST /api/v1/agents
GET  /api/v1/agents/{agent_id}
POST /api/v1/models
GET  /api/v1/models/{model_id}
POST /api/v1/runtime/invocations  # body: model_id + input; Tenant/Agent come from credential
GET  /api/v1/runtime/invocations/{invocation_id}
PUT  /api/v1/policies/agent-model-permissions
GET  /api/v1/policies/agent-model-permissions/{permission_id}
GET  /api/v1/tenants/{tenant_id}/audit-records?start=...&end=...&limit=50
```

## Repository layout

```text
src/valor/
  api/             HTTP boundary and operational routes
  application/     use-case ports and orchestration contracts
  bootstrap/       composition, lifecycle, configuration, logging
  ai_asset_registry/
    domain/         governed Agent/Model identities and focused repository ports
    application/    register/get use cases and tenant-existence port
    infrastructure/ focused persistence/UoW and tenant-existence adapters
    presentation/   Agent/Model HTTP contracts, routes, and error mappings
  identity_tenancy/
    domain/         Tenant aggregate and repository port
    application/    CreateTenant and GetTenant use cases
    infrastructure/ SQLAlchemy mapping, repository, and UoW adapter
    presentation/   tenant HTTP contracts, routes, and error mapping
  runtime_gateway/
    domain/         Invocation identity, final status, text, duration, and usage invariants
    application/    CreateInvocation/GetInvocation and narrow runtime ports
    infrastructure/ PostgreSQL admission/persistence and OpenAI Responses adapter
    presentation/   runtime HTTP contracts, routes, and error mappings
  policy_risk/
    domain/         explicit Agent-Model Permission and policy Decision
    application/    permission set/get and default-deny evaluation
    infrastructure/ PostgreSQL policy persistence/admission/runtime adapter
    presentation/   permission HTTP contracts, routes, and errors
  management_audit/
    domain/         immutable audit evidence and canonical fingerprints
    application/    bounded Tenant audit query and reader port
    infrastructure/ append-only persistence and PostgreSQL reader
    presentation/   Tenant-scoped audit records route and errors
  security/
    application/    authenticated principal and explicit Tenant authorization rule
    presentation/   bearer parsing, constant-time validation, and HTTP error mapping
  infrastructure/  concrete adapters
  shared_kernel/   minimal framework-free primitives
tests/             unit, integration, and architecture checks
migrations/        Alembic environment and revisions
docs/              architecture and decisions
```

## Security and contributions

Never commit `.env`, secrets, tokens, credentials, or sensitive payloads. Logs must use allow-listed metadata and must not contain prompts or credentials. Treat migrations as reviewed production changes: provide reversible downgrades where safe and never edit an applied revision. Contributions should include proportionate tests, updated documentation, and pass every `make lint`, `make typecheck`, and `make test` check. Use Conventional Commit subjects (for example, `feat(identity): register tenant`) without adding commit tooling solely to enforce formatting.

**Security status:** Management endpoints require a static management bearer credential and exact configured Tenant scope. Runtime endpoints require separate static credentials, each bound to exactly one Tenant and Agent. POST identity is derived from that binding; GET is isolated by runtime principal, Tenant, and Agent. Cross-boundary and cross-principal credentials are rejected. No bearer credential is persisted, logged, or returned.

Tenant creation is an authenticated provisioning exception because its generated UUID cannot be scoped before creation. Creation does not grant access. Add the returned UUID to `VALOR_SECURITY__MANAGEMENT_TENANT_IDS` and restart the application before retrieving the Tenant or managing its Agents, Models, and permissions. The value uses JSON-array syntax, for example `["00000000-0000-4000-8000-000000000001"]`.

Runtime authentication does not replace authorization: an explicit ALLOW for the authenticated Tenant/Agent and requested Model remains required. Static runtime configuration has no issuance, rotation, revocation, expiry, rate limits, or workload federation, so this remains an interim boundary requiring TLS and secure secret injection.

Invocation input and output text are currently persisted for this first runtime/audit slice and returned by the Invocation API. Raw input/output and credentials are not logged. Redaction, retention, data classification, access controls, and encryption policy are not yet implemented, so this storage policy is not production-complete for sensitive workloads.

Invocation responses also expose integer lifecycle duration, provider-neutral input/output/total
usage units when supplied, and a sanitized provider response identifier when available. These are
durable attribution facts, not a metrics, tracing, pricing, billing, generalized budget, quota, or
abuse-control system. Usage telemetry does not solve sensitive-data retention.

Pricing entries are optional static configuration. Missing pricing or incomplete usage leaves
`estimated_cost` null without blocking successful execution. The Management endpoint
`GET /api/v1/tenants/{tenant_id}/runtime-report?start=...&end=...` aggregates persisted usage and
estimated cost over a required UTC-aware half-open range of at most 31 days. It also returns fixed
Top 10 Agent and Model lists ranked by persisted estimated cost, with UUID tie-breaks and
completeness counts. It does not reprice history. No configurable ranking, billing, pricing
synchronization, or historical backfill is implemented.

Runtime execution requires an explicit static Tenant budget entry. After policy and usage-limit
checks, VALOR sums known persisted `cost_total` snapshots for the current UTC day and permits the
provider only when `known cost + per-invocation allowance <= daily budget`. Missing configuration
or an unavailable cost read fails closed. A monetary rejection returns 429 and persists a distinct
`cost_limited` Invocation with the evaluated decision evidence.

Warning: VALOR's Tenant budget is enforced against known persisted estimated-cost attribution. It
does not guarantee that actual provider invoice spend cannot exceed the configured value. Missing
attribution, one-request overshoot, and concurrent overshoot remain possible.

The [initial threat model](docs/security/threat-model.md) documents current trust boundaries,
material risks, and the recommended security sequence. The roadmap is documented in
[ROADMAP.md](ROADMAP.md). VALOR is licensed under the [Apache License 2.0](LICENSE).
