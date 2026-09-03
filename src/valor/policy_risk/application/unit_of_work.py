from typing import Protocol

from valor.application.unit_of_work import UnitOfWork
from valor.policy_risk.domain.repositories import (
    AgentModelPermissionRepository,
    PolicyDecisionRepository,
)


class PolicyUnitOfWork(UnitOfWork, Protocol):
    @property
    def permissions(self) -> AgentModelPermissionRepository: ...

    @property
    def decisions(self) -> PolicyDecisionRepository: ...
