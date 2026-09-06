from typing import Protocol
from uuid import UUID

from valor.application.unit_of_work import UnitOfWork
from valor.management_audit.domain.repositories import ManagementAuditRepository
from valor.management_identity.domain.repositories import (
    ManagementCredentialRepository,
    ManagementPrincipalRepository,
)


class TenantExistencePort(Protocol):
    async def all_exist(self, tenant_ids: frozenset[UUID]) -> bool: ...


class ManagementIdentityUnitOfWork(UnitOfWork, Protocol):
    @property
    def principals(self) -> ManagementPrincipalRepository: ...
    @property
    def credentials(self) -> ManagementCredentialRepository: ...
    @property
    def tenants(self) -> TenantExistencePort: ...
    @property
    def audits(self) -> ManagementAuditRepository: ...
    async def lock_management_state(self) -> None: ...


class ManagementIdentityUnitOfWorkFactory(Protocol):
    def __call__(self) -> ManagementIdentityUnitOfWork: ...
