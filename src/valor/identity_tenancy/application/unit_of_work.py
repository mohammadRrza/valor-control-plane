"""Tenant-capable Unit of Work application port."""

from typing import Protocol

from valor.application.unit_of_work import UnitOfWork
from valor.identity_tenancy.domain.repository import TenantRepository


class TenantUnitOfWork(UnitOfWork, Protocol):
    @property
    def tenants(self) -> TenantRepository: ...
