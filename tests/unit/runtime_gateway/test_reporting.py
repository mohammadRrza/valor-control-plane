from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

import pytest

from valor.runtime_gateway.application.reporting import (
    MAX_REPORT_RANGE,
    EstimatedCostTotals,
    GetTenantRuntimeReportHandler,
    GetTenantRuntimeReportQuery,
    InvalidReportRange,
    InvocationCounts,
    TenantRuntimeReport,
    TenantRuntimeReportNotFound,
    UsageTotals,
)
from valor.runtime_gateway.domain.identity import TenantId

TENANT_ID = TenantId(UUID("11111111-1111-4111-8111-111111111111"))
START = datetime(2026, 9, 1, tzinfo=UTC)


class ReportReaderStub:
    def __init__(self, *, exists: bool = True) -> None:
        self.exists = exists
        self.request: tuple[TenantId, datetime, datetime] | None = None

    async def tenant_exists(self, tenant_id: TenantId) -> bool:
        assert tenant_id == TENANT_ID
        return self.exists

    async def get_report(
        self, *, tenant_id: TenantId, start: datetime, end: datetime
    ) -> TenantRuntimeReport:
        self.request = (tenant_id, start, end)
        return TenantRuntimeReport(
            tenant_id,
            start,
            end,
            InvocationCounts(0, 0, 0, 0, 0),
            UsageTotals(0, 0, 0, 0, 0, 0),
            EstimatedCostTotals("USD", Decimal("0.000000000000"), 0, 0),
        )


@pytest.mark.asyncio
async def test_handler_accepts_exact_maximum_and_normalizes_to_utc() -> None:
    reader = ReportReaderStub()
    offset = timezone(timedelta(hours=2))
    start = START.astimezone(offset)
    end = start + MAX_REPORT_RANGE

    report = await GetTenantRuntimeReportHandler(reader)(
        GetTenantRuntimeReportQuery(TENANT_ID, start, end)
    )

    assert report.start == START
    assert report.end == START + MAX_REPORT_RANGE
    assert reader.request == (TENANT_ID, START, START + MAX_REPORT_RANGE)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("start", "end"),
    [
        (START.replace(tzinfo=None), START + timedelta(hours=1)),
        (START, (START + timedelta(hours=1)).replace(tzinfo=None)),
        (START, START),
        (START + timedelta(seconds=1), START),
        (START, START + MAX_REPORT_RANGE + timedelta(microseconds=1)),
    ],
)
async def test_handler_rejects_invalid_ranges(start: datetime, end: datetime) -> None:
    reader = ReportReaderStub()
    with pytest.raises(InvalidReportRange):
        await GetTenantRuntimeReportHandler(reader)(
            GetTenantRuntimeReportQuery(TENANT_ID, start, end)
        )
    assert reader.request is None


@pytest.mark.asyncio
async def test_handler_rejects_missing_tenant_without_returning_empty_report() -> None:
    reader = ReportReaderStub(exists=False)
    with pytest.raises(TenantRuntimeReportNotFound):
        await GetTenantRuntimeReportHandler(reader)(
            GetTenantRuntimeReportQuery(TENANT_ID, START, START + timedelta(hours=1))
        )
    assert reader.request is None
