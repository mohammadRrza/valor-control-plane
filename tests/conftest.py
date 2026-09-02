from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from valor.bootstrap.application import create_app
from valor.bootstrap.settings import DatabaseSettings, Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database=DatabaseSettings(url="postgresql+psycopg://valor:valor@localhost:5432/valor"),
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
