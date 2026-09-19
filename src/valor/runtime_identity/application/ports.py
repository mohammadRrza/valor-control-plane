from dataclasses import dataclass
from datetime import datetime
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


@dataclass(frozen=True, slots=True)
class LegacyRuntimeConfiguration:
    principal_id: str
    tenant_id: UUID
    agent_id: UUID
    daily_usage_limit_units: int
    per_invocation_allowance_units: int


class LegacyRuntimeConfigurationPort(Protocol):
    def get(self, principal_id: str) -> LegacyRuntimeConfiguration | None: ...


@dataclass(frozen=True, slots=True)
class RuntimeInvocationContinuityFacts:
    historical_invocation_count: int
    same_day_attributed_usage_units: int
    legacy_binding_mismatch: bool
    canonical_binding_mismatch: bool


class RuntimeInvocationContinuityPort(Protocol):
    async def inspect(
        self,
        *,
        legacy_id: str,
        canonical_id: str,
        tenant_id: UUID,
        agent_id: UUID,
        day_start: datetime,
        day_end: datetime,
    ) -> RuntimeInvocationContinuityFacts: ...

    async def consumed_total_units(
        self, identity_ids: frozenset[str], day_start: datetime, day_end: datetime
    ) -> int: ...


class RuntimeIdentityUnitOfWork(UnitOfWork, Protocol):
    @property
    def principals(self) -> RuntimePrincipalRepository: ...
    @property
    def credentials(self) -> RuntimeCredentialRepository: ...
    @property
    def bindings(self) -> RuntimeBindingPort: ...
    @property
    def invocations(self) -> RuntimeInvocationContinuityPort: ...
    @property
    def audits(self) -> ManagementAuditRepository: ...


class RuntimeIdentityUnitOfWorkFactory(Protocol):
    def __call__(self) -> RuntimeIdentityUnitOfWork: ...
