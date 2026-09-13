from typing import Protocol
from uuid import UUID

from valor.application.unit_of_work import UnitOfWork
from valor.management_audit.domain.repositories import ManagementAuditRepository
from valor.runtime_identity.domain.repositories import (
    RuntimeCredentialRepository,
    RuntimePrincipalRepository,
)


class RuntimeBindingPort(Protocol):
    async def exists(self, tenant_id: UUID, agent_id: UUID) -> bool: ...


class RuntimeIdentityUnitOfWork(UnitOfWork, Protocol):
    @property
    def principals(self) -> RuntimePrincipalRepository: ...
    @property
    def credentials(self) -> RuntimeCredentialRepository: ...
    @property
    def bindings(self) -> RuntimeBindingPort: ...
    @property
    def audits(self) -> ManagementAuditRepository: ...


class RuntimeIdentityUnitOfWorkFactory(Protocol):
    def __call__(self) -> RuntimeIdentityUnitOfWork: ...
