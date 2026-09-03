"""Tenant HTTP request and response contracts."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from valor.identity_tenancy.domain.tenant import MAX_TENANT_NAME_LENGTH, Tenant


class CreateTenantRequest(BaseModel):
    name: str = Field(min_length=1, max_length=MAX_TENANT_NAME_LENGTH)


class TenantResponse(BaseModel):
    id: UUID
    name: str
    created_at: datetime

    @classmethod
    def from_domain(cls, tenant: Tenant) -> "TenantResponse":
        return cls(
            id=tenant.id.value,
            name=tenant.name.value,
            created_at=tenant.created_at,
        )
