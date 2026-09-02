# ADR-0003: Use PostgreSQL as the primary transactional store

**Status:** Accepted

## Context
Future tenancy, policy, asset, incident, and audit metadata require reliable transactions and mature operations.

## Decision
Use PostgreSQL with SQLAlchemy 2.x, Psycopg 3, and Alembic. No schema-per-context or domain tables are invented in Phase 0.

## Consequences
VALOR gains ACID semantics and a future outbox path, at the cost of operating one stateful dependency. Context data ownership must remain explicit inside a shared deployment.

## Alternatives considered
SQLite does not represent production concurrency. Document and key-value stores weaken relational constraints without a demonstrated access-pattern benefit.

