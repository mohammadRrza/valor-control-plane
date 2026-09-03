# VALOR Control Plane

**Verifiable Agent Lifecycle, Observability & Risk (VALOR)** is a self-hostable control-plane project for organizations operating LLM applications and autonomous agents. It is intended to govern and explain requests crossing from applications and agents to model providers, MCP servers, enterprise tools, databases, and APIs.

VALOR is not an agent framework, chatbot, LLM provider, generic API gateway, monitoring replacement, Kubernetes replacement, or microservices demonstration.

## Status

**Current phase: Phase 1 — Identity & Tenancy (in progress).**

Implemented: the Phase 0 engineering foundation; Tenant create/get; and AI Asset Registry Agent and governed Model reference register/get slices, with PostgreSQL persistence, explicit tenant ownership, and scoped normalized-name uniqueness.

Planned: the rest of Identity & Tenancy and AI Asset Registry, plus runtime routing, model/prompt/tool management, policy, evaluation, telemetry, FinOps, incident, and compliance capabilities. Neither implemented bounded context is complete.

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
  infrastructure/  concrete adapters
  shared_kernel/   minimal framework-free primitives
tests/             unit, integration, and architecture checks
migrations/        Alembic environment and revisions
docs/              architecture and decisions
```

## Security and contributions

Never commit `.env`, secrets, tokens, credentials, or sensitive payloads. Logs must use allow-listed metadata and must not contain prompts or credentials. Treat migrations as reviewed production changes: provide reversible downgrades where safe and never edit an applied revision. Contributions should include proportionate tests, updated documentation, and pass every `make lint`, `make typecheck`, and `make test` check. Use Conventional Commit subjects (for example, `feat(identity): register tenant`) without adding commit tooling solely to enforce formatting.

**Security status:** authentication and authorization are not implemented. Tenant, Agent, and Model management endpoints must not be exposed to untrusted networks in their current form. Model records are governance references only: they contain no provider credentials, connectivity, invocation behavior, or verification that a provider-side model exists.

The roadmap is documented in [ROADMAP.md](ROADMAP.md). VALOR is licensed under the [Apache License 2.0](LICENSE).
