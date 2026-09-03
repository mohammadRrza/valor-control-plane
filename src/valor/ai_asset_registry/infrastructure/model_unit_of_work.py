"""Model repository exposure on the existing SQLAlchemy Unit of Work."""

from valor.ai_asset_registry.domain.model_repository import ModelRepository
from valor.ai_asset_registry.infrastructure.model_repository import SqlAlchemyModelRepository
from valor.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork


class SqlAlchemyModelUnitOfWork(SqlAlchemyUnitOfWork):
    @property
    def models(self) -> ModelRepository:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return SqlAlchemyModelRepository(self.session)
