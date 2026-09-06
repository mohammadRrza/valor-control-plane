from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from valor.management_identity.application.errors import ManagementPrincipalNotFound


def utc_now() -> datetime:
    return datetime.now(UTC)


class CredentialInventoryState(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    PRINCIPAL_DISABLED = "principal_disabled"


@dataclass(frozen=True, slots=True)
class CredentialInventoryRecord:
    credential_id: UUID
    principal_id: UUID
    label: str | None
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None


@dataclass(frozen=True, slots=True)
class CredentialInventoryRead:
    principal_disabled: bool
    credentials: Sequence[CredentialInventoryRecord]


class ManagementCredentialInventoryReaderPort(Protocol):
    async def list_for_principal(
        self, *, principal_id: UUID, limit: int
    ) -> CredentialInventoryRead | None: ...


@dataclass(frozen=True, slots=True)
class CredentialInventoryItem:
    credential_id: UUID
    principal_id: UUID
    label: str | None
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None
    usable: bool
    state: CredentialInventoryState


@dataclass(frozen=True, slots=True)
class CredentialInventoryResult:
    items: tuple[CredentialInventoryItem, ...]
    truncated: bool


class ListManagementCredentialInventoryHandler:
    def __init__(
        self,
        reader: ManagementCredentialInventoryReaderPort,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._reader = reader
        self._clock = clock

    async def __call__(self, principal_id: UUID, limit: int = 50) -> CredentialInventoryResult:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        result = await self._reader.list_for_principal(principal_id=principal_id, limit=limit + 1)
        if result is None:
            raise ManagementPrincipalNotFound
        now = self._clock()
        records = tuple(result.credentials)
        return CredentialInventoryResult(
            tuple(
                _inventory_item(record, principal_disabled=result.principal_disabled, now=now)
                for record in records[:limit]
            ),
            truncated=len(records) > limit,
        )


def _inventory_item(
    record: CredentialInventoryRecord, *, principal_disabled: bool, now: datetime
) -> CredentialInventoryItem:
    if principal_disabled:
        state = CredentialInventoryState.PRINCIPAL_DISABLED
    elif record.revoked_at is not None:
        state = CredentialInventoryState.REVOKED
    elif record.expires_at is not None and now >= record.expires_at:
        state = CredentialInventoryState.EXPIRED
    else:
        state = CredentialInventoryState.ACTIVE
    return CredentialInventoryItem(
        record.credential_id,
        record.principal_id,
        record.label,
        record.created_at,
        record.expires_at,
        record.revoked_at,
        state is CredentialInventoryState.ACTIVE,
        state,
    )
