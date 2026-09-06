# ADR-0020: Bound Management credential-use evidence by UTC hour

## Status

Accepted.

## Decision

Management authentication records credential-use evidence only after the public credential UUID
resolves. Evidence identifies the credential, its owning Principal, one outcome, the UTC-hour
bucket, and the first observation time. Outcomes are `succeeded`, `credential_mismatch`,
`revoked`, `expired`, and `principal_disabled`.

Lifecycle outcomes are recorded only after the supplied secret matches the persisted verifier.
Consequently, knowledge of a public credential UUID cannot fabricate revoked, expired, or disabled
use evidence. A mismatch means an attempt targeted a known credential; it does not attribute the
attempt to the owning Principal. Malformed bearer values and unknown UUIDs are external garbage and
are not persisted. Every failure remains the same generic 401 response externally.

The primary key is `(credential_id, outcome, bucket_started_at)` and writes use `ON CONFLICT DO
NOTHING`. Repetition therefore causes at most one durable row per credential, outcome, and UTC
hour. Authentication opportunistically removes buckets older than 90 days using an indexed bucket
timestamp. Counts are intentionally not stored: exact attempt counting would turn attacker traffic
into database write amplification. One row means the outcome was observed at least once in that
hour, not exactly once.

Evidence belongs to `management_identity`, which already owns credential verification and
lifecycle state. It is distinct from atomic governance-mutation records in `management_audit` and
does not create a generic security-event abstraction. Runtime authentication is unchanged.

## Consequences

Operators gain bounded forensic evidence of successful credential use and safely attributable
credential failures without storing bearer tokens, secrets, verifiers, headers, payloads, IP
addresses, or user-agent strings. Repeated attempts still execute an idempotent database statement,
but durable writes and retained cardinality are bounded. The first-observation-only model does not
provide exact counts, ordering within an hour, last-use time, network attribution, alerting, or a
read API. Evidence availability shares the Management authentication database dependency.
