# Runtime authentication cutover preparation

Phase 5.0B prepares durable Runtime identities without changing live Runtime authentication.
Static Runtime credentials and their static `usage_limit` and `per_invocation_allowance` values
remain authoritative. There is no synchronization, feature flag, dual-authentication mode, or
automatic cutover.

1. Deploy Phase 5.0B and apply migration 0019.
2. Keep every required workload on its current static Runtime credential.
3. For each workload that must survive Phase 5.0C, create a persisted Runtime Principal with the
   equivalent usage values, or initialize the values once on a legacy 5.0A Principal.
4. Store its one-time-returned persisted credential securely with the workload operator.
5. Read the individual Principal and require `cutover_ready=true`. This means only that the
   Principal is active, limits are configured, and a non-revoked credential exists whose expiry is
   later than the read clock. It does not mean Runtime Gateway accepts that credential yet.
6. Do not deploy Phase 5.0C until every required workload is ready and its operator can switch.

Phase 5.0C will invalidate static Runtime credentials by switching authentication identity and
usage-limit authority together. Downgrading 0019 to 0018 removes persisted usage-limit preparation
and its initialization audit rows, but retains Runtime Principals and credentials.
