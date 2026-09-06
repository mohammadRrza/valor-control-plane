# VALOR roadmap

This direction is intentionally revisable as architecture and product evidence emerge.

1. **Phase 0 — Foundation (complete):** modular-monolith boundaries, HTTP/database lifecycle, engineering controls, documentation.
2. **Phase 1 — Identity, Tenancy, Asset Registry (in progress):** Tenant create/get plus governed Agent and Model reference register/get vertical slices implemented; remaining identity and asset capabilities are planned.
3. **Phase 2 — LLM Runtime Gateway (in progress):** one synchronous text invocation path, OpenAI Responses adapter, authenticated Tenant/Agent Runtime Principals, principal-isolated Invocation reads, succeeded/failed/denied persistence, default-deny Agent-to-Model policy, and authenticated/Tenant-scoped management are implemented. Credential lifecycle, routing, fallbacks, streaming, and additional providers remain planned.
4. **Phase 3 — Usage and observability (in progress):** durable Invocation duration, normalized provider usage, safe provider response correlation, and bounded Tenant-scoped usage/estimated-cost reporting with fixed Top 10 Agent and Model cost rankings are implemented. Configurable reporting, metrics export, tracing backends, dashboards, alerts, and retention/redaction remain planned; no OpenTelemetry stack is present.
5. **Phase 4 — Policy, Risk & governance evidence (in progress):** first explicit Agent-to-Model permission and persisted decision slice implemented early; successful governance mutations append atomic fingerprint-only audit evidence; independently persisted Management Principals now have Tenant scopes, revocable/rotatable credentials, terminal disablement, and one-time bootstrap. OIDC, MFA, automatic rotation, protected retention, failure-attempt evidence, and richer policy remain planned.
6. **Phase 5 — MCP/Tool Governance:** tool authorization and human approvals.
7. **Phase 6 — Evaluation:** quality suites and deployment gates.
8. **Phase 7 — AI FinOps:** usage facts, sequential UTC-daily Runtime Principal enforcement, immutable Invocation-level estimated USD cost snapshots, read-only Tenant aggregation, and static sequential Tenant daily estimated-cost budgets are implemented early. Invoice reconciliation, pricing lifecycle/sync, budget CRUD, monthly budgets, reservation accounting, strict concurrent quotas, and broader cost controls remain planned.
9. **Phase 8 — Incidents:** detection, response, and automated containment.
10. **Phase 9 — Compliance:** durable audit evidence and reporting.
11. **Phase 10 — Broker/outbox:** Kafka or Redpanda only when event volume and consumers justify it.
12. **Phase 11 — Deployment platform:** Kubernetes, Helm, OpenTofu/Terraform, and GitOps when operational scale requires them.
13. **Phase 12 — Advanced delivery security:** supply-chain controls and progressive delivery based on concrete threat and release models.
