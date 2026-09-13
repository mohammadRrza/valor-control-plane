from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from valor.runtime_identity.application.handlers import (
    IssuedRuntimeCredential,
    RuntimePrincipalDetails,
)
from valor.runtime_identity.domain.models import RuntimeCredential, RuntimePrincipal


class CredentialRequest(BaseModel):
    label: str | None = Field(default=None, max_length=100)
    expires_at: datetime | None = None


class CreateRuntimePrincipalRequest(BaseModel):
    tenant_id: UUID
    agent_id: UUID
    daily_usage_limit_units: int = Field(gt=0)
    per_invocation_allowance_units: int = Field(gt=0)
    credential: CredentialRequest = CredentialRequest()


class RuntimeUsageLimitsRequest(BaseModel):
    daily_usage_limit_units: int = Field(gt=0)
    per_invocation_allowance_units: int = Field(gt=0)


class RuntimePrincipalResponse(BaseModel):
    principal_id: UUID
    tenant_id: UUID
    agent_id: UUID
    created_at: datetime
    disabled_at: datetime | None
    state: str
    daily_usage_limit_units: int | None
    per_invocation_allowance_units: int | None
    cutover_ready: bool

    @classmethod
    def from_domain(
        cls, value: RuntimePrincipal, *, cutover_ready: bool
    ) -> "RuntimePrincipalResponse":
        return cls(
            principal_id=value.principal_id,
            tenant_id=value.tenant_id,
            agent_id=value.agent_id,
            created_at=value.created_at,
            disabled_at=value.disabled_at,
            state=value.state,
            daily_usage_limit_units=value.daily_usage_limit_units,
            per_invocation_allowance_units=value.per_invocation_allowance_units,
            cutover_ready=cutover_ready,
        )

    @classmethod
    def from_details(cls, value: RuntimePrincipalDetails) -> "RuntimePrincipalResponse":
        return cls.from_domain(value.principal, cutover_ready=value.cutover_ready)


class RuntimeCredentialResponse(BaseModel):
    credential_id: UUID
    principal_id: UUID
    label: str | None
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None

    @classmethod
    def from_domain(cls, value: RuntimeCredential) -> "RuntimeCredentialResponse":
        return cls(
            credential_id=value.credential_id,
            principal_id=value.principal_id,
            label=value.label,
            created_at=value.created_at,
            expires_at=value.expires_at,
            revoked_at=value.revoked_at,
        )


class IssuedRuntimeCredentialResponse(RuntimeCredentialResponse):
    bearer_token: str

    @classmethod
    def from_issued(cls, value: IssuedRuntimeCredential) -> "IssuedRuntimeCredentialResponse":
        metadata = RuntimeCredentialResponse.from_domain(value.credential)
        return cls(**metadata.model_dump(), bearer_token=value.bearer_token)


class CreateRuntimePrincipalResponse(BaseModel):
    principal: RuntimePrincipalResponse
    credential: IssuedRuntimeCredentialResponse
