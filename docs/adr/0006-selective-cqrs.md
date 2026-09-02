# ADR-0006: Use selective rather than global CQRS

**Status:** Accepted

## Context
Some future telemetry and reporting reads may differ greatly from transactional writes, but most early workflows will not.

## Decision
Commands change state through domain models. Introduce separate query models only for demonstrated read complexity, scale, or latency needs.

## Consequences
Simple capabilities remain simple; selected reads can evolve independently. The codebase may contain more than one query style, requiring clear naming and ownership.

## Alternatives considered
Global CQRS was rejected for duplication and consistency overhead. One aggregate model for every read remains the default but is not mandated when evidence contradicts it.

