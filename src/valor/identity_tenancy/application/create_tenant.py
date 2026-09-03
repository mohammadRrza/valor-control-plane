"""CreateTenant command and handler."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from valor.identity_tenancy.application.unit_of_work import TenantUnitOfWork
from valor.identity_tenancy.domain.tenant import Tenant, TenantId


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class CreateTenantCommand:
    name: str


class CreateTenantHandler:
    def __init__(
        self,
        unit_of_work: TenantUnitOfWork,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._unit_of_work = unit_of_work
        self._id_factory = id_factory
        self._clock = clock

    async def __call__(self, command: CreateTenantCommand) -> Tenant:
        tenant = Tenant.create(
            tenant_id=TenantId(self._id_factory()),
            name=command.name,
            created_at=self._clock(),
        )
        async with self._unit_of_work as unit_of_work:
            await unit_of_work.tenants.add(tenant)
            await unit_of_work.commit()
        return tenant
