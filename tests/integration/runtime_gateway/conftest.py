import os
from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from valor.bootstrap.application import create_app
from valor.bootstrap.settings import DatabaseSettings, Settings
from valor.runtime_gateway.application.ports import (
    ProviderInvocationResult,
    ProviderTransportError,
)


class DeterministicRuntimeProvider:
    def __init__(self) -> None:
        self.fails = False
        self.calls: list[tuple[str, str]] = []

    async def invoke(self, *, model_reference: str, input_text: str) -> ProviderInvocationResult:
        self.calls.append((model_reference, input_text))
        if self.fails:
            raise ProviderTransportError
        return ProviderInvocationResult(f"provider output for {input_text}")


@pytest.fixture
def runtime_database_url() -> str:
    url = os.environ.get("VALOR_TEST_DATABASE_URL")
    if url is None:
        pytest.skip("VALOR_TEST_DATABASE_URL is not configured")
    return url


@pytest.fixture(autouse=True)
async def clean_runtime_tables(runtime_database_url: str) -> AsyncIterator[None]:
    engine = create_async_engine(runtime_database_url)
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM invocations"))
        await connection.execute(text("DELETE FROM models"))
        await connection.execute(text("DELETE FROM agents"))
        await connection.execute(text("DELETE FROM tenants"))
    yield
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM invocations"))
        await connection.execute(text("DELETE FROM models"))
        await connection.execute(text("DELETE FROM agents"))
        await connection.execute(text("DELETE FROM tenants"))
    await engine.dispose()


@pytest.fixture
def runtime_provider() -> DeterministicRuntimeProvider:
    return DeterministicRuntimeProvider()


@pytest.fixture
def runtime_client(
    runtime_database_url: str,
    runtime_provider: DeterministicRuntimeProvider,
) -> Iterator[TestClient]:
    settings = Settings(database=DatabaseSettings(url=runtime_database_url))
    with TestClient(create_app(settings, runtime_provider=runtime_provider)) as client:
        yield client
