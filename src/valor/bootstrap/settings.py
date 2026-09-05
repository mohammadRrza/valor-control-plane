"""Centralized, environment-driven configuration."""

from decimal import Decimal
from functools import lru_cache
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PostgresDsn,
    SecretStr,
    StringConstraints,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApplicationSettings(BaseModel):
    name: str = "VALOR"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = False


class DatabaseSettings(BaseModel):
    url: PostgresDsn
    pool_size: int = Field(default=5, ge=1, le=50)
    max_overflow: int = Field(default=10, ge=0, le=100)
    pool_timeout_seconds: float = Field(default=30, gt=0)


class ObservabilitySettings(BaseModel):
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_json: bool = True


class ProviderSettings(BaseModel):
    openai_api_key: SecretStr | None = None
    timeout_seconds: float = Field(default=30, gt=0, le=300)


class PricingEntrySettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    provider_model_reference: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    pricing_version: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    price_basis_units: int = Field(gt=0)
    input_price_per_basis: Decimal = Field(ge=0, max_digits=18, decimal_places=12)
    output_price_per_basis: Decimal = Field(ge=0, max_digits=18, decimal_places=12)
    currency: Literal["USD"] = "USD"


class PricingSettings(BaseModel):
    entries: tuple[PricingEntrySettings, ...] = ()

    @model_validator(mode="after")
    def reject_duplicate_pricing(self) -> "PricingSettings":
        keys = [(entry.provider, entry.provider_model_reference) for entry in self.entries]
        versions = [entry.pricing_version for entry in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("Provider pricing keys must be unique.")
        if len(versions) != len(set(versions)):
            raise ValueError("Pricing versions must be unique.")
        return self


class TenantBudgetEntrySettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: UUID
    daily_estimated_cost_budget: Decimal = Field(gt=0, max_digits=30, decimal_places=12)
    per_invocation_cost_allowance: Decimal = Field(gt=0, max_digits=30, decimal_places=12)
    currency: Literal["USD"] = "USD"

    @model_validator(mode="after")
    def allowance_must_fit_budget(self) -> "TenantBudgetEntrySettings":
        if self.per_invocation_cost_allowance > self.daily_estimated_cost_budget:
            raise ValueError("Tenant cost allowance must not exceed its daily budget.")
        return self


class TenantBudgetSettings(BaseModel):
    entries: tuple[TenantBudgetEntrySettings, ...] = ()

    @model_validator(mode="after")
    def reject_duplicate_tenants(self) -> "TenantBudgetSettings":
        tenant_ids = [entry.tenant_id for entry in self.entries]
        if len(tenant_ids) != len(set(tenant_ids)):
            raise ValueError("Tenant cost budget IDs must be unique.")
        return self


class SecuritySettings(BaseModel):
    management_principal_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    management_token: SecretStr = Field(min_length=32)
    management_tenant_ids: frozenset[UUID]


class RuntimePrincipalSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    principal_id: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
    ]
    tenant_id: UUID
    agent_id: UUID
    credential: SecretStr = Field(min_length=32)
    usage_limit: int = Field(gt=0)
    per_invocation_allowance: int = Field(gt=0)

    @model_validator(mode="after")
    def allowance_must_fit_limit(self) -> "RuntimePrincipalSettings":
        if self.per_invocation_allowance > self.usage_limit:
            raise ValueError("Runtime principal allowance must not exceed its usage limit.")
        return self


class RuntimeAuthenticationSettings(BaseModel):
    principals: tuple[RuntimePrincipalSettings, ...]

    @model_validator(mode="after")
    def reject_ambiguous_principals(self) -> "RuntimeAuthenticationSettings":
        principal_ids = [principal.principal_id for principal in self.principals]
        credentials = [principal.credential.get_secret_value() for principal in self.principals]
        bindings = [(principal.tenant_id, principal.agent_id) for principal in self.principals]
        if len(principal_ids) != len(set(principal_ids)):
            raise ValueError("Runtime principal IDs must be unique.")
        if len(credentials) != len(set(credentials)):
            raise ValueError("Runtime principal credentials must be unique.")
        if len(bindings) != len(set(bindings)):
            raise ValueError("Only one runtime principal may be configured per Agent.")
        return self


class Settings(BaseSettings):
    """VALOR settings loaded once at the composition root."""

    model_config = SettingsConfigDict(
        env_prefix="VALOR_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    application: ApplicationSettings = ApplicationSettings()
    database: DatabaseSettings
    observability: ObservabilitySettings = ObservabilitySettings()
    provider: ProviderSettings = ProviderSettings()
    pricing: PricingSettings = PricingSettings()
    tenant_budgets: TenantBudgetSettings = TenantBudgetSettings()
    security: SecuritySettings
    runtime_auth: RuntimeAuthenticationSettings

    @model_validator(mode="after")
    def separate_management_and_runtime_credentials(self) -> "Settings":
        management = self.security.management_token.get_secret_value()
        if any(
            principal.credential.get_secret_value() == management
            for principal in self.runtime_auth.principals
        ):
            raise ValueError("Management and runtime credentials must be distinct.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
