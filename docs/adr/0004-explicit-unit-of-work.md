# ADR-0004: Use explicit Unit of Work transaction boundaries

**Status:** Accepted

## Context
Hidden repository commits make multi-aggregate work and future outbox publication unreliable.

## Decision
Application command handlers enter a Unit of Work and explicitly commit. Repositories only stage persistence; exceptions cause rollback and sessions always close.

## Consequences
Atomicity is visible and testable. Handlers carry modest ceremony, and developers must choose transaction scope deliberately.

## Alternatives considered
Commit-per-repository was rejected for partial writes. Framework middleware transactions were rejected because they obscure intent and often over-broaden query transactions.

