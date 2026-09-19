from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StringConstraints

from valor.runtime_identity.application.handlers import (
    IssuedRuntimeCredential,
    RuntimeIdentityContinuityPreflight,
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


class RuntimeIdentityContinuityRequest(BaseModel):
    legacy_runtime_principal_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]


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
    legacy_runtime_principal_id: str | None
    identity_continuity_bound_at: datetime | None
    identity_continuity_ready: bool

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
            legacy_runtime_principal_id=value.legacy_runtime_principal_id,
            identity_continuity_bound_at=value.identity_continuity_bound_at,
            identity_continuity_ready=value.identity_continuity_ready,
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


class RuntimeIdentityContinuityPreflightResponse(BaseModel):
    principal_id: UUID
    legacy_runtime_principal_id: str
    static_identity_exists: bool
    tenant_binding_matches: bool
    agent_binding_matches: bool
    legacy_identity_unclaimed: bool
    principal_unbound: bool
    historical_invocation_count: int
    same_day_attributed_usage_units: int
    usage_limits_match: bool
    historical_bindings_consistent: bool
    cutover_ready: bool
    safe_to_bind: bool

    @classmethod
    def from_application(
        cls, value: RuntimeIdentityContinuityPreflight
    ) -> "RuntimeIdentityContinuityPreflightResponse":
        return cls(**{field: getattr(value, field) for field in cls.model_fields})
