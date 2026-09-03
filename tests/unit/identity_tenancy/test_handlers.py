from datetime import UTC, datetime
from types import TracebackType
from typing import Self
from uuid import UUID

import pytest

from valor.identity_tenancy.application.create_tenant import (
    CreateTenantCommand,
    CreateTenantHandler,
)
from valor.identity_tenancy.application.errors import TenantNotFound
from valor.identity_tenancy.application.get_tenant import GetTenantHandler, GetTenantQuery
from valor.identity_tenancy.domain.tenant import Tenant, TenantId

TENANT_UUID = UUID("11111111-1111-4111-8111-111111111111")
CREATED_AT = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)


class InMemoryTenantRepository:
    def __init__(self) -> None:
        self.tenants: dict[TenantId, Tenant] = {}

    async def add(self, tenant: Tenant) -> None:
        self.tenants[tenant.id] = tenant

    async def get(self, tenant_id: TenantId) -> Tenant | None:
        return self.tenants.get(tenant_id)


class RecordingUnitOfWork:
    def __init__(self, tenants: InMemoryTenantRepository | None = None) -> None:
        self._tenants = tenants or InMemoryTenantRepository()
        self.commits = 0
        self.rollbacks = 0

    @property
    def tenants(self) -> InMemoryTenantRepository:
        return self._tenants

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.rollbacks += 1

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


@pytest.mark.asyncio
async def test_create_tenant_builds_aggregate_and_commits() -> None:
    unit_of_work = RecordingUnitOfWork()
    handler = CreateTenantHandler(
        unit_of_work,
        id_factory=lambda: TENANT_UUID,
        clock=lambda: CREATED_AT,
    )
    tenant = await handler(CreateTenantCommand(name=" Acme  Research "))
    assert tenant.id == TenantId(TENANT_UUID)
    assert tenant.name.value == "Acme Research"
    assert await unit_of_work.tenants.get(tenant.id) == tenant
    assert unit_of_work.commits == 1


@pytest.mark.asyncio
async def test_get_tenant_returns_existing_aggregate_without_commit() -> None:
    tenant = Tenant.create(TenantId(TENANT_UUID), "Acme", CREATED_AT)
    repository = InMemoryTenantRepository()
    await repository.add(tenant)
    unit_of_work = RecordingUnitOfWork(repository)
    result = await GetTenantHandler(unit_of_work)(GetTenantQuery(tenant.id))
    assert result == tenant
    assert unit_of_work.commits == 0


@pytest.mark.asyncio
async def test_get_tenant_raises_application_error_when_missing() -> None:
    tenant_id = TenantId(TENANT_UUID)
    with pytest.raises(TenantNotFound) as error:
        await GetTenantHandler(RecordingUnitOfWork())(GetTenantQuery(tenant_id))
    assert error.value.tenant_id == tenant_id
