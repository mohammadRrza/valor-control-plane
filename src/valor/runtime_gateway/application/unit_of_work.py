"""Invocation-capable Unit of Work application port."""

from typing import Protocol

from valor.application.unit_of_work import UnitOfWork
from valor.runtime_gateway.domain.repository import InvocationRepository


class InvocationUnitOfWork(UnitOfWork, Protocol):
    @property
    def invocations(self) -> InvocationRepository: ...
