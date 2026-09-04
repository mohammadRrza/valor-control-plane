"""Tenant-scoped read model for bounded Runtime operational reporting."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Protocol

from valor.runtime_gateway.domain.identity import TenantId

MAX_REPORT_RANGE = timedelta(days=31)


class InvalidReportRange(Exception):
    """The requested reporting interval is invalid or unsafe."""


class TenantRuntimeReportNotFound(Exception):
    """The requested Tenant is unavailable within the caller's scope."""


class RuntimeReportUnavailable(Exception):
    """The reporting read dependency could not serve the request."""


@dataclass(frozen=True, slots=True)
class InvocationCounts:
    total: int
    succeeded: int
    failed: int
    denied: int
    limited: int


@dataclass(frozen=True, slots=True)
class UsageTotals:
    input_units: int
    output_units: int
    total_units: int
    provider_executed_invocations: int
    attributed_invocations: int
    unavailable_invocations: int


@dataclass(frozen=True, slots=True)
class EstimatedCostTotals:
    currency: str
    total: Decimal
    attributed_invocations: int
    unavailable_invocations: int


@dataclass(frozen=True, slots=True)
class TenantRuntimeReport:
    tenant_id: TenantId
    start: datetime
    end: datetime
    invocations: InvocationCounts
    usage: UsageTotals
    estimated_cost: EstimatedCostTotals


class TenantRuntimeReportReaderPort(Protocol):
    async def tenant_exists(self, tenant_id: TenantId) -> bool: ...

    async def get_report(
        self, *, tenant_id: TenantId, start: datetime, end: datetime
    ) -> TenantRuntimeReport: ...


@dataclass(frozen=True, slots=True)
class GetTenantRuntimeReportQuery:
    tenant_id: TenantId
    start: datetime
    end: datetime


class GetTenantRuntimeReportHandler:
    def __init__(self, reader: TenantRuntimeReportReaderPort) -> None:
        self._reader = reader

    async def __call__(self, query: GetTenantRuntimeReportQuery) -> TenantRuntimeReport:
        start, end = _validated_utc_range(query.start, query.end)
        if not await self._reader.tenant_exists(query.tenant_id):
            raise TenantRuntimeReportNotFound
        return await self._reader.get_report(tenant_id=query.tenant_id, start=start, end=end)


def _validated_utc_range(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    if start.tzinfo is None or start.utcoffset() is None:
        raise InvalidReportRange("start must include a timezone offset")
    if end.tzinfo is None or end.utcoffset() is None:
        raise InvalidReportRange("end must include a timezone offset")
    utc_start = start.astimezone(UTC)
    utc_end = end.astimezone(UTC)
    if utc_start >= utc_end:
        raise InvalidReportRange("start must be earlier than end")
    if utc_end - utc_start > MAX_REPORT_RANGE:
        raise InvalidReportRange("reporting range must not exceed 31 days")
    return utc_start, utc_end
