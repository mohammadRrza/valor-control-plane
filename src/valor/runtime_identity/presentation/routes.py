from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from valor.runtime_identity.application.handlers import (
    CreateRuntimePrincipalCommand,
    InitializeRuntimeUsageLimitsCommand,
    IssueRuntimeCredentialCommand,
    RuntimeCredentialCommand,
    RuntimeIdentityActor,
    RuntimeIdentityService,
)
from valor.runtime_identity.presentation.schemas import (
    CreateRuntimePrincipalRequest,
    CreateRuntimePrincipalResponse,
    CredentialRequest,
    IssuedRuntimeCredentialResponse,
    RuntimeCredentialResponse,
    RuntimePrincipalResponse,
    RuntimeUsageLimitsRequest,
)
from valor.security.application.principal import AuthenticatedPrincipal
from valor.security.presentation.authentication import require_management_principal

router = APIRouter(prefix="/management/runtime-principals", tags=["runtime-identity"])


def service(request: Request) -> RuntimeIdentityService:
    return cast(RuntimeIdentityService, request.app.state.runtime_identity_service)


def actor(value: AuthenticatedPrincipal) -> RuntimeIdentityActor:
    return RuntimeIdentityActor(value.principal_id, value.can_manage_principals)


@router.post("", response_model=CreateRuntimePrincipalResponse, status_code=status.HTTP_201_CREATED)
async def create(
    payload: CreateRuntimePrincipalRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
    identity: Annotated[RuntimeIdentityService, Depends(service)],
) -> CreateRuntimePrincipalResponse:
    runtime_principal, issued = await identity.create_principal(
        CreateRuntimePrincipalCommand(
            actor(principal),
            payload.tenant_id,
            payload.agent_id,
            payload.daily_usage_limit_units,
            payload.per_invocation_allowance_units,
            payload.credential.label,
            payload.credential.expires_at,
        )
    )
    return CreateRuntimePrincipalResponse(
        principal=RuntimePrincipalResponse.from_domain(runtime_principal, cutover_ready=True),
        credential=IssuedRuntimeCredentialResponse.from_issued(issued),
    )


@router.get("/{principal_id}", response_model=RuntimePrincipalResponse)
async def get(
    principal_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
    identity: Annotated[RuntimeIdentityService, Depends(service)],
) -> RuntimePrincipalResponse:
    return RuntimePrincipalResponse.from_details(
        await identity.get_principal(actor(principal), principal_id)
    )


@router.put("/{principal_id}/usage-limits", response_model=RuntimePrincipalResponse)
async def initialize_usage_limits(
    principal_id: UUID,
    payload: RuntimeUsageLimitsRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
    identity: Annotated[RuntimeIdentityService, Depends(service)],
) -> RuntimePrincipalResponse:
    await identity.initialize_usage_limits(
        InitializeRuntimeUsageLimitsCommand(
            actor(principal),
            principal_id,
            payload.daily_usage_limit_units,
            payload.per_invocation_allowance_units,
        )
    )
    return RuntimePrincipalResponse.from_details(
        await identity.get_principal(actor(principal), principal_id)
    )


@router.post(
    "/{principal_id}/credentials",
    response_model=IssuedRuntimeCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def issue(
    principal_id: UUID,
    payload: CredentialRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
    identity: Annotated[RuntimeIdentityService, Depends(service)],
) -> IssuedRuntimeCredentialResponse:
    return IssuedRuntimeCredentialResponse.from_issued(
        await identity.issue_credential(
            IssueRuntimeCredentialCommand(
                actor(principal), principal_id, payload.label, payload.expires_at
            )
        )
    )


@router.post(
    "/{principal_id}/credentials/{credential_id}/revoke", response_model=RuntimeCredentialResponse
)
async def revoke(
    principal_id: UUID,
    credential_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
    identity: Annotated[RuntimeIdentityService, Depends(service)],
) -> RuntimeCredentialResponse:
    return RuntimeCredentialResponse.from_domain(
        await identity.revoke_credential(
            RuntimeCredentialCommand(actor(principal), principal_id, credential_id)
        )
    )


@router.post("/{principal_id}/disable", response_model=RuntimePrincipalResponse)
async def disable(
    principal_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
    identity: Annotated[RuntimeIdentityService, Depends(service)],
) -> RuntimePrincipalResponse:
    return RuntimePrincipalResponse.from_domain(
        await identity.disable_principal(actor(principal), principal_id), cutover_ready=False
    )
