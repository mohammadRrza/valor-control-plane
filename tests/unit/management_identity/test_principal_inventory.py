from datetime import UTC, datetime
from uuid import UUID

import pytest

from valor.management_identity.application.principal_inventory import (
    ListManagementPrincipalInventoryHandler,
    PrincipalInventoryRecord,
    PrincipalInventoryState,
)

NOW = datetime(2026, 9, 7, 12, tzinfo=UTC)


class Reader:
    def __init__(self, records: tuple[PrincipalInventoryRecord, ...]) -> None:
        self.records = records
        self.calls: list[tuple[datetime, int]] = []

    async def list_principals(
        self, *, now: datetime, limit: int
    ) -> tuple[PrincipalInventoryRecord, ...]:
        self.calls.append((now, limit))
        return self.records


def record(value: int, *, disabled: bool = False) -> PrincipalInventoryRecord:
    return PrincipalInventoryRecord(
        UUID(f"00000000-0000-4000-8000-{value:012d}"),
        f"Principal {value}",
        value == 1,
        NOW,
        NOW if disabled else None,
        value,
        value + 1,
        0 if disabled else value,
    )


@pytest.mark.asyncio
async def test_inventory_derives_states_and_captures_one_time() -> None:
    calls = 0

    def clock() -> datetime:
        nonlocal calls
        calls += 1
        return NOW

    reader = Reader((record(1), record(2, disabled=True)))
    result = await ListManagementPrincipalInventoryHandler(reader, clock=clock)(50)
    assert [item.state for item in result.items] == [
        PrincipalInventoryState.ACTIVE,
        PrincipalInventoryState.DISABLED,
    ]
    assert result.items[0].tenant_scope_count == 1
    assert result.items[0].credential_count == 2
    assert result.items[1].usable_credential_count == 0
    assert calls == 1
    assert reader.calls == [(NOW, 51)]


@pytest.mark.asyncio
async def test_inventory_is_bounded_and_reports_truncation() -> None:
    reader = Reader((record(1), record(2)))
    result = await ListManagementPrincipalInventoryHandler(reader, clock=lambda: NOW)(1)
    assert len(result.items) == 1
    assert result.truncated is True
    assert reader.calls == [(NOW, 2)]


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, 101])
async def test_inventory_rejects_invalid_limit(limit: int) -> None:
    reader = Reader(())
    with pytest.raises(ValueError):
        await ListManagementPrincipalInventoryHandler(reader)(limit)
    assert reader.calls == []
