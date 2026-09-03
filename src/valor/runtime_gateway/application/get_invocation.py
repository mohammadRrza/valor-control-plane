"""GetInvocation query orchestration."""

from dataclasses import dataclass

from valor.runtime_gateway.application.errors import InvocationNotFound
from valor.runtime_gateway.application.unit_of_work import InvocationUnitOfWork
from valor.runtime_gateway.domain.identity import InvocationId
from valor.runtime_gateway.domain.invocation import Invocation


@dataclass(frozen=True, slots=True)
class GetInvocationQuery:
    invocation_id: InvocationId


class GetInvocationHandler:
    def __init__(self, unit_of_work: InvocationUnitOfWork) -> None:
        self._unit_of_work = unit_of_work

    async def __call__(self, query: GetInvocationQuery) -> Invocation:
        async with self._unit_of_work as unit_of_work:
            invocation = await unit_of_work.invocations.get(query.invocation_id)
        if invocation is None:
            raise InvocationNotFound(query.invocation_id)
        return invocation
