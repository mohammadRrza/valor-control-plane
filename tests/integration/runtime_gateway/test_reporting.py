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
from valor.runtime_gateway.infrastructure.cost_budget import PostgresTenantEstimatedCostReader
from valor.runtime_gateway.infrastructure.reporting import PostgresTenantRuntimeReportReader

TENANT_A = UUID("11111111-1111-4111-8111-111111111111")
TENANT_B = UUID("22222222-2222-4222-8222-222222222222")
START = datetime(2026, 9, 1, tzinfo=UTC)
END = START + timedelta(days=1)


def agent_id(number: int) -> UUID:
    return UUID(int=10_000 + number)


def model_id(number: int) -> UUID:
    return UUID(int=20_000 + number)


async def seed_asset_pair(connection: AsyncConnection, tenant_id: UUID, number: int) -> None:
    await connection.execute(
        text(
            "INSERT INTO agents (id, tenant_id, name, normalized_name, created_at) "
            "VALUES (:id, :tenant_id, :name, :normalized_name, :created_at)"
        ),
        {
            "id": agent_id(number),
            "tenant_id": tenant_id,
            "name": f"Agent {number}",
            "normalized_name": f"agent {tenant_id} {number}",
            "created_at": START,
        },
    )
    await connection.execute(
        text(
            "INSERT INTO models (id, tenant_id, name, normalized_name, provider, "
            "provider_model_reference, created_at) VALUES "
            "(:id, :tenant_id, :name, :normalized_name, 'openai', 'gpt-test', :created_at)"
        ),
        {
            "id": model_id(number),
            "tenant_id": tenant_id,
            "name": f"Model {number}",
            "normalized_name": f"model {tenant_id} {number}",
            "created_at": START,
        },
    )


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
    agent: UUID | None = None,
    model: UUID | None = None,
) -> dict[str, object]:
    suffix = 1 if tenant_id == TENANT_A else 2
    limited = status == "limited"
    cost_limited = status == "cost_limited"
    return {
        "id": uuid4(),
        "tenant_id": tenant_id,
        "agent_id": agent or UUID(f"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa{suffix}"),
        "model_id": model or UUID(f"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb{suffix}"),
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
        "budget_consumed": Decimal("9.5") if cost_limited else None,
        "budget_limit": Decimal("10") if cost_limited else None,
        "budget_allowance": Decimal("1") if cost_limited else None,
        "budget_window_start": START if cost_limited else None,
        "budget_window_end": END if cost_limited else None,
    }


INSERT_INVOCATION = text(
    "INSERT INTO invocations (id, tenant_id, agent_id, model_id, status, input_text, "
    "output_text, started_at, completed_at, runtime_principal_id, duration_ms, input_units, "
    "output_units, total_units, usage_consumed_units, usage_limit_units, "
    "usage_allowance_units, usage_window_start, usage_window_end, cost_currency, cost_input, "
    "cost_output, cost_total, pricing_version, pricing_basis_units, pricing_input_rate, "
    "pricing_output_rate, cost_budget_consumed, cost_budget_limit, cost_budget_allowance, "
    "cost_budget_window_start, cost_budget_window_end) VALUES "
    "(:id, :tenant_id, :agent_id, :model_id, :status, 'input', "
    ":output_text, :started_at, :completed_at, 'runtime-test', 1000, :input_units, "
    ":output_units, :total_units, :consumed, :limit, :allowance, :window_start, :window_end, "
    ":currency, :cost_input, :cost_output, :cost_total, :pricing_version, :basis, "
    ":input_rate, :output_rate, :budget_consumed, :budget_limit, :budget_allowance, "
    ":budget_window_start, :budget_window_end)"
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
            invocation_values("cost_limited", START + timedelta(hours=7)),
            invocation_values("succeeded", END, usage=(999, 999, 1998)),
            invocation_values("succeeded", START, tenant_id=TENANT_B, usage=(999, 999, 1998)),
        ]
        for row in rows:
            await connection.execute(INSERT_INVOCATION, row)

    reader = PostgresTenantRuntimeReportReader(async_sessionmaker(engine))
    report = await reader.get_report(tenant_id=TenantId(TENANT_A), start=START, end=END)

    assert report.invocations.total == 8
    assert report.invocations.succeeded == 3
    assert report.invocations.failed == 2
    assert report.invocations.denied == 1
    assert report.invocations.limited == 1
    assert report.invocations.cost_limited == 1
    assert report.usage.input_units == 120
    assert report.usage.output_units == 50
    assert report.usage.total_units == 170
    assert report.usage.provider_executed_invocations == 5
    assert report.usage.attributed_invocations == 2
    assert report.usage.unavailable_invocations == 3
    assert report.estimated_cost.total == Decimal("3.000000000003")
    assert report.estimated_cost.attributed_invocations == 2
    assert report.estimated_cost.unavailable_invocations == 1
    assert report.top_agents_by_estimated_cost[0].invocation_count == 8
    assert report.top_agents_by_estimated_cost[0].cost_unavailable_invocations == 1
    assert report.top_models_by_estimated_cost[0].invocation_count == 8

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
        "total": 8,
        "succeeded": 3,
        "failed": 2,
        "denied": 1,
        "limited": 1,
        "cost_limited": 1,
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
    assert report.top_agents_by_estimated_cost == ()
    assert report.top_models_by_estimated_cost == ()
    assert not report.agent_breakdown_truncated
    assert not report.model_breakdown_truncated
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_report_returns_deterministic_bounded_cost_breakdowns(
    runtime_database_url: str,
    runtime_client: TestClient,
) -> None:
    engine = create_async_engine(runtime_database_url)
    async with engine.begin() as connection:
        await seed_references(connection)
        for number in range(12):
            await seed_asset_pair(connection, TENANT_A, number)
            cost = Decimal(number).quantize(Decimal("0.000000000001"))
            await connection.execute(
                INSERT_INVOCATION,
                invocation_values(
                    "succeeded",
                    START + timedelta(minutes=number),
                    usage=(number, number + 1, number * 2 + 1),
                    cost=cost if number < 10 else None,
                    pricing_version=f"historical-{number % 2}" if number < 10 else None,
                    agent=agent_id(number),
                    model=model_id(number),
                ),
            )
        await connection.execute(
            INSERT_INVOCATION,
            invocation_values(
                "succeeded",
                START + timedelta(hours=2),
                agent=agent_id(9),
                model=model_id(9),
            ),
        )
        await connection.execute(
            INSERT_INVOCATION,
            invocation_values(
                "succeeded",
                END,
                usage=(999, 999, 1998),
                cost=Decimal("999.000000000000"),
                pricing_version="outside-range",
                agent=agent_id(11),
                model=model_id(11),
            ),
        )
        await connection.execute(
            INSERT_INVOCATION,
            invocation_values(
                "succeeded",
                START,
                tenant_id=TENANT_B,
                usage=(999, 999, 1998),
                cost=Decimal("1000.000000000000"),
                pricing_version="other-tenant",
            ),
        )

    reader = PostgresTenantRuntimeReportReader(async_sessionmaker(engine))
    report = await reader.get_report(tenant_id=TenantId(TENANT_A), start=START, end=END)
    expected_agents = [agent_id(number) for number in range(9, -1, -1)]
    expected_models = [model_id(number) for number in range(9, -1, -1)]
    assert [row.agent_id for row in report.top_agents_by_estimated_cost] == expected_agents
    assert [row.model_id for row in report.top_models_by_estimated_cost] == expected_models
    assert len(report.top_agents_by_estimated_cost) == 10
    assert len(report.top_models_by_estimated_cost) == 10
    assert report.agent_breakdown_truncated
    assert report.model_breakdown_truncated

    leading_agent = report.top_agents_by_estimated_cost[0]
    assert leading_agent.invocation_count == 2
    assert leading_agent.total_units == 19
    assert leading_agent.usage_attributed_invocations == 1
    assert leading_agent.usage_unavailable_invocations == 1
    assert leading_agent.estimated_cost_total == Decimal("9.000000000000")
    assert leading_agent.cost_attributed_invocations == 1
    assert leading_agent.cost_unavailable_invocations == 1

    zero_agent = report.top_agents_by_estimated_cost[-1]
    assert zero_agent.agent_id == agent_id(0)
    assert zero_agent.estimated_cost_total == Decimal("0.000000000000")
    assert zero_agent.cost_attributed_invocations == 1
    assert zero_agent.cost_unavailable_invocations == 0

    cast(FastAPI, runtime_client.app).state.settings.security.management_tenant_ids = frozenset(
        {TENANT_A}
    )
    response = runtime_client.get(
        f"/api/v1/tenants/{TENANT_A}/runtime-report",
        params={"start": START.isoformat(), "end": END.isoformat()},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["top_agents_by_estimated_cost"]) == 10
    assert len(payload["top_models_by_estimated_cost"]) == 10
    assert payload["agent_breakdown_truncated"] is True
    assert payload["model_breakdown_truncated"] is True
    assert payload["top_agents_by_estimated_cost"][0] == {
        "agent_id": str(agent_id(9)),
        "invocation_count": 2,
        "total_units": 19,
        "usage_attributed_invocations": 1,
        "usage_unavailable_invocations": 1,
        "estimated_cost_total": "9.000000000000",
        "cost_attributed_invocations": 1,
        "cost_unavailable_invocations": 1,
    }
    assert "input_text" not in response.text
    assert "output_text" not in response.text
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tenant_cost_reader_sums_exact_snapshots_with_tenant_utc_day_isolation(
    runtime_database_url: str,
) -> None:
    engine = create_async_engine(runtime_database_url)
    async with engine.begin() as connection:
        await seed_references(connection)
        rows = [
            invocation_values(
                "succeeded",
                START,
                cost=Decimal("1.000000000001"),
                pricing_version="historical-a",
                usage=(1, 1, 2),
            ),
            invocation_values("succeeded", START + timedelta(hours=1)),
            invocation_values(
                "succeeded",
                END,
                cost=Decimal("999.000000000000"),
                pricing_version="next-day",
                usage=(1, 1, 2),
            ),
            invocation_values(
                "succeeded",
                START,
                tenant_id=TENANT_B,
                cost=Decimal("1000.000000000000"),
                pricing_version="other-tenant",
                usage=(1, 1, 2),
            ),
        ]
        for row in rows:
            await connection.execute(INSERT_INVOCATION, row)
    reader = PostgresTenantEstimatedCostReader(async_sessionmaker(engine))
    cost = await reader.attributed_cost(
        tenant_id=TenantId(TENANT_A), window_start=START, window_end=END
    )
    assert cost == Decimal("1.000000000001")
    assert isinstance(cost, Decimal)
    await engine.dispose()
