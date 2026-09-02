# ADR-0008: Extract services only against explicit criteria

**Status:** Accepted

## Context
Module boundaries should permit evolution without assuming microservices are the destination.

## Decision
Consider extraction only for evidenced independent scaling, failure/latency/security isolation, distinct data characteristics, deployment cadence, or team ownership. Require a stable contract, data migration, observability, failure behavior, and operational owner.

## Consequences
The default remains operationally simple. A justified extraction requires up-front migration effort and accepts distributed consistency and network failure.

## Alternatives considered
Service-per-context was rejected because domain boundaries do not automatically require process boundaries. Never extracting was rejected because high-volume telemetry or strict isolation may eventually demand it.

