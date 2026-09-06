from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from valor.management_identity.application.credential_inventory import (
    CredentialInventoryRead,
    CredentialInventoryRecord,
    CredentialInventoryState,
    ListManagementCredentialInventoryHandler,
)
from valor.management_identity.application.errors import ManagementPrincipalNotFound

NOW = datetime(2026, 9, 6, 12, tzinfo=UTC)
PRINCIPAL_ID = UUID("22222222-2222-4222-8222-222222222222")


class Reader:
    def __init__(self, result: CredentialInventoryRead | None) -> None:
        self.result = result
        self.calls: list[tuple[UUID, int]] = []

    async def list_for_principal(
        self, *, principal_id: UUID, limit: int
    ) -> CredentialInventoryRead | None:
        self.calls.append((principal_id, limit))
        return self.result


def record(
    value: int,
    *,
    expires_at: datetime | None = None,
    revoked_at: datetime | None = None,
) -> CredentialInventoryRecord:
    return CredentialInventoryRecord(
        UUID(f"00000000-0000-4000-8000-{value:012d}"),
        PRINCIPAL_ID,
        f"credential-{value}",
        NOW - timedelta(days=value),
        expires_at,
        revoked_at,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("disabled", "expires_at", "revoked_at", "state", "usable"),
    [
        (False, None, None, CredentialInventoryState.ACTIVE, True),
        (False, NOW + timedelta(seconds=1), None, CredentialInventoryState.ACTIVE, True),
        (False, NOW, None, CredentialInventoryState.EXPIRED, False),
        (False, NOW - timedelta(seconds=1), None, CredentialInventoryState.EXPIRED, False),
        (False, None, NOW, CredentialInventoryState.REVOKED, False),
        (True, NOW - timedelta(days=1), NOW, CredentialInventoryState.PRINCIPAL_DISABLED, False),
    ],
)
async def test_inventory_derives_deterministic_state(
    disabled: bool,
    expires_at: datetime | None,
    revoked_at: datetime | None,
    state: CredentialInventoryState,
    usable: bool,
) -> None:
    reader = Reader(
        CredentialInventoryRead(
            disabled, (record(1, expires_at=expires_at, revoked_at=revoked_at),)
        )
    )
    result = await ListManagementCredentialInventoryHandler(reader, clock=lambda: NOW)(
        PRINCIPAL_ID, 50
    )
    assert result.items[0].state is state
    assert result.items[0].usable is usable
    assert reader.calls == [(PRINCIPAL_ID, 51)]


@pytest.mark.asyncio
async def test_inventory_truncates_and_validates_limit() -> None:
    reader = Reader(CredentialInventoryRead(False, (record(1), record(2))))
    result = await ListManagementCredentialInventoryHandler(reader, clock=lambda: NOW)(
        PRINCIPAL_ID, 1
    )
    assert len(result.items) == 1
    assert result.truncated is True
    with pytest.raises(ValueError):
        await ListManagementCredentialInventoryHandler(reader)(PRINCIPAL_ID, 101)


@pytest.mark.asyncio
async def test_unknown_principal_is_not_found() -> None:
    with pytest.raises(ManagementPrincipalNotFound):
        await ListManagementCredentialInventoryHandler(Reader(None))(PRINCIPAL_ID)
