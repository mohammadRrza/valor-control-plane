import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from valor.bootstrap.settings import get_settings
from valor.shared_kernel.events import DomainEvent


def test_domain_event_has_identity_and_utc_timestamp() -> None:
    event = DomainEvent()
    assert event.event_id.version == 4
    assert event.occurred_at.utcoffset() is not None


def test_settings_factory_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("VALOR_DATABASE__URL", "postgresql+psycopg://user:pass@localhost:5432/valor")
    monkeypatch.setenv("VALOR_SECURITY__MANAGEMENT_PRINCIPAL_ID", "test-management")
    monkeypatch.setenv("VALOR_SECURITY__MANAGEMENT_TOKEN", "test-only-management-token-32-bytes")
    assert get_settings().database.url.hosts()[0]["host"] == "localhost"
    get_settings.cache_clear()


def test_unhandled_error_uses_problem_details(app: FastAPI) -> None:
    @app.get("/explode")
    async def explode() -> None:
        raise RuntimeError("secret internal detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/explode")
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["detail"] == "An unexpected error occurred."
    assert "secret" not in response.text
