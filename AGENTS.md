# VALOR engineering constitution

- Read `README.md`, `docs/architecture/`, and applicable ADRs before changing architecture.
- Preserve `presentation → application → domain`; infrastructure implements inward-facing ports. Domain/shared kernel never imports frameworks, persistence, HTTP, or infrastructure. Application never imports presentation or concrete adapters.
- Keep bounded contexts cohesive. Do not import another context's internals; use explicit published contracts. Do not create empty future-context packages.
- Put future domain functionality in its bounded context with local `domain`, `application`, `infrastructure`, and `presentation` layers. Do not let global top-level application or infrastructure packages become cross-context dumping grounds; architecture checks enforce layer direction recursively.
- Use domain language and focused modules. No generic repositories, base services, manager/helper/util dumping grounds, speculative interfaces, or inheritance for convenience.
- Domain logic is synchronous, deterministic, and uses standard Python types. Pydantic belongs at boundaries. ORM models never leave infrastructure and are never API DTOs.
- Commands define explicit Unit of Work boundaries. Repositories never commit. Handle rollback deliberately; migrations must be reviewed, safe, and never rewritten after application.
- Domain/application errors contain no HTTP concepts. Presentation maps failures to consistent problem details without leaking internals.
- Maintain strict practical typing; avoid `Any` and broad ignores. Add unit tests for pure behavior, integration tests for real adapters, and architecture tests for boundaries.
- Never commit secrets or log credentials, tokens, connection URLs, prompts, sensitive payloads, or personal data. Use centralized settings and secure defaults.
- Do not add brokers, caches, orchestration, policy engines, telemetry stacks, or cloud infrastructure without a demonstrated current requirement and ADR.
- Do not describe scaffolding, mocks, or planned work as implemented. Keep README status accurate and update ADRs/docs with material decisions.
- Before declaring completion run: `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest`, `uv run alembic upgrade head`, `uv build`, and applicable Docker checks. Report skipped or unavailable checks explicitly.
