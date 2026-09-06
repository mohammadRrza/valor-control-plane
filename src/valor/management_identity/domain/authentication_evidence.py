from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID


class ManagementAuthenticationOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    CREDENTIAL_MISMATCH = "credential_mismatch"
    REVOKED = "revoked"
    EXPIRED = "expired"
    PRINCIPAL_DISABLED = "principal_disabled"


def hourly_bucket(at: datetime) -> datetime:
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("authentication evidence timestamp must be timezone-aware")
    return at.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


@dataclass(frozen=True, slots=True)
class ManagementAuthenticationEvidence:
    credential_id: UUID
    principal_id: UUID
    outcome: ManagementAuthenticationOutcome
    bucket_started_at: datetime
    first_observed_at: datetime

    def __post_init__(self) -> None:
        if self.first_observed_at.tzinfo is None or self.first_observed_at.utcoffset() is None:
            raise ValueError("authentication evidence timestamp must be timezone-aware")
        if self.bucket_started_at != hourly_bucket(self.first_observed_at):
            raise ValueError("authentication evidence must use its UTC hourly bucket")
