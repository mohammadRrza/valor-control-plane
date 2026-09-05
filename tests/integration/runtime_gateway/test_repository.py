from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from valor.ai_asset_registry.domain.agent import Agent
from valor.ai_asset_registry.domain.agent import AgentId as RegistryAgentId
from valor.ai_asset_registry.domain.model import Model, Provider
from valor.ai_asset_registry.domain.model import ModelId as RegistryModelId
from valor.ai_asset_registry.domain.ownership import OwningTenantId
from valor.ai_asset_registry.infrastructure.model_unit_of_work import SqlAlchemyModelUnitOfWork
from valor.ai_asset_registry.infrastructure.unit_of_work import SqlAlchemyAgentUnitOfWork
from valor.identity_tenancy.domain.tenant import Tenant
from valor.identity_tenancy.domain.tenant import TenantId as RegistryTenantId
from valor.identity_tenancy.infrastructure.unit_of_work import SqlAlchemyTenantUnitOfWork
from valor.policy_risk.domain.identity import (
    AgentId as PolicyAgentId,
)
from valor.policy_risk.domain.identity import (
    DecisionId,
)
from valor.policy_risk.domain.identity import (
    InvocationId as PolicyInvocationId,
)
from valor.policy_risk.domain.identity import (
    ModelId as PolicyModelId,
)
from valor.policy_risk.domain.identity import (
    TenantId as PolicyTenantId,
)
from valor.policy_risk.domain.policy import PolicyDecision, PolicyEffect
from valor.policy_risk.infrastructure.unit_of_work import SqlAlchemyPolicyUnitOfWork
from valor.runtime_gateway.application.errors import (
    AgentNotAvailable,
    ModelNotAvailable,
    TenantNotAvailable,
)
from valor.runtime_gateway.domain.cost import InvocationCost
from valor.runtime_gateway.domain.identity import (
    AgentId,
    InvocationId,
    ModelId,
    PolicyDecisionId,
    TenantId,
)
from valor.runtime_gateway.domain.invocation import Invocation
from valor.runtime_gateway.domain.usage import InvocationUsage
from valor.runtime_gateway.infrastructure.admission import PostgresRuntimeAdmission
from valor.runtime_gateway.infrastructure.unit_of_work import SqlAlchemyInvocationUnitOfWork
from valor.runtime_gateway.infrastructure.usage_reader import PostgresRuntimeUsageReader

TENANT_UUID = UUID("11111111-1111-4111-8111-111111111111")
AGENT_UUID = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
MODEL_UUID = UUID("cccccccc-cccc-4ccc-8ccc-cccccccccccc")
INVOCATION_ID = InvocationId(UUID("eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"))
STARTED_AT = datetime(2026, 2, 3, 4, 5, 6, 678901, tzinfo=UTC)
COMPLETED_AT = STARTED_AT + timedelta(seconds=1)
DECISION_UUID = UUID("dddddddd-dddd-4ddd-8ddd-dddddddddddd")
DECISION_ID = PolicyDecisionId(DECISION_UUID)


def sessions_for(database_url: str) -> tuple[async_sessionmaker[AsyncSession], AsyncEngine]:
    engine = create_async_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False), engine


async def persist_runtime_references(sessions: async_sessionmaker[AsyncSession]) -> None:
    async with SqlAlchemyTenantUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.tenants.add(
            Tenant.create(RegistryTenantId(TENANT_UUID), "Acme", STARTED_AT)
        )
        await unit_of_work.commit()
    async with SqlAlchemyAgentUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.agents.add(
            Agent.register(
                RegistryAgentId(AGENT_UUID),
                OwningTenantId(TENANT_UUID),
                "Runtime Agent",
                STARTED_AT,
            )
        )
        await unit_of_work.commit()
    async with SqlAlchemyModelUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.models.add(
            Model.register(
                RegistryModelId(MODEL_UUID),
                OwningTenantId(TENANT_UUID),
                "Runtime Model",
                Provider.OPENAI,
                "gpt-test",
                STARTED_AT,
            )
        )
        await unit_of_work.commit()
    async with SqlAlchemyPolicyUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.decisions.add(
            PolicyDecision(
                DecisionId(DECISION_UUID),
                PolicyInvocationId(INVOCATION_ID.value),
                PolicyTenantId(TENANT_UUID),
                PolicyAgentId(AGENT_UUID),
                PolicyModelId(MODEL_UUID),
                None,
                PolicyEffect.ALLOW,
                STARTED_AT,
            )
        )
        await unit_of_work.commit()


def succeeded_invocation(
    *,
    tenant_id: UUID = TENANT_UUID,
    agent_id: UUID = AGENT_UUID,
    model_id: UUID = MODEL_UUID,
) -> Invocation:
    return Invocation.succeeded(
        INVOCATION_ID,
        TenantId(tenant_id),
        AgentId(agent_id),
        ModelId(model_id),
        "input",
        "output",
        STARTED_AT,
        COMPLETED_AT,
        DECISION_ID,
        "runtime-principal",
        InvocationUsage(10, 5, 15),
        "provider-request-1",
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_succeeded_invocation_persists_and_reconstitutes_exact_values(
    runtime_database_url: str,
) -> None:
    sessions, engine = sessions_for(runtime_database_url)
    await persist_runtime_references(sessions)
    expected = succeeded_invocation()
    async with SqlAlchemyInvocationUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.invocations.add(expected)
        await unit_of_work.commit()
    async with SqlAlchemyInvocationUnitOfWork(sessions) as unit_of_work:
        assert await unit_of_work.invocations.get(INVOCATION_ID) == expected
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invocation_cost_snapshot_round_trips_exact_decimal_values(
    runtime_database_url: str,
) -> None:
    sessions, engine = sessions_for(runtime_database_url)
    await persist_runtime_references(sessions)
    cost = InvocationCost(
        "USD",
        Decimal("0.500000000000"),
        Decimal("0.800000000000"),
        Decimal("1.300000000000"),
        "synthetic-v1",
        1_000_000,
        Decimal("2.000000000000"),
        Decimal("8.000000000000"),
    )
    expected = Invocation.succeeded(
        INVOCATION_ID,
        TenantId(TENANT_UUID),
        AgentId(AGENT_UUID),
        ModelId(MODEL_UUID),
        "input",
        "output",
        STARTED_AT,
        COMPLETED_AT,
        DECISION_ID,
        "runtime-principal",
        InvocationUsage(250_000, 100_000, 350_000),
        "provider-response",
        cost,
    )
    async with SqlAlchemyInvocationUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.invocations.add(expected)
        await unit_of_work.commit()
    async with SqlAlchemyInvocationUnitOfWork(sessions) as unit_of_work:
        assert await unit_of_work.invocations.get(INVOCATION_ID) == expected
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "assignment",
    ["cost_currency = 'USD'", "cost_input = -1"],
)
async def test_database_rejects_partial_or_negative_cost_snapshot(
    runtime_database_url: str, assignment: str
) -> None:
    sessions, engine = sessions_for(runtime_database_url)
    await persist_runtime_references(sessions)
    async with SqlAlchemyInvocationUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.invocations.add(succeeded_invocation())
        await unit_of_work.commit()
    with pytest.raises(IntegrityError):
        async with engine.begin() as connection:
            await connection.execute(
                text(f"UPDATE invocations SET {assignment} WHERE id = :id"),  # noqa: S608
                {"id": INVOCATION_ID.value},
            )
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_failed_invocation_persists_without_output(runtime_database_url: str) -> None:
    sessions, engine = sessions_for(runtime_database_url)
    await persist_runtime_references(sessions)
    expected = Invocation.failed(
        INVOCATION_ID,
        TenantId(TENANT_UUID),
        AgentId(AGENT_UUID),
        ModelId(MODEL_UUID),
        "input",
        STARTED_AT,
        COMPLETED_AT,
        DECISION_ID,
        "runtime-principal",
    )
    async with SqlAlchemyInvocationUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.invocations.add(expected)
        await unit_of_work.commit()
    async with SqlAlchemyInvocationUnitOfWork(sessions) as unit_of_work:
        assert await unit_of_work.invocations.get(INVOCATION_ID) == expected
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cost_limited_invocation_round_trips_exact_budget_evidence(
    runtime_database_url: str,
) -> None:
    sessions, engine = sessions_for(runtime_database_url)
    await persist_runtime_references(sessions)
    expected = Invocation.cost_limited(
        INVOCATION_ID,
        TenantId(TENANT_UUID),
        AgentId(AGENT_UUID),
        ModelId(MODEL_UUID),
        "input",
        STARTED_AT,
        COMPLETED_AT,
        DECISION_ID,
        "runtime-principal",
        consumed=Decimal("9.000000000001"),
        limit=Decimal("10.000000000000"),
        allowance=Decimal("1.000000000000"),
        window_start=STARTED_AT.replace(hour=0, minute=0, second=0, microsecond=0),
        window_end=STARTED_AT.replace(hour=0, minute=0, second=0, microsecond=0)
        + timedelta(days=1),
    )
    async with SqlAlchemyInvocationUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.invocations.add(expected)
        await unit_of_work.commit()
    async with SqlAlchemyInvocationUnitOfWork(sessions) as unit_of_work:
        assert await unit_of_work.invocations.get(INVOCATION_ID) == expected
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_database_rejects_budget_evidence_on_non_cost_limited_invocation(
    runtime_database_url: str,
) -> None:
    sessions, engine = sessions_for(runtime_database_url)
    await persist_runtime_references(sessions)
    async with SqlAlchemyInvocationUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.invocations.add(succeeded_invocation())
        await unit_of_work.commit()
    with pytest.raises(IntegrityError):
        async with engine.begin() as connection:
            await connection.execute(
                text("UPDATE invocations SET cost_budget_consumed = 1 WHERE id = :id"),
                {"id": INVOCATION_ID.value},
            )
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_legacy_null_telemetry_remains_readable(runtime_database_url: str) -> None:
    sessions, engine = sessions_for(runtime_database_url)
    await persist_runtime_references(sessions)
    async with SqlAlchemyInvocationUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.invocations.add(succeeded_invocation())
        await unit_of_work.commit()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE invocations SET duration_ms = NULL, input_units = NULL, "
                "output_units = NULL, total_units = NULL, provider_response_id = NULL "
                "WHERE id = :id"
            ),
            {"id": INVOCATION_ID.value},
        )
    async with SqlAlchemyInvocationUnitOfWork(sessions) as unit_of_work:
        invocation = await unit_of_work.invocations.get(INVOCATION_ID)
    assert invocation is not None
    assert invocation.duration_ms is None
    assert invocation.usage is None
    assert invocation.provider_response_id is None
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize("column", ["duration_ms", "input_units", "output_units", "total_units"])
async def test_database_rejects_negative_observability_values(
    runtime_database_url: str, column: str
) -> None:
    sessions, engine = sessions_for(runtime_database_url)
    await persist_runtime_references(sessions)
    async with SqlAlchemyInvocationUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.invocations.add(succeeded_invocation())
        await unit_of_work.commit()
    with pytest.raises(IntegrityError):
        async with engine.begin() as connection:
            await connection.execute(
                text(f"UPDATE invocations SET {column} = -1 WHERE id = :id"),  # noqa: S608
                {"id": INVOCATION_ID.value},
            )
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"tenant_id": UUID("99999999-9999-4999-8999-999999999999")}, TenantNotAvailable),
        ({"agent_id": UUID("99999999-9999-4999-8999-999999999999")}, AgentNotAvailable),
        ({"model_id": UUID("99999999-9999-4999-8999-999999999999")}, ModelNotAvailable),
    ],
)
async def test_invocation_foreign_keys_translate_to_runtime_errors(
    runtime_database_url: str,
    overrides: dict[str, UUID],
    error: type[Exception],
) -> None:
    sessions, engine = sessions_for(runtime_database_url)
    await persist_runtime_references(sessions)
    with pytest.raises(error):
        async with SqlAlchemyInvocationUnitOfWork(sessions) as unit_of_work:
            await unit_of_work.invocations.add(succeeded_invocation(**overrides))
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_invocation_uow_exit_without_commit_rolls_back(runtime_database_url: str) -> None:
    sessions, engine = sessions_for(runtime_database_url)
    await persist_runtime_references(sessions)
    async with SqlAlchemyInvocationUnitOfWork(sessions) as unit_of_work:
        await unit_of_work.invocations.add(succeeded_invocation())
    async with SqlAlchemyInvocationUnitOfWork(sessions) as unit_of_work:
        assert await unit_of_work.invocations.get(INVOCATION_ID) is None
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_runtime_admission_reads_only_required_projections(
    runtime_database_url: str,
) -> None:
    sessions, engine = sessions_for(runtime_database_url)
    admission = PostgresRuntimeAdmission(sessions)
    assert await admission.exists(TenantId(TENANT_UUID)) is False
    await persist_runtime_references(sessions)
    assert await admission.exists(TenantId(TENANT_UUID)) is True
    agent = await admission.get_agent(AgentId(AGENT_UUID))
    model = await admission.get_model(ModelId(MODEL_UUID))
    assert agent is not None and agent.tenant_id == TenantId(TENANT_UUID)
    assert model is not None and model.tenant_id == TenantId(TENANT_UUID)
    assert model.provider == "openai"
    assert model.provider_model_reference == "gpt-test"
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_usage_reader_aggregates_only_principal_utc_window_known_usage(
    runtime_database_url: str,
) -> None:
    sessions, engine = sessions_for(runtime_database_url)
    await persist_runtime_references(sessions)
    current_start = datetime(2026, 2, 3, tzinfo=UTC)
    rows = [
        ("10000000-0000-4000-8000-000000000001", "principal-a", current_start, 30),
        ("10000000-0000-4000-8000-000000000002", "principal-a", current_start, 40),
        (
            "10000000-0000-4000-8000-000000000003",
            "principal-a",
            current_start - timedelta(minutes=1),
            900,
        ),
        ("10000000-0000-4000-8000-000000000004", "principal-b", current_start, 50),
        ("10000000-0000-4000-8000-000000000005", "principal-a", current_start, None),
    ]
    async with engine.begin() as connection:
        for invocation_id, principal_id, started_at, total_units in rows:
            await connection.execute(
                text(
                    "INSERT INTO invocations "
                    "(id, tenant_id, agent_id, model_id, status, input_text, output_text, "
                    "started_at, completed_at, policy_decision_id, runtime_principal_id, "
                    "duration_ms, total_units) VALUES "
                    "(:id, :tenant, :agent, :model, 'succeeded', 'input', 'output', "
                    ":started, :started, :decision, :principal, 0, :total)"
                ),
                {
                    "id": UUID(invocation_id),
                    "tenant": TENANT_UUID,
                    "agent": AGENT_UUID,
                    "model": MODEL_UUID,
                    "started": started_at,
                    "decision": DECISION_UUID,
                    "principal": principal_id,
                    "total": total_units,
                },
            )
    reader = PostgresRuntimeUsageReader(sessions)
    assert (
        await reader.consumed_total_units(
            runtime_principal_id="principal-a",
            window_start=current_start,
            window_end=current_start + timedelta(days=1),
        )
        == 70
    )
    assert (
        await reader.consumed_total_units(
            runtime_principal_id="principal-b",
            window_start=current_start,
            window_end=current_start + timedelta(days=1),
        )
        == 50
    )
    await engine.dispose()
