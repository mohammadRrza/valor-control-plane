from sqlalchemy import text

from valor.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork
from valor.management_audit.domain.repositories import ManagementAuditRepository
from valor.management_audit.infrastructure.repositories import SqlAlchemyManagementAuditRepository
from valor.management_identity.application.ports import TenantExistencePort
from valor.management_identity.domain.repositories import (
    ManagementAuthenticationEvidenceRepository,
    ManagementCredentialRepository,
    ManagementPrincipalRepository,
)
from valor.management_identity.infrastructure.repositories import (
    SqlAlchemyManagementAuthenticationEvidenceRepository,
    SqlAlchemyManagementCredentialRepository,
    SqlAlchemyManagementPrincipalRepository,
    SqlAlchemyTenantExistence,
)


class SqlAlchemyManagementIdentityUnitOfWork(SqlAlchemyUnitOfWork):
    @property
    def authentication_evidence(self) -> ManagementAuthenticationEvidenceRepository:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return SqlAlchemyManagementAuthenticationEvidenceRepository(self.session)

    @property
    def principals(self) -> ManagementPrincipalRepository:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return SqlAlchemyManagementPrincipalRepository(self.session)

    @property
    def credentials(self) -> ManagementCredentialRepository:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return SqlAlchemyManagementCredentialRepository(self.session)

    @property
    def tenants(self) -> TenantExistencePort:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return SqlAlchemyTenantExistence(self.session)

    @property
    def audits(self) -> ManagementAuditRepository:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return SqlAlchemyManagementAuditRepository(self.session)

    async def lock_management_state(self) -> None:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        await self.session.execute(text("SELECT pg_advisory_xact_lock(1447906382)"))
