from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from fastapi.security import HTTPAuthorizationCredentials

from valor.management_identity.application.errors import BootstrapAuthenticationFailed
from valor.management_identity.application.handlers import (
    BootstrapCommand,
    CreatePrincipalCommand,
    DisablePrincipalCommand,
    IssueCredentialCommand,
    ManagementActor,
    ManagementIdentityService,
    RevokeCredentialCommand,
    SetScopesCommand,
)
from valor.management_identity.presentation.schemas import (
    BootstrapRequest,
    BootstrapResponse,
    CreatePrincipalRequest,
    CredentialMetadataResponse,
    IssueCredentialRequest,
    IssuedCredentialResponse,
    PrincipalResponse,
    SetTenantScopesRequest,
)
from valor.security.application.principal import AuthenticatedPrincipal
from valor.security.presentation.authentication import bearer, require_management_principal

router = APIRouter(prefix="/management", tags=["management-identity"])


def identity_service(request: Request) -> ManagementIdentityService:
    return cast(ManagementIdentityService, request.app.state.management_identity_service)


def actor(principal: AuthenticatedPrincipal) -> ManagementActor:
    return ManagementActor(principal.principal_id, principal.can_manage_principals)


@router.post("/bootstrap", response_model=BootstrapResponse, status_code=status.HTTP_201_CREATED)
async def bootstrap(
    payload: BootstrapRequest,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    service: Annotated[ManagementIdentityService, Depends(identity_service)],
) -> BootstrapResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise BootstrapAuthenticationFailed
    principal, issued = await service.bootstrap(
        BootstrapCommand(credentials.credentials, payload.display_name, payload.tenant_ids)
    )
    return BootstrapResponse(
        principal=PrincipalResponse.from_domain(principal),
        credential=IssuedCredentialResponse.from_issued(issued),
    )


@router.post("/principals", response_model=PrincipalResponse, status_code=status.HTTP_201_CREATED)
async def create_principal(
    payload: CreatePrincipalRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
    service: Annotated[ManagementIdentityService, Depends(identity_service)],
) -> PrincipalResponse:
    result = await service.create_principal(
        CreatePrincipalCommand(
            actor(principal),
            payload.display_name,
            payload.tenant_ids,
            payload.can_manage_principals,
        )
    )
    return PrincipalResponse.from_domain(result)


@router.get("/principals/{principal_id}", response_model=PrincipalResponse)
async def get_principal(
    principal_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
    service: Annotated[ManagementIdentityService, Depends(identity_service)],
) -> PrincipalResponse:
    return PrincipalResponse.from_domain(
        await service.get_principal(actor(principal), principal_id)
    )


@router.put("/principals/{principal_id}/tenant-scopes", response_model=PrincipalResponse)
async def set_scopes(
    principal_id: UUID,
    payload: SetTenantScopesRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
    service: Annotated[ManagementIdentityService, Depends(identity_service)],
) -> PrincipalResponse:
    return PrincipalResponse.from_domain(
        await service.set_scopes(
            SetScopesCommand(actor(principal), principal_id, payload.tenant_ids)
        )
    )


@router.post(
    "/principals/{principal_id}/credentials",
    response_model=IssuedCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def issue_credential(
    principal_id: UUID,
    payload: IssueCredentialRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
    service: Annotated[ManagementIdentityService, Depends(identity_service)],
) -> IssuedCredentialResponse:
    return IssuedCredentialResponse.from_issued(
        await service.issue_credential(
            IssueCredentialCommand(
                actor(principal), principal_id, payload.label, payload.expires_at
            )
        )
    )


@router.post(
    "/principals/{principal_id}/credentials/{credential_id}/revoke",
    response_model=CredentialMetadataResponse,
)
async def revoke_credential(
    principal_id: UUID,
    credential_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
    service: Annotated[ManagementIdentityService, Depends(identity_service)],
) -> CredentialMetadataResponse:
    return CredentialMetadataResponse.from_domain(
        await service.revoke_credential(
            RevokeCredentialCommand(actor(principal), principal_id, credential_id)
        )
    )


@router.post("/principals/{principal_id}/disable", response_model=PrincipalResponse)
async def disable_principal(
    principal_id: UUID,
    principal: Annotated[AuthenticatedPrincipal, Depends(require_management_principal)],
    service: Annotated[ManagementIdentityService, Depends(identity_service)],
) -> PrincipalResponse:
    return PrincipalResponse.from_domain(
        await service.disable_principal(DisablePrincipalCommand(actor(principal), principal_id))
    )
