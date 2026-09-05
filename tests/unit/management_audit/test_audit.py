from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from valor.management_audit.application.query import (
    InvalidAuditRange,
    ListManagementAuditRecordsHandler,
    ListManagementAuditRecordsQuery,
)
from valor.management_audit.domain.fingerprints import agent_model_permission_fingerprint

TENANT = UUID("11111111-1111-4111-8111-111111111111")
AGENT = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
MODEL = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")


def test_permission_fingerprint_is_canonical_and_lowercase_sha256() -> None:
    first = agent_model_permission_fingerprint(
        tenant_id=TENANT, agent_id=AGENT, model_id=MODEL, effect=" allow "
    )
    second = agent_model_permission_fingerprint(
        model_id=MODEL, effect="ALLOW", agent_id=AGENT, tenant_id=TENANT
    )
    assert first == second
    assert len(first) == 64
    assert first == first.lower()


class Reader:
    def __init__(self) -> None:
        self.request: tuple[UUID, datetime, datetime, int] | None = None

    async def tenant_exists(self, tenant_id: UUID) -> bool:
        return tenant_id == TENANT

    async def list_for_tenant(
        self, *, tenant_id: UUID, start: datetime, end: datetime, limit: int
    ) -> tuple[()]:
        self.request = (tenant_id, start, end, limit)
        return ()


@pytest.mark.asyncio
async def test_query_normalizes_aware_range_to_utc() -> None:
    reader = Reader()
    start = datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=2)))
    end = start + timedelta(days=1)
    assert (
        await ListManagementAuditRecordsHandler(reader)(
            ListManagementAuditRecordsQuery(TENANT, start, end)
        )
        == ()
    )
    assert reader.request == (
        TENANT,
        start.astimezone(UTC),
        end.astimezone(UTC),
        50,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("start", "end"),
    [
        (datetime(2026, 1, 1), datetime(2026, 1, 2, tzinfo=UTC)),
        (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 1, tzinfo=UTC)),
        (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 2, 2, tzinfo=UTC)),
    ],
)
async def test_query_rejects_invalid_ranges(start: datetime, end: datetime) -> None:
    with pytest.raises(InvalidAuditRange):
        await ListManagementAuditRecordsHandler(Reader())(
            ListManagementAuditRecordsQuery(TENANT, start, end)
        )
