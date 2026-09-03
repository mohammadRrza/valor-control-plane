"""SQLAlchemy Tenant repository adapter."""

from psycopg.errors import UniqueViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from valor.identity_tenancy.application.errors import TenantNameAlreadyExists
from valor.identity_tenancy.domain.tenant import Tenant, TenantId, TenantName
from valor.identity_tenancy.infrastructure.models import TenantRow

TENANT_NAME_UNIQUE_CONSTRAINT = "uq_tenants_normalized_name"


class SqlAlchemyTenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, tenant: Tenant) -> None:
        self._session.add(
            TenantRow(
                id=tenant.id.value,
                name=tenant.name.value,
                normalized_name=tenant.name.normalized,
                created_at=tenant.created_at,
            )
        )
        try:
            await self._session.flush()
        except IntegrityError as error:
            if (
                isinstance(error.orig, UniqueViolation)
                and error.orig.diag.constraint_name == TENANT_NAME_UNIQUE_CONSTRAINT
            ):
                raise TenantNameAlreadyExists from error
            raise

    async def get(self, tenant_id: TenantId) -> Tenant | None:
        row = await self._session.scalar(select(TenantRow).where(TenantRow.id == tenant_id.value))
        if row is None:
            return None
        return Tenant(
            id=TenantId(row.id),
            name=TenantName(row.name),
            created_at=row.created_at,
        )
