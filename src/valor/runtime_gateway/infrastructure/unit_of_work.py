"""Invocation repository exposure on the SQLAlchemy Unit of Work."""

from valor.infrastructure.sqlalchemy_uow import SqlAlchemyUnitOfWork
from valor.runtime_gateway.domain.repository import InvocationRepository
from valor.runtime_gateway.infrastructure.repository import SqlAlchemyInvocationRepository


class SqlAlchemyInvocationUnitOfWork(SqlAlchemyUnitOfWork):
    @property
    def invocations(self) -> InvocationRepository:
        if self.session is None:
            raise RuntimeError("Unit of Work has not been entered")
        return SqlAlchemyInvocationRepository(self.session)
