from uuid import UUID

import pytest
from pydantic import ValidationError

from valor.bootstrap.settings import Settings


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VALOR_DATABASE__URL", raising=False)
    monkeypatch.setenv("VALOR_SECURITY__MANAGEMENT_PRINCIPAL_ID", "test-management")
    monkeypatch.setenv("VALOR_SECURITY__MANAGEMENT_TOKEN", "test-only-management-token-32-bytes")
    monkeypatch.setenv("VALOR_SECURITY__MANAGEMENT_TENANT_IDS", "[]")
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
    settings = Settings(_env_file=None)
    assert settings.application.environment == "staging"
    assert settings.database.url.hosts()[0]["host"] == "db"
    assert settings.provider.openai_api_key is not None
    assert settings.provider.openai_api_key.get_secret_value() == "test-secret"
    assert "test-secret" not in repr(settings)
    assert settings.security.management_principal_id == "ops-console"
    assert settings.security.management_tenant_ids == {UUID("11111111-1111-4111-8111-111111111111")}
    assert "test-only-management-token-32-bytes" not in repr(settings)


def test_management_credentials_are_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALOR_DATABASE__URL", "postgresql+psycopg://user:pass@db:5432/valor")
    monkeypatch.delenv("VALOR_SECURITY__MANAGEMENT_PRINCIPAL_ID", raising=False)
    monkeypatch.delenv("VALOR_SECURITY__MANAGEMENT_TOKEN", raising=False)
    monkeypatch.delenv("VALOR_SECURITY__MANAGEMENT_TENANT_IDS", raising=False)
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
    with pytest.raises(ValidationError):
        Settings(_env_file=None)
