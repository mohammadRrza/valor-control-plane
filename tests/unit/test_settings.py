import pytest
from pydantic import ValidationError

from valor.bootstrap.settings import Settings


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VALOR_DATABASE__URL", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_nested_environment_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VALOR_DATABASE__URL", "postgresql+psycopg://user:pass@db:5432/valor")
    monkeypatch.setenv("VALOR_APPLICATION__ENVIRONMENT", "staging")
    settings = Settings(_env_file=None)
    assert settings.application.environment == "staging"
    assert settings.database.url.hosts()[0]["host"] == "db"
