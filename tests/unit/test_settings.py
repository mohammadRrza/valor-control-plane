from uuid import UUID

import pytest
from pydantic import ValidationError

from valor.bootstrap.settings import (
    DatabaseSettings,
    RuntimeAuthenticationSettings,
    RuntimePrincipalSettings,
    SecuritySettings,
    Settings,
)


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
        '"credential":"runtime-test-secret-at-least-32-bytes"}]',
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
