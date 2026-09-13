from valor.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork
from valor.management_audit.domain.repositories import ManagementAuditRepository
from valor.management_audit.infrastructure.repositories import SqlAlchemyManagementAuditRepository
from valor.runtime_identity.application.ports import RuntimeBindingPort
from valor.runtime_identity.domain.repositories import (
    RuntimeCredentialRepository,
    RuntimePrincipalRepository,
)
from valor.runtime_identity.infrastructure.repositories import (
    SqlAlchemyRuntimeBinding,
    SqlAlchemyRuntimeCredentialRepository,
    SqlAlchemyRuntimePrincipalRepository,
)


class SqlAlchemyRuntimeIdentityUnitOfWork(SqlAlchemyUnitOfWork):
    @property
    def principals(self) -> RuntimePrincipalRepository:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return SqlAlchemyRuntimePrincipalRepository(self.session)

    @property
    def credentials(self) -> RuntimeCredentialRepository:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return SqlAlchemyRuntimeCredentialRepository(self.session)

    @property
    def bindings(self) -> RuntimeBindingPort:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return SqlAlchemyRuntimeBinding(self.session)

    @property
    def audits(self) -> ManagementAuditRepository:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return SqlAlchemyManagementAuditRepository(self.session)
