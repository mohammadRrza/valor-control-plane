"""Agent repository exposure on the existing SQLAlchemy Unit of Work."""

from valor.ai_asset_registry.domain.repository import AgentRepository
from valor.ai_asset_registry.infrastructure.repository import SqlAlchemyAgentRepository
from valor.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork


class SqlAlchemyAgentUnitOfWork(SqlAlchemyUnitOfWork):
    @property
    def agents(self) -> AgentRepository:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return SqlAlchemyAgentRepository(self.session)
