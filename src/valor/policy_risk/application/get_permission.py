from dataclasses import dataclass

from valor.policy_risk.application.errors import PermissionNotFound
from valor.policy_risk.application.unit_of_work import PolicyUnitOfWork
from valor.policy_risk.domain.identity import PermissionId
from valor.policy_risk.domain.policy import AgentModelPermission


@dataclass(frozen=True, slots=True)
class GetAgentModelPermissionQuery:
    permission_id: PermissionId


class GetAgentModelPermissionHandler:
    def __init__(self, unit_of_work: PolicyUnitOfWork) -> None:
        self._uow = unit_of_work

    async def __call__(self, query: GetAgentModelPermissionQuery) -> AgentModelPermission:
        async with self._uow as uow:
            permission = await uow.permissions.get(query.permission_id)
        if permission is None:
            raise PermissionNotFound(query.permission_id)
        return permission
