from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from valor.management_identity.application.handlers import IssuedCredential
from valor.management_identity.domain.authentication_evidence import (
    ManagementAuthenticationEvidence,
)
from valor.management_identity.domain.models import ManagementCredential, ManagementPrincipal


class BootstrapRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    tenant_ids: frozenset[UUID] = frozenset()


class CreatePrincipalRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    tenant_ids: frozenset[UUID] = frozenset()
    can_manage_principals: bool = False


class SetTenantScopesRequest(BaseModel):
    tenant_ids: frozenset[UUID]


class IssueCredentialRequest(BaseModel):
    label: str | None = Field(default=None, max_length=100)
    expires_at: datetime | None = None


class PrincipalResponse(BaseModel):
    principal_id: UUID
    display_name: str
    tenant_ids: frozenset[UUID]
    can_manage_principals: bool
    created_at: datetime
    disabled_at: datetime | None

    @classmethod
    def from_domain(cls, value: ManagementPrincipal) -> "PrincipalResponse":
        return cls(**{field: getattr(value, field) for field in cls.model_fields})


class CredentialMetadataResponse(BaseModel):
    credential_id: UUID
    principal_id: UUID
    label: str | None
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None

    @classmethod
    def from_domain(cls, value: ManagementCredential) -> "CredentialMetadataResponse":
        return cls(
            credential_id=value.credential_id,
            principal_id=value.principal_id,
            label=value.label,
            created_at=value.created_at,
            expires_at=value.expires_at,
            revoked_at=value.revoked_at,
        )


class IssuedCredentialResponse(CredentialMetadataResponse):
    bearer_token: str

    @classmethod
    def from_issued(cls, value: IssuedCredential) -> "IssuedCredentialResponse":
        metadata = CredentialMetadataResponse.from_domain(value.credential)
        return cls(**metadata.model_dump(), bearer_token=value.bearer_token)


class BootstrapResponse(BaseModel):
    principal: PrincipalResponse
    credential: IssuedCredentialResponse


class ManagementAuthenticationEvidenceResponse(BaseModel):
    credential_id: UUID
    principal_id: UUID
    outcome: str
    bucket_started_at: datetime
    first_observed_at: datetime

    @classmethod
    def from_domain(
        cls, value: ManagementAuthenticationEvidence
    ) -> "ManagementAuthenticationEvidenceResponse":
        return cls(
            credential_id=value.credential_id,
            principal_id=value.principal_id,
            outcome=value.outcome.value,
            bucket_started_at=value.bucket_started_at,
            first_observed_at=value.first_observed_at,
        )
