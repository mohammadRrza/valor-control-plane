import os
from collections.abc import AsyncIterator, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.integration.management_helpers import BOOTSTRAP_TOKEN, PEPPER, bootstrap_management
from valor.bootstrap.application import create_app
from valor.bootstrap.settings import (
    DatabaseSettings,
    RuntimeAuthenticationSettings,
    SecuritySettings,
    Settings,
)
from valor.runtime_gateway.application.ports import (
    ProviderInvocationResult,
    ProviderTransportError,
)
from valor.runtime_gateway.domain.usage import InvocationUsage


class DeterministicRuntimeProvider:
    def __init__(self) -> None:
        self.fails = False
        self.calls: list[tuple[str, str]] = []
        self.usage_totals: list[int] = []
        self.usage_available = True

    async def invoke(self, *, model_reference: str, input_text: str) -> ProviderInvocationResult:
        self.calls.append((model_reference, input_text))
        if self.fails:
            raise ProviderTransportError
        total = self.usage_totals.pop(0) if self.usage_totals else None
        usage = (
            None
            if not self.usage_available
            else (
                InvocationUsage(total // 2, total - total // 2, total)
                if total is not None
                else InvocationUsage(17, 9, 26)
            )
        )
        return ProviderInvocationResult(
            f"provider output for {input_text}",
            usage,
            "resp_deterministic_123",
        )


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
        await connection.execute(text("DELETE FROM management_audit_records"))
        await connection.execute(text("DELETE FROM management_authentication_evidence"))
        await connection.execute(text("DELETE FROM management_credentials"))
        await connection.execute(text("DELETE FROM management_principal_tenant_scopes"))
        await connection.execute(text("DELETE FROM management_principals"))
        await connection.execute(text("DELETE FROM invocations"))
        await connection.execute(text("DELETE FROM policy_decisions"))
        await connection.execute(text("DELETE FROM agent_model_permissions"))
        await connection.execute(text("DELETE FROM models"))
        await connection.execute(text("DELETE FROM agents"))
        await connection.execute(text("DELETE FROM tenants"))
    yield
    async with engine.begin() as connection:
        await connection.execute(text("DELETE FROM management_audit_records"))
        await connection.execute(text("DELETE FROM management_authentication_evidence"))
        await connection.execute(text("DELETE FROM management_credentials"))
        await connection.execute(text("DELETE FROM management_principal_tenant_scopes"))
        await connection.execute(text("DELETE FROM management_principals"))
        await connection.execute(text("DELETE FROM invocations"))
        await connection.execute(text("DELETE FROM policy_decisions"))
        await connection.execute(text("DELETE FROM agent_model_permissions"))
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
    settings = Settings(
        database=DatabaseSettings(url=runtime_database_url),
        security=SecuritySettings(
            management_bootstrap_token=BOOTSTRAP_TOKEN,
            management_credential_pepper=PEPPER,
        ),
        runtime_auth=RuntimeAuthenticationSettings(principals=()),
    )
    with TestClient(create_app(settings, runtime_provider=runtime_provider)) as client:
        bootstrap_management(client)
        yield client


@pytest.fixture
def unauthenticated_runtime_client(
    runtime_database_url: str,
    runtime_provider: DeterministicRuntimeProvider,
) -> Iterator[TestClient]:
    settings = Settings(
        database=DatabaseSettings(url=runtime_database_url),
        security=SecuritySettings(
            management_bootstrap_token=BOOTSTRAP_TOKEN,
            management_credential_pepper=PEPPER,
        ),
        runtime_auth=RuntimeAuthenticationSettings(principals=()),
    )
    with TestClient(create_app(settings, runtime_provider=runtime_provider)) as client:
        yield client
