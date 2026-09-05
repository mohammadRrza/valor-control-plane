from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from valor.bootstrap.settings import (
    DatabaseSettings,
    PricingEntrySettings,
    PricingSettings,
    RuntimeAuthenticationSettings,
    RuntimePrincipalSettings,
    SecuritySettings,
    Settings,
    TenantBudgetEntrySettings,
    TenantBudgetSettings,
)


def pricing_entry(**overrides: object) -> PricingEntrySettings:
    values: dict[str, object] = {
        "provider": "openai",
        "provider_model_reference": "gpt-test",
        "pricing_version": "synthetic-v1",
        "price_basis_units": 1_000_000,
        "input_price_per_basis": "2.0",
        "output_price_per_basis": "8.0",
        "currency": "USD",
    }
    return PricingEntrySettings.model_validate(values | overrides)


def test_valid_and_zero_provider_pricing() -> None:
    entry = pricing_entry(input_price_per_basis="0", output_price_per_basis="0")
    assert entry.input_price_per_basis == Decimal("0")


@pytest.mark.parametrize(
    "overrides",
    [
        {"input_price_per_basis": "-1"},
        {"output_price_per_basis": "-1"},
        {"price_basis_units": 0},
        {"price_basis_units": -1},
        {"input_price_per_basis": "not-decimal"},
        {"currency": "EUR"},
    ],
)
def test_invalid_provider_pricing_fails_fast(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        pricing_entry(**overrides)


@pytest.mark.parametrize("duplicate", ["key", "version"])
def test_duplicate_provider_pricing_fails_fast(duplicate: str) -> None:
    first = pricing_entry()
    second = pricing_entry(
        provider_model_reference=("gpt-test" if duplicate == "key" else "gpt-other"),
        pricing_version=("synthetic-v1" if duplicate == "version" else "synthetic-v2"),
    )
    with pytest.raises(ValidationError):
        PricingSettings(entries=(first, second))


def tenant_budget(**overrides: object) -> TenantBudgetEntrySettings:
    values: dict[str, object] = {
        "tenant_id": "11111111-1111-4111-8111-111111111111",
        "daily_estimated_cost_budget": "10.000000000000",
        "per_invocation_cost_allowance": "1.000000000000",
        "currency": "USD",
    }
    return TenantBudgetEntrySettings.model_validate(values | overrides)


def test_valid_tenant_budget_uses_decimal() -> None:
    entry = tenant_budget()
    assert entry.daily_estimated_cost_budget == Decimal("10.000000000000")
    assert entry.per_invocation_cost_allowance == Decimal("1.000000000000")


@pytest.mark.parametrize(
    "overrides",
    [
        {"daily_estimated_cost_budget": "0"},
        {"daily_estimated_cost_budget": "-1"},
        {"per_invocation_cost_allowance": "0"},
        {"per_invocation_cost_allowance": "-1"},
        {"per_invocation_cost_allowance": "11"},
        {"daily_estimated_cost_budget": "not-decimal"},
        {"currency": "EUR"},
    ],
)
def test_invalid_tenant_budget_fails_fast(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        tenant_budget(**overrides)


def test_missing_tenant_budget_values_fail_fast() -> None:
    with pytest.raises(ValidationError):
        TenantBudgetEntrySettings.model_validate(
            {"tenant_id": "11111111-1111-4111-8111-111111111111"}
        )


def test_duplicate_tenant_budget_configuration_fails_fast() -> None:
    with pytest.raises(ValidationError):
        TenantBudgetSettings(entries=(tenant_budget(), tenant_budget()))


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VALOR_DATABASE__URL", raising=False)
    monkeypatch.setenv("VALOR_SECURITY__MANAGEMENT_PRINCIPAL_ID", "test-management")
    monkeypatch.setenv("VALOR_SECURITY__MANAGEMENT_TOKEN", "test-only-management-token-32-bytes")
    monkeypatch.setenv("VALOR_SECURITY__MANAGEMENT_TENANT_IDS", "[]")
    monkeypatch.setenv("VALOR_RUNTIME_AUTH__PRINCIPALS", "[]")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_nested_environment_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALOR_DATABASE__URL", "postgresql+psycopg://user:pass@db:5432/valor")
    monkeypatch.setenv("VALOR_APPLICATION__ENVIRONMENT", "staging")
    monkeypatch.setenv("VALOR_PROVIDER__OPENAI_API_KEY", "test-secret")
    monkeypatch.setenv("VALOR_SECURITY__MANAGEMENT_PRINCIPAL_ID", "ops-console")
    monkeypatch.setenv("VALOR_SECURITY__MANAGEMENT_TOKEN", "test-only-management-token-32-bytes")
    monkeypatch.setenv(
        "VALOR_SECURITY__MANAGEMENT_TENANT_IDS",
        '["11111111-1111-4111-8111-111111111111"]',
    )
    monkeypatch.setenv(
        "VALOR_RUNTIME_AUTH__PRINCIPALS",
        '[{"principal_id":"runtime-a","tenant_id":"11111111-1111-4111-8111-111111111111",'
        '"agent_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",'
        '"credential":"runtime-test-secret-at-least-32-bytes",'
        '"usage_limit":1000,"per_invocation_allowance":100}]',
    )
    settings = Settings(_env_file=None)
    assert settings.application.environment == "staging"
    assert settings.database.url.hosts()[0]["host"] == "db"
    assert settings.provider.openai_api_key is not None
    assert settings.provider.openai_api_key.get_secret_value() == "test-secret"
    assert "test-secret" not in repr(settings)
    assert settings.security.management_principal_id == "ops-console"
    assert settings.security.management_tenant_ids == {UUID("11111111-1111-4111-8111-111111111111")}
    assert "test-only-management-token-32-bytes" not in repr(settings)
    assert settings.runtime_auth.principals[0].principal_id == "runtime-a"
    assert "runtime-test-secret-at-least-32-bytes" not in repr(settings)


def test_management_credentials_are_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALOR_DATABASE__URL", "postgresql+psycopg://user:pass@db:5432/valor")
    monkeypatch.delenv("VALOR_SECURITY__MANAGEMENT_PRINCIPAL_ID", raising=False)
    monkeypatch.delenv("VALOR_SECURITY__MANAGEMENT_TOKEN", raising=False)
    monkeypatch.delenv("VALOR_SECURITY__MANAGEMENT_TENANT_IDS", raising=False)
    monkeypatch.setenv("VALOR_RUNTIME_AUTH__PRINCIPALS", "[]")
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)
    assert "security" in str(error.value)
    assert "test-only-management-token" not in str(error.value)


def test_malformed_management_tenant_scope_fails_fast(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VALOR_DATABASE__URL", "postgresql+psycopg://user:pass@db:5432/valor")
    monkeypatch.setenv("VALOR_SECURITY__MANAGEMENT_PRINCIPAL_ID", "test-management")
    monkeypatch.setenv("VALOR_SECURITY__MANAGEMENT_TOKEN", "test-only-management-token-32-bytes")
    monkeypatch.setenv("VALOR_SECURITY__MANAGEMENT_TENANT_IDS", '["not-a-uuid"]')
    monkeypatch.setenv("VALOR_RUNTIME_AUTH__PRINCIPALS", "[]")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def runtime_principal(
    principal_id: str,
    agent_id: str,
    credential: str,
) -> RuntimePrincipalSettings:
    return RuntimePrincipalSettings(
        principal_id=principal_id,
        tenant_id=UUID("11111111-1111-4111-8111-111111111111"),
        agent_id=UUID(agent_id),
        credential=credential,
        usage_limit=1000,
        per_invocation_allowance=100,
    )


@pytest.mark.parametrize("duplicate", ["principal_id", "credential", "binding"])
def test_ambiguous_runtime_principal_configuration_fails(duplicate: str) -> None:
    first = runtime_principal(
        "runtime-a",
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "runtime-credential-a-at-least-32-bytes",
    )
    second = runtime_principal(
        "runtime-a" if duplicate == "principal_id" else "runtime-b",
        (
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            if duplicate == "binding"
            else "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        ),
        (
            "runtime-credential-a-at-least-32-bytes"
            if duplicate == "credential"
            else "runtime-credential-b-at-least-32-bytes"
        ),
    )
    with pytest.raises(ValidationError):
        RuntimeAuthenticationSettings(principals=(first, second))


def test_management_credential_cannot_be_configured_as_runtime_credential() -> None:
    shared_credential = "shared-test-credential-at-least-32-bytes"
    with pytest.raises(ValidationError):
        Settings(
            database=DatabaseSettings(url="postgresql+psycopg://valor:valor@localhost:5432/valor"),
            security=SecuritySettings(
                management_principal_id="management",
                management_token=shared_credential,
                management_tenant_ids=frozenset(),
            ),
            runtime_auth=RuntimeAuthenticationSettings(
                principals=(
                    runtime_principal(
                        "runtime-a",
                        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                        shared_credential,
                    ),
                )
            ),
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"usage_limit": 0},
        {"usage_limit": -1},
        {"per_invocation_allowance": 0},
        {"per_invocation_allowance": -1},
        {"usage_limit": 100, "per_invocation_allowance": 101},
    ],
)
def test_invalid_runtime_usage_limit_configuration_fails(overrides: dict[str, int]) -> None:
    values = {
        "principal_id": "runtime-a",
        "tenant_id": UUID("11111111-1111-4111-8111-111111111111"),
        "agent_id": UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        "credential": "runtime-credential-a-at-least-32-bytes",
        "usage_limit": 1000,
        "per_invocation_allowance": 100,
    }
    with pytest.raises(ValidationError):
        RuntimePrincipalSettings.model_validate(values | overrides)


def test_runtime_usage_limit_configuration_is_required() -> None:
    with pytest.raises(ValidationError):
        RuntimePrincipalSettings.model_validate(
            {
                "principal_id": "runtime-a",
                "tenant_id": UUID("11111111-1111-4111-8111-111111111111"),
                "agent_id": UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
                "credential": "runtime-credential-a-at-least-32-bytes",
            }
        )


def test_runtime_principals_have_independent_usage_limits() -> None:
    first = runtime_principal(
        "runtime-a",
        "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "runtime-credential-a-at-least-32-bytes",
    )
    second = RuntimePrincipalSettings(
        principal_id="runtime-b",
        tenant_id=UUID("11111111-1111-4111-8111-111111111111"),
        agent_id=UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"),
        credential="runtime-credential-b-at-least-32-bytes",
        usage_limit=2000,
        per_invocation_allowance=250,
    )
    configured = RuntimeAuthenticationSettings(principals=(first, second))
    assert configured.principals[0].usage_limit == 1000
    assert configured.principals[1].usage_limit == 2000
