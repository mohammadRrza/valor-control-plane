# VALOR roadmap

This direction is intentionally revisable as architecture and product evidence emerge.

1. **Phase 0 — Foundation (complete):** modular-monolith boundaries, HTTP/database lifecycle, engineering controls, documentation.
2. **Phase 1 — Identity, Tenancy, Asset Registry (in progress):** Tenant create/get plus governed Agent and Model reference register/get vertical slices implemented; remaining identity and asset capabilities are planned.
3. **Phase 2 — LLM Runtime Gateway (in progress):** one synchronous text invocation path, OpenAI Responses adapter, authenticated Tenant/Agent Runtime Principals, principal-isolated Invocation reads, succeeded/failed/denied persistence, default-deny Agent-to-Model policy, and authenticated/Tenant-scoped management are implemented. Credential lifecycle, routing, fallbacks, streaming, and additional providers remain planned.
4. **Phase 3 — Telemetry:** OpenTelemetry-based request and agent traces.
5. **Phase 4 — Policy & Risk:** first explicit Agent-to-Model permission and persisted decision slice implemented early; administration is authenticated and statically Tenant-scoped; dynamic grants, richer conditions, and explainable policy evolution remain planned.
6. **Phase 5 — MCP/Tool Governance:** tool authorization and human approvals.
7. **Phase 6 — Evaluation:** quality suites and deployment gates.
8. **Phase 7 — AI FinOps:** usage attribution, budgets, and cost controls.
9. **Phase 8 — Incidents:** detection, response, and automated containment.
10. **Phase 9 — Compliance:** durable audit evidence and reporting.
11. **Phase 10 — Broker/outbox:** Kafka or Redpanda only when event volume and consumers justify it.
12. **Phase 11 — Deployment platform:** Kubernetes, Helm, OpenTofu/Terraform, and GitOps when operational scale requires them.
13. **Phase 12 — Advanced delivery security:** supply-chain controls and progressive delivery based on concrete threat and release models.
