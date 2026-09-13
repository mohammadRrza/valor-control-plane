import asyncio
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Any, cast
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.integration.management_helpers import grant_management_scopes
from valor.bootstrap.settings import RuntimeAuthenticationSettings, RuntimePrincipalSettings
from valor.runtime_identity.application.handlers import (
    CreateRuntimePrincipalCommand,
    InitializeRuntimeUsageLimitsCommand,
    IssueRuntimeCredentialCommand,
    RuntimeCredentialCommand,
    RuntimeIdentityActor,
    RuntimeIdentityService,
)
from valor.runtime_identity.domain.models import RuntimeCredential
from valor.runtime_identity.infrastructure.unit_of_work import (
    SqlAlchemyRuntimeIdentityUnitOfWork,
)


def _tenant_and_agent(client: TestClient, suffix: str = "one") -> tuple[UUID, UUID]:
    tenant_response = client.post("/api/v1/tenants", json={"name": f"Runtime {suffix}"})
    assert tenant_response.status_code == 201, tenant_response.text
    tenant_id = UUID(tenant_response.json()["id"])
    grant_management_scopes(client, {tenant_id})
    agent_response = client.post(
        "/api/v1/agents",
        json={"tenant_id": str(tenant_id), "name": f"Runtime Agent {suffix}"},
    )
    assert agent_response.status_code == 201, agent_response.text
    return tenant_id, UUID(agent_response.json()["id"])


def _create(client: TestClient, tenant_id: UUID, agent_id: UUID) -> dict[str, Any]:
    response = client.post(
        "/api/v1/management/runtime-principals",
        json={
            "tenant_id": str(tenant_id),
            "agent_id": str(agent_id),
            "daily_usage_limit_units": 1000,
            "per_invocation_allowance_units": 100,
            "credential": {"label": " initial  deployment "},
        },
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, Any], response.json())


@pytest.mark.integration
def test_runtime_identity_lifecycle_is_secret_safe_audited_and_staged(
    runtime_client: TestClient, runtime_database_url: str
) -> None:
    tenant_id, agent_id = _tenant_and_agent(runtime_client)
    created = _create(runtime_client, tenant_id, agent_id)
    principal = created["principal"]
    initial = created["credential"]
    principal_id = UUID(principal["principal_id"])
    initial_token = initial["bearer_token"]

    assert principal["tenant_id"] == str(tenant_id)
    assert principal["agent_id"] == str(agent_id)
    assert principal["state"] == "active"
    assert principal["daily_usage_limit_units"] == 1000
    assert principal["per_invocation_allowance_units"] == 100
    assert principal["cutover_ready"] is True
    assert initial["label"] == "initial deployment"
    assert initial_token.startswith("valor_runtime_")
    assert (
        runtime_client.get(
            "/api/v1/management/principals",
            headers={"Authorization": f"Bearer {initial_token}"},
        ).status_code
        == 401
    )
    assert (
        runtime_client.get(f"/api/v1/management/runtime-principals/{principal_id}").json()
        == principal
    )

    issued_response = runtime_client.post(
        f"/api/v1/management/runtime-principals/{principal_id}/credentials",
        json={"label": "rotation overlap"},
    )
    assert issued_response.status_code == 201, issued_response.text
    issued = issued_response.json()
    revoked = runtime_client.post(
        f"/api/v1/management/runtime-principals/{principal_id}/credentials/"
        f"{issued['credential_id']}/revoke"
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked_at"] is not None
    assert (
        runtime_client.post(
            f"/api/v1/management/runtime-principals/{principal_id}/credentials/"
            f"{issued['credential_id']}/revoke"
        ).status_code
        == 404
    )

    disabled = runtime_client.post(f"/api/v1/management/runtime-principals/{principal_id}/disable")
    assert disabled.status_code == 200
    assert disabled.json()["state"] == "disabled"
    assert (
        runtime_client.post(
            f"/api/v1/management/runtime-principals/{principal_id}/credentials",
            json={},
        ).status_code
        == 404
    )

    # Phase 5.0A intentionally has no dual Runtime authentication authority.
    runtime_attempt = runtime_client.post(
        "/api/v1/runtime/invocations",
        headers={"Authorization": f"Bearer {initial_token}"},
        json={},
    )
    assert runtime_attempt.status_code == 401

    async def inspect() -> tuple[list[str], tuple[str, str, str | None]]:
        engine = create_async_engine(runtime_database_url)
        async with engine.connect() as connection:
            actions = list(
                await connection.scalars(
                    text(
                        "SELECT action FROM management_audit_records "
                        "WHERE resource_type LIKE 'runtime_%' ORDER BY occurred_at"
                    )
                )
            )
            row = (
                await connection.execute(
                    text(
                        "SELECT secret_verifier, label, revoked_at::text "
                        "FROM runtime_credentials WHERE credential_id = :credential_id"
                    ),
                    {"credential_id": issued["credential_id"]},
                )
            ).one()
        await engine.dispose()
        return actions, (row[0], row[1], row[2])

    actions, stored = asyncio.run(inspect())
    assert actions == [
        "runtime_principal_created",
        "runtime_credential_issued",
        "runtime_credential_issued",
        "runtime_credential_revoked",
        "runtime_principal_disabled",
    ]
    assert len(stored[0]) == 64
    assert initial_token not in stored[0]
    assert stored[1] == "rotation overlap"
    assert stored[2] is not None


@pytest.mark.integration
def test_runtime_binding_and_management_authority_are_non_disclosing(
    runtime_client: TestClient,
) -> None:
    tenant_id, agent_id = _tenant_and_agent(runtime_client, "authority")
    other_tenant, _ = _tenant_and_agent(runtime_client, "other")
    wrong_binding = runtime_client.post(
        "/api/v1/management/runtime-principals",
        json={
            "tenant_id": str(other_tenant),
            "agent_id": str(agent_id),
            "daily_usage_limit_units": 1000,
            "per_invocation_allowance_units": 100,
        },
    )
    assert wrong_binding.status_code == 404

    created_manager = runtime_client.post(
        "/api/v1/management/principals",
        json={
            "display_name": "Scoped non-manager",
            "tenant_ids": [str(tenant_id)],
            "can_manage_principals": False,
        },
    )
    principal_id = created_manager.json()["principal_id"]
    issued = runtime_client.post(
        f"/api/v1/management/principals/{principal_id}/credentials", json={}
    ).json()
    denied = runtime_client.post(
        "/api/v1/management/runtime-principals",
        headers={"Authorization": f"Bearer {issued['bearer_token']}"},
        json={
            "tenant_id": str(tenant_id),
            "agent_id": str(agent_id),
            "daily_usage_limit_units": 1000,
            "per_invocation_allowance_units": 100,
        },
    )
    assert denied.status_code == 404

    anonymous = runtime_client.post(
        "/api/v1/management/runtime-principals",
        headers={"Authorization": ""},
        json={
            "tenant_id": str(tenant_id),
            "agent_id": str(uuid4()),
            "daily_usage_limit_units": 1000,
            "per_invocation_allowance_units": 100,
        },
    )
    assert anonymous.status_code == 401

    static_token = "static-runtime-token-that-is-at-least-32-bytes"
    app = cast(FastAPI, runtime_client.app)
    app.state.settings.runtime_auth = RuntimeAuthenticationSettings(
        principals=(
            RuntimePrincipalSettings(
                principal_id="static-runtime-authority-test",
                tenant_id=tenant_id,
                agent_id=agent_id,
                credential=static_token,
                usage_limit=1000,
                per_invocation_allowance=100,
            ),
        )
    )
    static_denied = runtime_client.post(
        "/api/v1/management/runtime-principals",
        headers={"Authorization": f"Bearer {static_token}"},
        json={
            "tenant_id": str(tenant_id),
            "agent_id": str(agent_id),
            "daily_usage_limit_units": 1000,
            "per_invocation_allowance_units": 100,
        },
    )
    assert static_denied.status_code == 401


@pytest.mark.integration
def test_legacy_usage_limits_initialize_once_and_drive_readiness(
    runtime_client: TestClient, runtime_database_url: str
) -> None:
    tenant_id, agent_id = _tenant_and_agent(runtime_client, "legacy usage")
    created = _create(runtime_client, tenant_id, agent_id)
    principal_id = created["principal"]["principal_id"]
    credential_id = created["credential"]["credential_id"]

    async def prepare_legacy() -> None:
        engine = create_async_engine(runtime_database_url)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE runtime_principals SET daily_usage_limit_units = NULL, "
                    "per_invocation_allowance_units = NULL WHERE principal_id = :principal_id"
                ),
                {"principal_id": principal_id},
            )
        await engine.dispose()

    asyncio.run(prepare_legacy())
    before = runtime_client.get(f"/api/v1/management/runtime-principals/{principal_id}")
    assert before.status_code == 200
    assert before.json()["daily_usage_limit_units"] is None
    assert before.json()["per_invocation_allowance_units"] is None
    assert before.json()["cutover_ready"] is False

    initialized = runtime_client.put(
        f"/api/v1/management/runtime-principals/{principal_id}/usage-limits",
        json={
            "daily_usage_limit_units": 2000,
            "per_invocation_allowance_units": 200,
        },
    )
    assert initialized.status_code == 200, initialized.text
    assert initialized.json()["cutover_ready"] is True
    assert initialized.json()["daily_usage_limit_units"] == 2000
    replay = runtime_client.put(
        f"/api/v1/management/runtime-principals/{principal_id}/usage-limits",
        json={
            "daily_usage_limit_units": 2000,
            "per_invocation_allowance_units": 200,
        },
    )
    assert replay.status_code == 409

    async def make_credential_unusable() -> tuple[int, int]:
        engine = create_async_engine(runtime_database_url)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE runtime_credentials SET revoked_at = now() "
                    "WHERE credential_id = :credential_id"
                ),
                {"credential_id": credential_id},
            )
            action_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM management_audit_records "
                    "WHERE action = 'runtime_principal_usage_limits_initialized' "
                    "AND resource_id = :principal_id"
                ),
                {"principal_id": principal_id},
            )
            secret_columns = await connection.scalar(
                text(
                    "SELECT count(*) FROM information_schema.columns "
                    "WHERE table_name = 'runtime_principals' "
                    "AND column_name IN ('secret_verifier', 'bearer_token')"
                )
            )
        await engine.dispose()
        return int(action_count or 0), int(secret_columns or 0)

    action_count, secret_columns = asyncio.run(make_credential_unusable())
    assert action_count == 1
    assert secret_columns == 0
    after_revoke = runtime_client.get(f"/api/v1/management/runtime-principals/{principal_id}")
    assert after_revoke.json()["cutover_ready"] is False
    assert "credential" not in after_revoke.json()


@pytest.mark.integration
def test_usage_limit_validation_and_disabled_initialization_rejection(
    runtime_client: TestClient, runtime_database_url: str
) -> None:
    tenant_id, agent_id = _tenant_and_agent(runtime_client, "invalid usage")
    invalid = runtime_client.post(
        "/api/v1/management/runtime-principals",
        json={
            "tenant_id": str(tenant_id),
            "agent_id": str(agent_id),
            "daily_usage_limit_units": 100,
            "per_invocation_allowance_units": 101,
        },
    )
    assert invalid.status_code == 422

    created = _create(runtime_client, tenant_id, agent_id)
    principal_id = created["principal"]["principal_id"]

    async def make_legacy() -> None:
        engine = create_async_engine(runtime_database_url)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "UPDATE runtime_principals SET daily_usage_limit_units = NULL, "
                    "per_invocation_allowance_units = NULL WHERE principal_id = :principal_id"
                ),
                {"principal_id": principal_id},
            )
        await engine.dispose()

    asyncio.run(make_legacy())
    assert (
        runtime_client.post(
            f"/api/v1/management/runtime-principals/{principal_id}/disable"
        ).status_code
        == 200
    )
    rejected = runtime_client.put(
        f"/api/v1/management/runtime-principals/{principal_id}/usage-limits",
        json={
            "daily_usage_limit_units": 2000,
            "per_invocation_allowance_units": 200,
        },
    )
    assert rejected.status_code == 404


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cutover_readiness_uses_one_clock_and_excludes_expiry_boundary(
    runtime_client: TestClient, runtime_database_url: str
) -> None:
    tenant_id, agent_id = _tenant_and_agent(runtime_client, "readiness clock")
    created = _create(runtime_client, tenant_id, agent_id)
    principal_id = UUID(created["principal"]["principal_id"])
    credential_id = UUID(created["credential"]["credential_id"])
    fixed_now = datetime.now(UTC) + timedelta(days=1)
    root_id = cast(FastAPI, runtime_client.app).state.test_management_principal_id
    actor = RuntimeIdentityActor(root_id, True)
    engine = create_async_engine(runtime_database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    identity = RuntimeIdentityService(
        partial(SqlAlchemyRuntimeIdentityUnitOfWork, sessions),
        pepper="runtime-pepper-distinct-and-at-least-32-bytes",
        clock=lambda: fixed_now,
    )

    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE runtime_credentials SET expires_at = :expires_at "
                "WHERE credential_id = :credential_id"
            ),
            {"expires_at": fixed_now, "credential_id": credential_id},
        )
    at_boundary = await identity.get_principal(actor, principal_id)
    assert at_boundary.cutover_ready is False

    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE runtime_credentials SET expires_at = :expires_at "
                "WHERE credential_id = :credential_id"
            ),
            {
                "expires_at": fixed_now + timedelta(microseconds=1),
                "credential_id": credential_id,
            },
        )
    just_after = await identity.get_principal(actor, principal_id)
    assert just_after.cutover_ready is True
    await engine.dispose()


class _FailingAudit:
    async def append(self, record: object) -> None:
        del record
        raise RuntimeError("simulated Runtime identity audit failure")


class _AuditFailingRuntimeIdentityUow(SqlAlchemyRuntimeIdentityUnitOfWork):
    @property
    def audits(self) -> _FailingAudit:
        return _FailingAudit()


class _FailingCredentialRepository:
    async def add(self, credential: RuntimeCredential) -> None:
        del credential
        raise RuntimeError("simulated Runtime credential persistence failure")

    async def get(self, credential_id: UUID) -> RuntimeCredential | None:
        del credential_id
        raise AssertionError("get must not be called")

    async def revoke(self, credential: RuntimeCredential) -> None:
        del credential
        raise AssertionError("revoke must not be called")

    async def has_potentially_usable(self, principal_id: UUID, now: object) -> bool:
        del principal_id, now
        raise AssertionError("has_potentially_usable must not be called")


class _CredentialFailingRuntimeIdentityUow(SqlAlchemyRuntimeIdentityUnitOfWork):
    @property
    def credentials(self) -> _FailingCredentialRepository:
        return _FailingCredentialRepository()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_every_runtime_identity_mutation_rolls_back_when_audit_fails(
    runtime_client: TestClient, runtime_database_url: str
) -> None:
    tenant_id, agent_id = _tenant_and_agent(runtime_client, "atomic")
    created = _create(runtime_client, tenant_id, agent_id)
    principal_id = UUID(created["principal"]["principal_id"])
    initial_id = UUID(created["credential"]["credential_id"])
    root_id = cast(FastAPI, runtime_client.app).state.test_management_principal_id
    actor = RuntimeIdentityActor(root_id, True)

    engine = create_async_engine(runtime_database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "UPDATE runtime_principals SET daily_usage_limit_units = NULL, "
                "per_invocation_allowance_units = NULL WHERE principal_id = :principal_id"
            ),
            {"principal_id": principal_id},
        )
    failing = RuntimeIdentityService(
        partial(_AuditFailingRuntimeIdentityUow, sessions),
        pepper="runtime-pepper-distinct-and-at-least-32-bytes",
    )

    with pytest.raises(RuntimeError, match="audit failure"):
        await failing.create_principal(
            CreateRuntimePrincipalCommand(actor, tenant_id, agent_id, 1000, 100, None, None)
        )
    with pytest.raises(RuntimeError, match="audit failure"):
        await failing.initialize_usage_limits(
            InitializeRuntimeUsageLimitsCommand(actor, principal_id, 2000, 200)
        )
    with pytest.raises(RuntimeError, match="audit failure"):
        await failing.issue_credential(
            IssueRuntimeCredentialCommand(actor, principal_id, "must rollback", None)
        )
    with pytest.raises(RuntimeError, match="audit failure"):
        await failing.revoke_credential(RuntimeCredentialCommand(actor, principal_id, initial_id))
    with pytest.raises(RuntimeError, match="audit failure"):
        await failing.disable_principal(actor, principal_id)

    async with sessions() as session:
        assert await session.scalar(text("SELECT count(*) FROM runtime_principals")) == 1
        assert await session.scalar(text("SELECT count(*) FROM runtime_credentials")) == 1
        assert await session.scalar(
            text(
                "SELECT revoked_at IS NULL FROM runtime_credentials "
                "WHERE credential_id = :credential_id"
            ),
            {"credential_id": initial_id},
        )
        assert await session.scalar(
            text(
                "SELECT disabled_at IS NULL FROM runtime_principals "
                "WHERE principal_id = :principal_id"
            ),
            {"principal_id": principal_id},
        )
        assert (
            await session.scalar(
                text(
                    "SELECT daily_usage_limit_units IS NULL "
                    "FROM runtime_principals WHERE principal_id = :principal_id"
                ),
                {"principal_id": principal_id},
            )
            is True
        )
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_initial_credential_failure_does_not_strand_runtime_principal(
    runtime_client: TestClient, runtime_database_url: str
) -> None:
    tenant_id, agent_id = _tenant_and_agent(runtime_client, "credential failure")
    root_id = cast(FastAPI, runtime_client.app).state.test_management_principal_id
    engine = create_async_engine(runtime_database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    service = RuntimeIdentityService(
        partial(_CredentialFailingRuntimeIdentityUow, sessions),
        pepper="runtime-pepper-distinct-and-at-least-32-bytes",
    )

    with pytest.raises(RuntimeError, match="credential persistence failure"):
        await service.create_principal(
            CreateRuntimePrincipalCommand(
                RuntimeIdentityActor(root_id, True),
                tenant_id,
                agent_id,
                1000,
                100,
                None,
                None,
            )
        )

    async with sessions() as session:
        assert await session.scalar(text("SELECT count(*) FROM runtime_principals")) == 0
        assert await session.scalar(text("SELECT count(*) FROM runtime_credentials")) == 0
    await engine.dispose()
