# VALOR Control Plane

**Verifiable Agent Lifecycle, Observability & Risk (VALOR)** is a self-hostable control-plane project for organizations operating LLM applications and autonomous agents. It is intended to govern and explain requests crossing from applications and agents to model providers, MCP servers, enterprise tools, databases, and APIs.

VALOR is not an agent framework, chatbot, LLM provider, generic API gateway, monitoring replacement, Kubernetes replacement, or microservices demonstration.

## Status

**Current phase: Phase 2 — Runtime Gateway (in progress).**

Implemented: the Phase 0 engineering foundation; Tenant create/get; AI Asset Registry Agent and governed Model reference register/get; one synchronous OpenAI Runtime Gateway path; and Policy & Risk Agent-to-Model ALLOW/DENY permissions with default-deny enforcement, persisted decisions, and denied runtime outcomes.

Planned: richer conditional policy, protected management APIs, human approval, tool/MCP governance, runtime routing and additional providers, evaluation, telemetry, FinOps, incident, and compliance capabilities. No bounded context, policy engine, or LLM gateway is complete.

Experimental: none.

## Architecture

VALOR begins as a DDD-oriented modular monolith using hexagonal boundaries. Domain code is framework-independent; application code coordinates use cases and owns ports; infrastructure implements ports; presentation translates HTTP. Modules are candidates for services only when measured operational or organizational needs justify extraction. See [architecture](docs/architecture/README.md) and [ADRs](docs/adr/).

## Local development

Prerequisites: Python 3.13, [uv](https://docs.astral.sh/uv/), and optionally Docker.

```bash
cp .env.example .env
# Replace example credentials before any non-local use.
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

The API listens on port 8000. Operational endpoints are `/health/live` and `/health/ready`. Implemented domain routes are:

```text
POST /api/v1/tenants
GET  /api/v1/tenants/{tenant_id}
POST /api/v1/agents
GET  /api/v1/agents/{agent_id}
POST /api/v1/models
GET  /api/v1/models/{model_id}
POST /api/v1/runtime/invocations
GET  /api/v1/runtime/invocations/{invocation_id}
PUT  /api/v1/policies/agent-model-permissions
GET  /api/v1/policies/agent-model-permissions/{permission_id}
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
    domain/         Invocation identity, final status, and text invariants
    application/    CreateInvocation/GetInvocation and narrow runtime ports
    infrastructure/ PostgreSQL admission/persistence and OpenAI Responses adapter
    presentation/   runtime HTTP contracts, routes, and error mappings
  policy_risk/
    domain/         explicit Agent-Model Permission and policy Decision
    application/    permission set/get and default-deny evaluation
    infrastructure/ PostgreSQL policy persistence/admission/runtime adapter
    presentation/   permission HTTP contracts, routes, and errors
  infrastructure/  concrete adapters
  shared_kernel/   minimal framework-free primitives
tests/             unit, integration, and architecture checks
migrations/        Alembic environment and revisions
docs/              architecture and decisions
```

## Security and contributions

Never commit `.env`, secrets, tokens, credentials, or sensitive payloads. Logs must use allow-listed metadata and must not contain prompts or credentials. Treat migrations as reviewed production changes: provide reversible downgrades where safe and never edit an applied revision. Contributions should include proportionate tests, updated documentation, and pass every `make lint`, `make typecheck`, and `make test` check. Use Conventional Commit subjects (for example, `feat(identity): register tenant`) without adding commit tooling solely to enforce formatting.

**Security status:** authentication and authorization are not implemented. Tenant, Agent, Model, and Runtime endpoints must not be exposed to untrusted networks. Model records remain governance references; OpenAI credentials come only from environment configuration and are not persisted or returned.

Runtime execution is now default-deny: an explicit ALLOW for the exact Tenant/Agent/Model tuple is required before the provider can run. Policy-management endpoints are also unauthenticated, however, so any caller who can reach them can grant ALLOW and defeat this governance control. They must not be exposed to untrusted networks.

Invocation input and output text are currently persisted for this first runtime/audit slice and returned by the Invocation API. Raw input/output and credentials are not logged. Redaction, retention, data classification, access controls, and encryption policy are not yet implemented, so this storage policy is not production-complete for sensitive workloads.

The roadmap is documented in [ROADMAP.md](ROADMAP.md). VALOR is licensed under the [Apache License 2.0](LICENSE).
