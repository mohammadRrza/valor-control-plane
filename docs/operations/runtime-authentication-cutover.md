# Runtime authentication cutover preparation

Phase 5.0B and 5.0B.1 prepare durable Runtime identities without changing live authentication.
Static Runtime credentials and their static `usage_limit` and `per_invocation_allowance` values
remain authoritative. There is no synchronization, feature flag, dual-authentication mode, or
automatic cutover.

1. Deploy Phase 5.0B.1 and apply migration 0020.
2. Keep every required workload on its current static Runtime credential.
3. For each workload that must survive Phase 5.0C, create a persisted Runtime Principal with the
   equivalent usage values, or initialize the values once on a legacy 5.0A Principal.
4. Store its one-time-returned persisted credential securely with the workload operator.
5. Read the individual Principal and require `cutover_ready=true`. This means only that the
   Principal is active, limits are configured, and a non-revoked credential exists whose expiry is
   later than the read clock. It does not mean Runtime Gateway accepts that credential yet.
6. For every legacy workload, identify its exact static Principal ID and the explicitly selected
   persisted Principal. Confirm exact Tenant/Agent binding and equal usage limits.
7. Run `POST .../identity-continuity/preflight` and require `safe_to_bind=true`.
8. Bind once with `POST .../identity-continuity`, then require
   `identity_continuity_ready=true` on Principal GET.
9. Deliver the persisted credential to the intended workload through the deployment secret system.
   Neither readiness boolean proves this delivery occurred.
10. Do not deploy Phase 5.0C until every required legacy workload satisfies both readiness values
    and credential delivery is confirmed. A genuinely new persisted-only workload needs
    `cutover_ready=true` but no legacy binding.

Phase 5.0C will invalidate static Runtime credentials by switching authentication identity and
usage-limit authority together. Its usage and historical-read queries will use the canonical UUID
plus optional legacy ID without changing historical rows. Downgrading 0020 to 0019 removes the
continuity mappings and binding audits, so Phase 5.0C must not operate until mappings are rebuilt.
