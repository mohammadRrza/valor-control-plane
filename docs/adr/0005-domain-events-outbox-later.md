# ADR-0005: Model domain events now; add a transactional outbox later

**Status:** Accepted

## Context
VALOR will publish operational and governance facts, but currently has no consumers or throughput evidence requiring a broker.

## Decision
Keep a framework-free DomainEvent primitive. When durable asynchronous consumers exist, persist integration events in an outbox within the domain transaction, then relay them to an evaluated broker.

## Consequences
Domain language can evolve without Kafka today. Delivery semantics, idempotency, schema evolution, and relay operation remain deliberate future work.

## Alternatives considered
Kafka/Redpanda now was rejected as architectural theater. Direct publish after commit was rejected because it creates a dual-write failure window.

