from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import UUID

from valor.management_audit.domain.audit_record import ManagementAuditRecord

MAX_AUDIT_RANGE = timedelta(days=31)


class InvalidAuditRange(Exception):
    pass


class TenantAuditNotFound(Exception):
    pass


class ManagementAuditUnavailable(Exception):
    pass


class ManagementAuditReaderPort(Protocol):
    async def tenant_exists(self, tenant_id: UUID) -> bool: ...

    async def list_for_tenant(
        self, *, tenant_id: UUID, start: datetime, end: datetime, limit: int
    ) -> Sequence[ManagementAuditRecord]: ...


@dataclass(frozen=True, slots=True)
class ListManagementAuditRecordsQuery:
    tenant_id: UUID
    start: datetime
    end: datetime
    limit: int = 50


class ListManagementAuditRecordsHandler:
    def __init__(self, reader: ManagementAuditReaderPort) -> None:
        self._reader = reader

    async def __call__(
        self, query: ListManagementAuditRecordsQuery
    ) -> Sequence[ManagementAuditRecord]:
        start, end = _validated_range(query.start, query.end)
        if not 1 <= query.limit <= 100:
            raise InvalidAuditRange("limit must be between 1 and 100")
        if not await self._reader.tenant_exists(query.tenant_id):
            raise TenantAuditNotFound
        return await self._reader.list_for_tenant(
            tenant_id=query.tenant_id, start=start, end=end, limit=query.limit
        )


def _validated_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    if start.tzinfo is None or start.utcoffset() is None:
        raise InvalidAuditRange("start must include a timezone offset")
    if end.tzinfo is None or end.utcoffset() is None:
        raise InvalidAuditRange("end must include a timezone offset")
    utc_start, utc_end = start.astimezone(UTC), end.astimezone(UTC)
    if utc_start >= utc_end:
        raise InvalidAuditRange("start must be earlier than end")
    if utc_end - utc_start > MAX_AUDIT_RANGE:
        raise InvalidAuditRange("audit range must not exceed 31 days")
    return utc_start, utc_end
