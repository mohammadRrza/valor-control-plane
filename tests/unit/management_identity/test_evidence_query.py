from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest

from valor.management_identity.application.evidence_query import (
    InvalidAuthenticationEvidenceQuery,
    ListManagementAuthenticationEvidenceHandler,
    ListManagementAuthenticationEvidenceQuery,
)

NOW = datetime(2026, 9, 6, 12, tzinfo=UTC)
CREDENTIAL_ID = UUID("11111111-1111-4111-8111-111111111111")
PRINCIPAL_ID = UUID("22222222-2222-4222-8222-222222222222")


class Reader:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    async def list_evidence(self, **values: object) -> tuple[()]:
        self.calls.append(values)
        return ()


@pytest.mark.asyncio
async def test_query_requires_one_filter_and_normalizes_range_to_utc() -> None:
    reader = Reader()
    query = ListManagementAuthenticationEvidenceQuery(
        CREDENTIAL_ID,
        None,
        NOW.astimezone(timezone(timedelta(hours=2))),
        (NOW + timedelta(hours=1)).astimezone(timezone(timedelta(hours=2))),
        25,
    )
    assert await ListManagementAuthenticationEvidenceHandler(reader)(query) == ()
    assert reader.calls == [
        {
            "credential_id": CREDENTIAL_ID,
            "principal_id": None,
            "start": NOW,
            "end": NOW + timedelta(hours=1),
            "limit": 25,
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("credential_id", "principal_id", "start", "end", "limit"),
    [
        (None, None, NOW, NOW + timedelta(hours=1), 50),
        (CREDENTIAL_ID, PRINCIPAL_ID, NOW, NOW + timedelta(hours=1), 50),
        (CREDENTIAL_ID, None, NOW.replace(tzinfo=None), NOW + timedelta(hours=1), 50),
        (CREDENTIAL_ID, None, NOW, NOW + timedelta(days=32), 50),
        (CREDENTIAL_ID, None, NOW, NOW, 50),
        (CREDENTIAL_ID, None, NOW, NOW + timedelta(hours=1), 0),
        (CREDENTIAL_ID, None, NOW, NOW + timedelta(hours=1), 101),
    ],
)
async def test_invalid_queries_fail_before_read(
    credential_id: UUID | None,
    principal_id: UUID | None,
    start: datetime,
    end: datetime,
    limit: int,
) -> None:
    reader = Reader()
    with pytest.raises(InvalidAuthenticationEvidenceQuery):
        await ListManagementAuthenticationEvidenceHandler(reader)(
            ListManagementAuthenticationEvidenceQuery(
                credential_id, principal_id, start, end, limit
            )
        )
    assert reader.calls == []
