# DevOps evolution

Technology is introduced only for an observed problem:

| Capability | Expected problem solved |
|---|---|
| Docker | repeatable process packaging (implemented) |
| Kubernetes, Helm | scheduling and repeatable cluster releases at operational scale |
| Terraform/OpenTofu | reviewed, reproducible infrastructure state |
| GitHub Actions | repeatable quality gates (baseline implemented) |
| Argo CD / Rollouts | reconciled GitOps deployment and measured progressive delivery |
| OpenTelemetry | vendor-neutral distributed context and telemetry |
| Prometheus / Grafana | metric storage, alerting and operational visualization |
| Tempo / Loki | trace and log storage correlated with requests |
| OPA | independently managed, declarative policy where embedded rules cease to fit |
| Vault / External Secrets | short-lived secret distribution and rotation |
| Trivy / Gitleaks / Checkov | image/dependency, secret, and infrastructure misconfiguration checks |
| SBOM / Cosign | artifact inventory, provenance and signature verification |
| SLOs / error budgets | reliability targets and release-risk decisions |
| load / chaos testing | capacity evidence and controlled failure validation |

None except Docker and the CI baseline is implemented in Phase 0. Each addition requires ownership, operating cost, threat/failure model, and measurable acceptance criteria.

