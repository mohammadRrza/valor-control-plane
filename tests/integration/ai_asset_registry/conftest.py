import os
from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from valor.bootstrap.application import create_app
from valor.bootstrap.settings import DatabaseSettings, Settings


@pytest.fixture
def agent_database_url() -> str:
    url = os.environ.get("VALOR_TEST_DATABASE_URL")
    if url is None:
        pytest.skip("VALOR_TEST_DATABASE_URL is not configured")
    return url


@pytest.fixture(autouse=True)
async def clean_assets_and_tenants(agent_database_url: str) -> AsyncIterator[None]:
    engine = create_async_engine(agent_database_url)
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM models"))
        await connection.execute(text("DELETE FROM agents"))
        await connection.execute(text("DELETE FROM tenants"))
    yield
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM models"))
        await connection.execute(text("DELETE FROM agents"))
        await connection.execute(text("DELETE FROM tenants"))
    await engine.dispose()


@pytest.fixture
def agent_postgres_client(agent_database_url: str) -> Iterator[TestClient]:
    settings = Settings(database=DatabaseSettings(url=agent_database_url))
    with TestClient(create_app(settings)) as client:
        yield client
