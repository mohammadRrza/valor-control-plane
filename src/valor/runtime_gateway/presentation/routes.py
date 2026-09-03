"""Versioned Runtime Gateway HTTP routes."""

from collections.abc import Callable
from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response, status

from valor.runtime_gateway.application.create_invocation import (
    CreateInvocationCommand,
    CreateInvocationHandler,
)
from valor.runtime_gateway.application.get_invocation import (
    GetInvocationHandler,
    GetInvocationQuery,
)
from valor.runtime_gateway.application.ports import (
    AgentRuntimeLookupPort,
    ModelProviderPort,
    ModelRuntimeLookupPort,
    TenantRuntimeLookupPort,
)
from valor.runtime_gateway.application.unit_of_work import InvocationUnitOfWork
from valor.runtime_gateway.domain.identity import AgentId, InvocationId, ModelId, TenantId
from valor.runtime_gateway.presentation.schemas import (
    CreateInvocationRequest,
    InvocationResponse,
)

InvocationUnitOfWorkFactory = Callable[[], InvocationUnitOfWork]


def invocation_unit_of_work(request: Request) -> InvocationUnitOfWork:
    factory = cast(
        InvocationUnitOfWorkFactory,
        request.app.state.invocation_unit_of_work_factory,
    )
    return factory()


def runtime_admission(
    request: Request,
) -> tuple[TenantRuntimeLookupPort, AgentRuntimeLookupPort, ModelRuntimeLookupPort]:
    adapter = request.app.state.runtime_admission
    return cast(
        tuple[TenantRuntimeLookupPort, AgentRuntimeLookupPort, ModelRuntimeLookupPort],
        (adapter, adapter, adapter),
    )


def runtime_provider(request: Request) -> ModelProviderPort:
    return cast(ModelProviderPort, request.app.state.runtime_provider)


router = APIRouter(prefix="/runtime/invocations", tags=["runtime"])


@router.post("", response_model=InvocationResponse, status_code=status.HTTP_201_CREATED)
async def create_invocation(
    payload: CreateInvocationRequest,
    response: Response,
    unit_of_work: Annotated[InvocationUnitOfWork, Depends(invocation_unit_of_work)],
    admission: Annotated[
        tuple[TenantRuntimeLookupPort, AgentRuntimeLookupPort, ModelRuntimeLookupPort],
        Depends(runtime_admission),
    ],
    provider: Annotated[ModelProviderPort, Depends(runtime_provider)],
) -> InvocationResponse:
    tenants, agents, models = admission
    invocation = await CreateInvocationHandler(unit_of_work, tenants, agents, models, provider)(
        CreateInvocationCommand(
            TenantId(payload.tenant_id),
            AgentId(payload.agent_id),
            ModelId(payload.model_id),
            payload.input,
        )
    )
    response.headers["Location"] = f"/api/v1/runtime/invocations/{invocation.id.value}"
    return InvocationResponse.from_domain(invocation)


@router.get("/{invocation_id}", response_model=InvocationResponse)
async def get_invocation(
    invocation_id: UUID,
    unit_of_work: Annotated[InvocationUnitOfWork, Depends(invocation_unit_of_work)],
) -> InvocationResponse:
    invocation = await GetInvocationHandler(unit_of_work)(
        GetInvocationQuery(InvocationId(invocation_id))
    )
    return InvocationResponse.from_domain(invocation)
