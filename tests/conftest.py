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

TEST_MANAGEMENT_TOKEN = "test-only-management-token-32-bytes"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database=DatabaseSettings(url="postgresql+psycopg://valor:valor@localhost:5432/valor"),
        security=SecuritySettings(
            management_principal_id="test-management",
            management_token=TEST_MANAGEMENT_TOKEN,
            management_tenant_ids=frozenset(),
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
