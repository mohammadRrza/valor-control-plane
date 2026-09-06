from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from valor.management_identity.domain.authentication_evidence import (
    ManagementAuthenticationEvidence,
)

MAX_AUTHENTICATION_EVIDENCE_RANGE = timedelta(days=31)


class InvalidAuthenticationEvidenceQuery(Exception):
    pass


class ManagementAuthenticationEvidenceReaderPort(Protocol):
    async def list_evidence(
        self,
        *,
        credential_id: UUID | None,
        principal_id: UUID | None,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> Sequence[ManagementAuthenticationEvidence]: ...


@dataclass(frozen=True, slots=True)
class ListManagementAuthenticationEvidenceQuery:
    credential_id: UUID | None
    principal_id: UUID | None
    start: datetime
    end: datetime
    limit: int = 50


class ListManagementAuthenticationEvidenceHandler:
    def __init__(self, reader: ManagementAuthenticationEvidenceReaderPort) -> None:
        self._reader = reader

    async def __call__(
        self, query: ListManagementAuthenticationEvidenceQuery
    ) -> Sequence[ManagementAuthenticationEvidence]:
        if (query.credential_id is None) == (query.principal_id is None):
            raise InvalidAuthenticationEvidenceQuery(
                "exactly one of credential_id or principal_id is required"
            )
        start, end = _validated_range(query.start, query.end)
        if not 1 <= query.limit <= 100:
            raise InvalidAuthenticationEvidenceQuery("limit must be between 1 and 100")
        return await self._reader.list_evidence(
            credential_id=query.credential_id,
            principal_id=query.principal_id,
            start=start,
            end=end,
            limit=query.limit,
        )


def _validated_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    if start.tzinfo is None or start.utcoffset() is None:
        raise InvalidAuthenticationEvidenceQuery("start must include a timezone offset")
    if end.tzinfo is None or end.utcoffset() is None:
        raise InvalidAuthenticationEvidenceQuery("end must include a timezone offset")
    utc_start, utc_end = start.astimezone(UTC), end.astimezone(UTC)
    if utc_start >= utc_end:
        raise InvalidAuthenticationEvidenceQuery("start must be earlier than end")
    if utc_end - utc_start > MAX_AUTHENTICATION_EVIDENCE_RANGE:
        raise InvalidAuthenticationEvidenceQuery(
            "authentication evidence range must not exceed 31 days"
        )
    return utc_start, utc_end
