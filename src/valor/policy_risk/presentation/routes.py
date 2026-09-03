from collections.abc import Callable
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request

from valor.policy_risk.application.get_permission import (
    GetAgentModelPermissionHandler,
    GetAgentModelPermissionQuery,
)
from valor.policy_risk.application.ports import (
    PolicyAgentLookupPort,
    PolicyModelLookupPort,
    PolicyTenantLookupPort,
)
from valor.policy_risk.application.set_permission import (
    SetAgentModelPermissionCommand,
    SetAgentModelPermissionHandler,
)
from valor.policy_risk.application.unit_of_work import PolicyUnitOfWork
from valor.policy_risk.domain.identity import AgentId, ModelId, PermissionId, TenantId
from valor.policy_risk.presentation.schemas import (
    AgentModelPermissionResponse,
    SetAgentModelPermissionRequest,
)

PolicyUnitOfWorkFactory = Callable[[], PolicyUnitOfWork]


def policy_uow(request: Request) -> PolicyUnitOfWork:
    return cast(PolicyUnitOfWorkFactory, request.app.state.policy_uow_factory)()


def policy_admission(
    request: Request,
) -> tuple[PolicyTenantLookupPort, PolicyAgentLookupPort, PolicyModelLookupPort]:
    adapter = request.app.state.policy_admission
    return cast(
        tuple[PolicyTenantLookupPort, PolicyAgentLookupPort, PolicyModelLookupPort],
        (adapter, adapter, adapter),
    )


router = APIRouter(prefix="/policies/agent-model-permissions", tags=["policies"])


@router.put("", response_model=AgentModelPermissionResponse)
async def set_permission(
    payload: SetAgentModelPermissionRequest,
    uow: Annotated[PolicyUnitOfWork, Depends(policy_uow)],
    admission: Annotated[
        tuple[PolicyTenantLookupPort, PolicyAgentLookupPort, PolicyModelLookupPort],
        Depends(policy_admission),
    ],
) -> AgentModelPermissionResponse:
    tenants, agents, models = admission
    permission = await SetAgentModelPermissionHandler(uow, tenants, agents, models)(
        SetAgentModelPermissionCommand(
            TenantId(payload.tenant_id),
            AgentId(payload.agent_id),
            ModelId(payload.model_id),
            payload.effect,
        )
    )
    return AgentModelPermissionResponse.from_domain(permission)


@router.get("/{permission_id}", response_model=AgentModelPermissionResponse)
async def get_permission(
    permission_id: UUID,
    uow: Annotated[PolicyUnitOfWork, Depends(policy_uow)],
) -> AgentModelPermissionResponse:
    permission = await GetAgentModelPermissionHandler(uow)(
        GetAgentModelPermissionQuery(PermissionId(permission_id))
    )
    return AgentModelPermissionResponse.from_domain(permission)
