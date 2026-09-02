# ADR-0007: Avoid global event sourcing

**Status:** Accepted

## Context
Auditability does not imply every aggregate must reconstruct state from events.

## Decision
Persist current transactional state normally. Evaluate append-only/event-sourced storage only for narrowly scoped compliance evidence where temporal reconstruction is essential.

## Consequences
CRUD-like persistence and migrations remain understandable. Temporal history must be designed explicitly for the contexts that need it rather than appearing automatically.

## Alternatives considered
Global event sourcing was rejected due to projection, schema-evolution, debugging, and operational costs. Database audit triggers alone were rejected as insufficient domain evidence.

