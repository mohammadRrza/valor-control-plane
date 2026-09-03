"""Versioned Agent HTTP routes."""

from collections.abc import Callable
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from valor.ai_asset_registry.application.errors import AgentNotFound, OwningTenantNotFound
from valor.ai_asset_registry.application.get_agent import GetAgentHandler, GetAgentQuery
from valor.ai_asset_registry.application.ports import TenantExistencePort
from valor.ai_asset_registry.application.register_agent import (
    RegisterAgentCommand,
    RegisterAgentHandler,
)
from valor.ai_asset_registry.application.unit_of_work import AgentUnitOfWork
from valor.ai_asset_registry.domain.agent import AgentId
from valor.ai_asset_registry.domain.ownership import OwningTenantId
from valor.ai_asset_registry.presentation.dependencies import tenant_existence
from valor.ai_asset_registry.presentation.schemas import AgentResponse, RegisterAgentRequest
from valor.security.application.authorization import authorize_tenant
from valor.security.application.errors import TenantManagementAccessDenied
from valor.security.application.principal import AuthenticatedPrincipal
from valor.security.presentation.authentication import require_management_principal

AgentUnitOfWorkFactory = Callable[[], AgentUnitOfWork]


def agent_unit_of_work(request: Request) -> AgentUnitOfWork:
    factory = cast(AgentUnitOfWorkFactory, request.app.state.agent_unit_of_work_factory)
    return factory()


router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
async def register_agent(
    payload: RegisterAgentRequest,
    response: Response,
    unit_of_work: Annotated[AgentUnitOfWork, Depends(agent_unit_of_work)],
    owning_tenant: Annotated[TenantExistencePort, Depends(tenant_existence)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
) -> AgentResponse:
    try:
        authorize_tenant(principal, payload.tenant_id)
    except TenantManagementAccessDenied as exc:
        raise OwningTenantNotFound(OwningTenantId(payload.tenant_id)) from exc
    command = RegisterAgentCommand(
        tenant_id=OwningTenantId(payload.tenant_id),
        name=payload.name,
    )
    agent = await RegisterAgentHandler(unit_of_work, owning_tenant)(command)
    response.headers["Location"] = f"/api/v1/agents/{agent.id.value}"
    return AgentResponse.from_domain(agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    unit_of_work: Annotated[AgentUnitOfWork, Depends(agent_unit_of_work)],
    principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
) -> AgentResponse:
    agent = await GetAgentHandler(unit_of_work)(GetAgentQuery(AgentId(agent_id)))
    try:
        authorize_tenant(principal, agent.tenant_id.value)
    except TenantManagementAccessDenied as exc:
        raise AgentNotFound(AgentId(agent_id)) from exc
    return AgentResponse.from_domain(agent)
