# ADR-0002: Use FastAPI and Python 3.13

**Status:** Accepted

## Context
VALOR needs typed HTTP boundaries and strong alignment with the AI ecosystem without coupling domain logic to a web framework.

## Decision
Use Python 3.13, FastAPI at presentation boundaries, Pydantic v2 for boundary schemas, and uv for locked dependencies.

## Consequences
Development is productive and async I/O is available; Python requires runtime validation and disciplined typing. FastAPI types must not leak inward.

## Alternatives considered
Django adds unused full-stack conventions. Go offers stronger compile-time guarantees but weaker alignment with near-term AI integrations and team assumptions.

