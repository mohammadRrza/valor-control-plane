# VALOR Control Plane

**Verifiable Agent Lifecycle, Observability & Risk (VALOR)** is a self-hostable control-plane project for organizations operating LLM applications and autonomous agents. It is intended to govern and explain requests crossing from applications and agents to model providers, MCP servers, enterprise tools, databases, and APIs.

VALOR is not an agent framework, chatbot, LLM provider, generic API gateway, monitoring replacement, Kubernetes replacement, or microservices demonstration.

## Status

**Current phase: Phase 0 — Architecture & Engineering Foundation.**

Implemented: a FastAPI application factory; PostgreSQL connectivity and readiness; liveness; centralized validated settings; structured logging; explicit SQLAlchemy Unit of Work; Alembic; architecture tests; CI; and local containers.

Planned: all product capabilities, including identity, tenancy, asset registry, runtime routing, policy, evaluation, telemetry, FinOps, incidents, and compliance. No domain capability is represented as complete.

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

The API listens on port 8000. Operational endpoints are `/health/live` and `/health/ready`; future domain APIs are versioned under `/api/v1`.

## Repository layout

```text
src/valor/
  api/             HTTP boundary and operational routes
  application/     use-case ports and orchestration contracts
  bootstrap/       composition, lifecycle, configuration, logging
  infrastructure/  concrete adapters
  shared_kernel/   minimal framework-free primitives
tests/             unit, integration, and architecture checks
migrations/        Alembic environment and revisions
docs/              architecture and decisions
```

## Security and contributions

Never commit `.env`, secrets, tokens, credentials, or sensitive payloads. Logs must use allow-listed metadata and must not contain prompts or credentials. Treat migrations as reviewed production changes: provide reversible downgrades where safe and never edit an applied revision. Contributions should include proportionate tests, updated documentation, and pass every `make lint`, `make typecheck`, and `make test` check. Use Conventional Commit subjects (for example, `feat(identity): register tenant`) without adding commit tooling solely to enforce formatting.

The roadmap is documented in [ROADMAP.md](ROADMAP.md). VALOR is licensed under the [Apache License 2.0](LICENSE).
