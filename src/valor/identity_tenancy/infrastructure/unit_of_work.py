"""Tenant repository exposure on the existing SQLAlchemy Unit of Work."""

from valor.identity_tenancy.domain.repository import TenantRepository
from valor.identity_tenancy.infrastructure.repository import SqlAlchemyTenantRepository
from valor.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork


class SqlAlchemyTenantUnitOfWork(SqlAlchemyUnitOfWork):
    @property
    def tenants(self) -> TenantRepository:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return SqlAlchemyTenantRepository(self.session)
