# ADR-0001: Use a DDD-oriented modular monolith

**Status:** Accepted

## Context
VALOR spans distinct business capabilities, but Phase 0 has neither scale evidence nor teams that justify distributed deployment.

## Decision
Build one deployable application with explicit bounded-context and hexagonal dependency boundaries. Add context packages only with working capability; each future context owns its architectural layers, whose dependency direction is checked recursively.

## Consequences
Transactions, development, and operations stay simple, while architecture tests preserve seams. Modules share a process and database deployment, so discipline—not a network—enforces isolation.

## Alternatives considered
Microservices were rejected as premature operational complexity. An unstructured monolith was rejected because it makes later ownership and extraction unsafe.
