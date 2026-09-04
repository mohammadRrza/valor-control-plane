from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, async_sessionmaker, create_async_engine

from valor.runtime_gateway.domain.identity import TenantId
from valor.runtime_gateway.infrastructure.reporting import PostgresTenantRuntimeReportReader

TENANT_A = UUID("11111111-1111-4111-8111-111111111111")
TENANT_B = UUID("22222222-2222-4222-8222-222222222222")
START = datetime(2026, 9, 1, tzinfo=UTC)
END = START + timedelta(days=1)


async def seed_references(connection: AsyncConnection) -> None:
    for tenant_id, suffix in ((TENANT_A, "a"), (TENANT_B, "b")):
        await connection.execute(
            text(
                "INSERT INTO tenants (id, name, normalized_name, created_at) "
                "VALUES (:id, :name, :normalized_name, :created_at)"
            ),
            {
                "id": tenant_id,
                "name": f"Tenant {suffix}",
                "normalized_name": f"tenant {suffix}",
                "created_at": START,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO agents (id, tenant_id, name, normalized_name, created_at) "
                "VALUES (:id, :tenant_id, :name, :normalized_name, :created_at)"
            ),
            {
                "id": UUID(f"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa{1 if suffix == 'a' else 2}"),
                "tenant_id": tenant_id,
                "name": f"Agent {suffix}",
                "normalized_name": f"agent {suffix}",
                "created_at": START,
            },
        )
        await connection.execute(
            text(
                "INSERT INTO models "
                "(id, tenant_id, name, normalized_name, provider, "
                "provider_model_reference, created_at) VALUES "
                "(:id, :tenant_id, :name, :normalized_name, 'openai', 'gpt-test', :created_at)"
            ),
            {
                "id": UUID(f"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb{1 if suffix == 'a' else 2}"),
                "tenant_id": tenant_id,
                "name": f"Model {suffix}",
                "normalized_name": f"model {suffix}",
                "created_at": START,
            },
        )


def invocation_values(
    status: str,
    started_at: datetime,
    *,
    tenant_id: UUID = TENANT_A,
    usage: tuple[int, int, int] | None = None,
    cost: Decimal | None = None,
    pricing_version: str | None = None,
) -> dict[str, object]:
    suffix = 1 if tenant_id == TENANT_A else 2
    limited = status == "limited"
    return {
        "id": uuid4(),
        "tenant_id": tenant_id,
        "agent_id": UUID(f"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa{suffix}"),
        "model_id": UUID(f"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb{suffix}"),
        "status": status,
        "output_text": "output" if status == "succeeded" else None,
        "started_at": started_at,
        "completed_at": started_at + timedelta(seconds=1),
        "input_units": usage[0] if usage else None,
        "output_units": usage[1] if usage else None,
        "total_units": usage[2] if usage else None,
        "consumed": 100 if limited else None,
        "limit": 100 if limited else None,
        "allowance": 1 if limited else None,
        "window_start": START if limited else None,
        "window_end": END if limited else None,
        "currency": "USD" if cost is not None else None,
        "cost_input": cost if cost is not None else None,
        "cost_output": Decimal("0") if cost is not None else None,
        "cost_total": cost,
        "pricing_version": pricing_version,
        "basis": 1_000_000 if cost is not None else None,
        "input_rate": Decimal("1") if cost is not None else None,
        "output_rate": Decimal("1") if cost is not None else None,
    }


INSERT_INVOCATION = text(
    "INSERT INTO invocations (id, tenant_id, agent_id, model_id, status, input_text, "
    "output_text, started_at, completed_at, runtime_principal_id, duration_ms, input_units, "
    "output_units, total_units, usage_consumed_units, usage_limit_units, "
    "usage_allowance_units, usage_window_start, usage_window_end, cost_currency, cost_input, "
    "cost_output, cost_total, pricing_version, pricing_basis_units, pricing_input_rate, "
    "pricing_output_rate) VALUES (:id, :tenant_id, :agent_id, :model_id, :status, 'input', "
    ":output_text, :started_at, :completed_at, 'runtime-test', 1000, :input_units, "
    ":output_units, :total_units, :consumed, :limit, :allowance, :window_start, :window_end, "
    ":currency, :cost_input, :cost_output, :cost_total, :pricing_version, :basis, "
    ":input_rate, :output_rate)"
)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_report_aggregates_exact_tenant_half_open_evidence(
    runtime_database_url: str,
    runtime_client: TestClient,
) -> None:
    engine = create_async_engine(runtime_database_url)
    async with engine.begin() as connection:
        await seed_references(connection)
        rows = [
            invocation_values(
                "succeeded",
                START,
                usage=(100, 40, 140),
                cost=Decimal("1.000000000001"),
                pricing_version="version-a",
            ),
            invocation_values(
                "succeeded",
                START + timedelta(hours=1),
                usage=(20, 10, 30),
                cost=Decimal("2.000000000002"),
                pricing_version="version-b",
            ),
            invocation_values("succeeded", START + timedelta(hours=2)),
            invocation_values("failed", START + timedelta(hours=3)),
            invocation_values("failed", START + timedelta(hours=4)),
            invocation_values("denied", START + timedelta(hours=5)),
            invocation_values("limited", START + timedelta(hours=6)),
            invocation_values("succeeded", END, usage=(999, 999, 1998)),
            invocation_values("succeeded", START, tenant_id=TENANT_B, usage=(999, 999, 1998)),
        ]
        for row in rows:
            await connection.execute(INSERT_INVOCATION, row)

    reader = PostgresTenantRuntimeReportReader(async_sessionmaker(engine))
    report = await reader.get_report(tenant_id=TenantId(TENANT_A), start=START, end=END)

    assert report.invocations.total == 7
    assert report.invocations.succeeded == 3
    assert report.invocations.failed == 2
    assert report.invocations.denied == 1
    assert report.invocations.limited == 1
    assert report.usage.input_units == 120
    assert report.usage.output_units == 50
    assert report.usage.total_units == 170
    assert report.usage.provider_executed_invocations == 5
    assert report.usage.attributed_invocations == 2
    assert report.usage.unavailable_invocations == 3
    assert report.estimated_cost.total == Decimal("3.000000000003")
    assert report.estimated_cost.attributed_invocations == 2
    assert report.estimated_cost.unavailable_invocations == 1

    cast(FastAPI, runtime_client.app).state.settings.security.management_tenant_ids = frozenset(
        {TENANT_A}
    )
    response = runtime_client.get(
        f"/api/v1/tenants/{TENANT_A}/runtime-report",
        params={"start": START.isoformat(), "end": END.isoformat()},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["invocations"] == {
        "total": 7,
        "succeeded": 3,
        "failed": 2,
        "denied": 1,
        "limited": 1,
    }
    assert payload["usage"] == {
        "input_units": 120,
        "output_units": 50,
        "total_units": 170,
        "provider_executed_invocations": 5,
        "attributed_invocations": 2,
        "unavailable_invocations": 3,
    }
    assert payload["estimated_cost"] == {
        "currency": "USD",
        "total": "3.000000000003",
        "attributed_invocations": 2,
        "unavailable_invocations": 1,
    }
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_report_returns_explicit_zero_aggregates(runtime_database_url: str) -> None:
    engine = create_async_engine(runtime_database_url)
    async with engine.begin() as connection:
        await seed_references(connection)
    reader = PostgresTenantRuntimeReportReader(async_sessionmaker(engine))
    assert await reader.tenant_exists(TenantId(TENANT_A))
    report = await reader.get_report(tenant_id=TenantId(TENANT_A), start=START, end=END)
    assert report.invocations.total == 0
    assert report.usage.total_units == 0
    assert report.estimated_cost.total == Decimal("0.000000000000")
    await engine.dispose()
