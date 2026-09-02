from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from valor.api.health import database_engine


def test_liveness_does_not_depend_on_database(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_reports_database_failure(app: FastAPI, client: TestClient) -> None:
    engine = MagicMock()
    engine.connect.side_effect = ConnectionError("database unavailable")
    app.dependency_overrides[database_engine] = lambda: engine
    with capture_logs() as logs:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert logs == [{"event": "database_readiness_failed", "log_level": "warning"}]


def test_readiness_reports_success(app: FastAPI, client: TestClient) -> None:
    connection = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = connection
    engine = MagicMock()
    engine.connect.return_value = context
    app.dependency_overrides[database_engine] = lambda: engine
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}
    connection.execute.assert_awaited_once()
