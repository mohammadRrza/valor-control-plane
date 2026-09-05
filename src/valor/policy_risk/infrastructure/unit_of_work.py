from valor.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork
from valor.management_audit.domain.repositories import ManagementAuditRepository
from valor.management_audit.infrastructure.repositories import SqlAlchemyManagementAuditRepository
from valor.policy_risk.domain.repositories import (
    AgentModelPermissionRepository,
    PolicyDecisionRepository,
)
from valor.policy_risk.infrastructure.repositories import (
    SqlAlchemyAgentModelPermissionRepository,
    SqlAlchemyPolicyDecisionRepository,
)


class SqlAlchemyPolicyUnitOfWork(SqlAlchemyUnitOfWork):
    @property
    def permissions(self) -> AgentModelPermissionRepository:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return SqlAlchemyAgentModelPermissionRepository(self.session)

    @property
    def decisions(self) -> PolicyDecisionRepository:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return SqlAlchemyPolicyDecisionRepository(self.session)

    @property
    def audits(self) -> ManagementAuditRepository:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return SqlAlchemyManagementAuditRepository(self.session)
