from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol
from uuid import UUID


def utc_now() -> datetime:
    return datetime.now(UTC)


class PrincipalInventoryState(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class PrincipalInventoryRecord:
    principal_id: UUID
    display_name: str
    can_manage_principals: bool
    created_at: datetime
    disabled_at: datetime | None
    tenant_scope_count: int
    credential_count: int
    usable_credential_count: int


class ManagementPrincipalInventoryReaderPort(Protocol):
    async def list_principals(
        self, *, now: datetime, limit: int
    ) -> Sequence[PrincipalInventoryRecord]: ...


@dataclass(frozen=True, slots=True)
class PrincipalInventoryItem:
    principal_id: UUID
    display_name: str
    created_at: datetime
    disabled_at: datetime | None
    state: PrincipalInventoryState
    can_manage_principals: bool
    tenant_scope_count: int
    credential_count: int
    usable_credential_count: int


@dataclass(frozen=True, slots=True)
class PrincipalInventoryResult:
    items: tuple[PrincipalInventoryItem, ...]
    truncated: bool


class ListManagementPrincipalInventoryHandler:
    def __init__(
        self,
        reader: ManagementPrincipalInventoryReaderPort,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._reader = reader
        self._clock = clock

    async def __call__(self, limit: int = 50) -> PrincipalInventoryResult:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        now = self._clock()
        records = tuple(await self._reader.list_principals(now=now, limit=limit + 1))
        return PrincipalInventoryResult(
            tuple(
                PrincipalInventoryItem(
                    record.principal_id,
                    record.display_name,
                    record.created_at,
                    record.disabled_at,
                    PrincipalInventoryState.DISABLED
                    if record.disabled_at is not None
                    else PrincipalInventoryState.ACTIVE,
                    record.can_manage_principals,
                    record.tenant_scope_count,
                    record.credential_count,
                    record.usable_credential_count,
                )
                for record in records[:limit]
            ),
            truncated=len(records) > limit,
        )
