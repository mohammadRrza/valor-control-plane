"""Shared SQLAlchemy mapping registry for infrastructure adapters."""

from sqlalchemy.orm import DeclarativeBase


class SqlAlchemyBase(DeclarativeBase):
    pass
