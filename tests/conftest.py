from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from valor.bootstrap.application import create_app
from valor.bootstrap.settings import (
    DatabaseSettings,
    RuntimeAuthenticationSettings,
    SecuritySettings,
    Settings,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database=DatabaseSettings(url="postgresql+psycopg://valor:valor@localhost:5432/valor"),
        security=SecuritySettings(
            management_bootstrap_token="test-only-management-bootstrap-token-32-bytes",
            management_credential_pepper="test-only-management-pepper-value-32-bytes",
        ),
        runtime_auth=RuntimeAuthenticationSettings(principals=()),
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
