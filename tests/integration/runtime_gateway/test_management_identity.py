import asyncio
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import cast
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tests.integration.management_helpers import BOOTSTRAP_TOKEN, PEPPER
from valor.management_identity.application.errors import BootstrapAlreadyCompleted
from valor.management_identity.application.handlers import (
    BootstrapCommand,
    CreatePrincipalCommand,
    ManagementActor,
    ManagementIdentityService,
)
from valor.management_identity.infrastructure.unit_of_work import (
    SqlAlchemyManagementIdentityUnitOfWork,
)


def _create_principal(
    client: TestClient,
    *,
    name: str = "Second Operator",
    tenant_ids: set[UUID] | None = None,
    manager: bool = False,
) -> UUID:
    response = client.post(
        "/api/v1/management/principals",
        json={
            "display_name": name,
            "tenant_ids": [str(value) for value in tenant_ids or set()],
            "can_manage_principals": manager,
        },
    )
    assert response.status_code == 201, response.text
    return UUID(response.json()["principal_id"])


def _issue(client: TestClient, principal_id: UUID, label: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/management/principals/{principal_id}/credentials",
        json={"label": label},
    )
    assert response.status_code == 201, response.text
    return cast(dict[str, object], response.json())


@pytest.mark.integration
def test_rotation_revocation_preserves_principal_identity_and_audit(
    runtime_client: TestClient,
) -> None:
    tenant = UUID(runtime_client.post("/api/v1/tenants", json={"name": "Rotation"}).json()["id"])
    principal_id = _create_principal(runtime_client, tenant_ids={tenant})
    first = _issue(runtime_client, principal_id, "deployment-a")
    second = _issue(runtime_client, principal_id, "deployment-b")
    first_token, second_token = str(first["bearer_token"]), str(second["bearer_token"])

    path = f"/api/v1/tenants/{tenant}"
    assert (
        runtime_client.get(path, headers={"Authorization": f"Bearer {first_token}"}).status_code
        == 200
    )
    assert (
        runtime_client.get(path, headers={"Authorization": f"Bearer {second_token}"}).status_code
        == 200
    )
    assert (
        runtime_client.put(
            f"/api/v1/management/principals/{principal_id}/tenant-scopes",
            json={"tenant_ids": []},
        ).status_code
        == 200
    )
    assert (
        runtime_client.get(path, headers={"Authorization": f"Bearer {second_token}"}).status_code
        == 404
    )
    assert (
        runtime_client.put(
            f"/api/v1/management/principals/{principal_id}/tenant-scopes",
            json={"tenant_ids": [str(tenant)]},
        ).status_code
        == 200
    )
    revoked = runtime_client.post(
        f"/api/v1/management/principals/{principal_id}/credentials/{first['credential_id']}/revoke"
    )
    assert revoked.status_code == 200
    assert (
        runtime_client.get(path, headers={"Authorization": f"Bearer {first_token}"}).status_code
        == 401
    )
    assert (
        runtime_client.get(path, headers={"Authorization": f"Bearer {second_token}"}).status_code
        == 200
    )

    asset_headers = {"Authorization": f"Bearer {second_token}"}
    agent = runtime_client.post(
        "/api/v1/agents",
        headers=asset_headers,
        json={"tenant_id": str(tenant), "name": "Rotated Agent"},
    ).json()
    model = runtime_client.post(
        "/api/v1/models",
        headers=asset_headers,
        json={
            "tenant_id": str(tenant),
            "name": "Rotated Model",
            "provider": "openai",
            "provider_model_reference": "gpt-rotation",
        },
    ).json()
    assert (
        runtime_client.put(
            "/api/v1/policies/agent-model-permissions",
            headers=asset_headers,
            json={
                "tenant_id": str(tenant),
                "agent_id": agent["id"],
                "model_id": model["id"],
                "effect": "allow",
            },
        ).status_code
        == 200
    )

    app = cast(FastAPI, runtime_client.app)
    assert str(principal_id) != str(app.state.test_management_principal_id)
    now = datetime.now(UTC)
    audit = runtime_client.get(
        f"/api/v1/tenants/{tenant}/audit-records",
        headers=asset_headers,
        params={
            "start": (now - timedelta(days=1)).isoformat(),
            "end": (now + timedelta(days=1)).isoformat(),
        },
    ).json()
    assert audit[0]["principal_id"] == str(principal_id)


@pytest.mark.integration
def test_disable_invalidates_all_credentials(runtime_client: TestClient) -> None:
    principal_id = _create_principal(runtime_client)
    first = _issue(runtime_client, principal_id, "one")
    second = _issue(runtime_client, principal_id, "two")
    response = runtime_client.post(f"/api/v1/management/principals/{principal_id}/disable")
    assert response.status_code == 200
    for issued in (first, second):
        authentication = runtime_client.get(
            f"/api/v1/management/principals/{principal_id}",
            headers={"Authorization": f"Bearer {issued['bearer_token']}"},
        )
        assert authentication.status_code == 401


@pytest.mark.integration
def test_last_recoverable_manager_cannot_be_disabled_or_revoked(
    runtime_client: TestClient,
) -> None:
    app = cast(FastAPI, runtime_client.app)
    root_id: UUID = app.state.test_management_principal_id
    credential_id = UUID(runtime_client.headers["Authorization"].split("_")[2])
    assert (
        runtime_client.post(f"/api/v1/management/principals/{root_id}/disable").status_code == 409
    )
    assert (
        runtime_client.post(
            f"/api/v1/management/principals/{root_id}/credentials/{credential_id}/revoke"
        ).status_code
        == 409
    )
    replacement_manager = _create_principal(runtime_client, name="Recovery Manager", manager=True)
    _issue(runtime_client, replacement_manager, "recovery")
    assert (
        runtime_client.post(f"/api/v1/management/principals/{root_id}/disable").status_code == 200
    )


@pytest.mark.integration
def test_bootstrap_is_one_time_and_secret_is_returned_only_on_issue(
    runtime_client: TestClient, runtime_database_url: str
) -> None:
    repeated = runtime_client.post(
        "/api/v1/management/bootstrap",
        headers={"Authorization": f"Bearer {BOOTSTRAP_TOKEN}"},
        json={"display_name": "Second Bootstrap", "tenant_ids": []},
    )
    assert repeated.status_code == 401
    principal_id = _create_principal(runtime_client)
    issued = _issue(runtime_client, principal_id, "one-time")
    metadata = runtime_client.get(f"/api/v1/management/principals/{principal_id}").json()
    assert "bearer_token" not in metadata
    token = str(issued["bearer_token"])

    async def verifier_is_not_token() -> None:
        engine = create_async_engine(runtime_database_url)
        async with engine.connect() as connection:
            verifier = await connection.scalar(
                text(
                    "SELECT secret_verifier FROM management_credentials "
                    "WHERE credential_id = :credential_id"
                ),
                {"credential_id": issued["credential_id"]},
            )
            audit_count = await connection.scalar(
                text(
                    "SELECT count(*) FROM management_audit_records "
                    "WHERE action = 'management_credential_issued' "
                    "AND resource_id = :credential_id"
                ),
                {"credential_id": issued["credential_id"]},
            )
        await engine.dispose()
        assert verifier != token
        assert token not in str(verifier)
        assert audit_count == 1

    asyncio.run(verifier_is_not_token())


@pytest.mark.integration
def test_invalid_bootstrap_secret_is_generic_unauthorized(
    unauthenticated_runtime_client: TestClient,
) -> None:
    response = unauthenticated_runtime_client.post(
        "/api/v1/management/bootstrap",
        headers={"Authorization": "Bearer wrong-bootstrap-secret"},
        json={"display_name": "Invalid Bootstrap", "tenant_ids": []},
    )
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["detail"] == "Authentication credentials are missing or invalid."
    assert "wrong-bootstrap-secret" not in response.text


@pytest.mark.integration
def test_authentication_evidence_is_secret_free_attributable_and_hourly_bounded(
    runtime_client: TestClient, runtime_database_url: str
) -> None:
    principal_id = _create_principal(runtime_client, name="Evidence Operator")
    issued = _issue(runtime_client, principal_id, "evidence credential")
    credential_id = UUID(str(issued["credential_id"]))
    token = str(issued["bearer_token"])
    path = f"/api/v1/management/principals/{principal_id}"
    valid_headers = {"Authorization": f"Bearer {token}"}
    invalid_token = token.rsplit("_", 1)[0] + "_incorrect-secret"

    async def insert_expired_bucket() -> None:
        engine = create_async_engine(runtime_database_url)
        old = datetime.now(UTC) - timedelta(days=91)
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO management_authentication_evidence "
                    "(credential_id, principal_id, outcome, bucket_started_at, "
                    "first_observed_at) VALUES "
                    "(:credential_id, :principal_id, 'succeeded', :bucket, :observed)"
                ),
                {
                    "credential_id": credential_id,
                    "principal_id": principal_id,
                    "bucket": old.replace(minute=0, second=0, microsecond=0),
                    "observed": old,
                },
            )
        await engine.dispose()

    asyncio.run(insert_expired_bucket())

    for _ in range(3):
        assert runtime_client.get(path, headers=valid_headers).status_code == 404
        invalid = runtime_client.get(path, headers={"Authorization": f"Bearer {invalid_token}"})
        assert invalid.status_code == 401
        assert invalid.headers["WWW-Authenticate"] == "Bearer"
        assert invalid.json()["detail"] == "Authentication credentials are missing or invalid."

    unknown = f"valor_mgmt_aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa_{token[-20:]}"
    assert (
        runtime_client.get(path, headers={"Authorization": f"Bearer {unknown}"}).status_code == 401
    )
    assert runtime_client.get(path, headers={"Authorization": "Bearer garbage"}).status_code == 401

    async def read_rows() -> list[tuple[str, int, int]]:
        engine = create_async_engine(runtime_database_url)
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT outcome, count(*), count(DISTINCT bucket_started_at) "
                    "FROM management_authentication_evidence "
                    "WHERE credential_id = :credential_id GROUP BY outcome ORDER BY outcome"
                ),
                {"credential_id": credential_id},
            )
            rows = [(str(row[0]), int(row[1]), int(row[2])) for row in result]
            serialized = await connection.scalar(
                text(
                    "SELECT string_agg(row_to_json(e)::text, '') "
                    "FROM management_authentication_evidence e "
                    "WHERE credential_id = :credential_id"
                ),
                {"credential_id": credential_id},
            )
        await engine.dispose()
        assert token not in str(serialized)
        assert invalid_token not in str(serialized)
        return rows

    assert asyncio.run(read_rows()) == [
        ("credential_mismatch", 1, 1),
        ("succeeded", 1, 1),
    ]


class _FailingAudit:
    async def append(self, record: object) -> None:
        del record
        raise RuntimeError("simulated identity audit failure")


class _AuditFailingIdentityUow(SqlAlchemyManagementIdentityUnitOfWork):
    @property
    def audits(self) -> _FailingAudit:
        return _FailingAudit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_identity_audit_failure_rolls_back_principal_creation(
    runtime_client: TestClient, runtime_database_url: str
) -> None:
    app = cast(FastAPI, runtime_client.app)
    root_id: UUID = app.state.test_management_principal_id
    engine = create_async_engine(runtime_database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    service = ManagementIdentityService(
        partial(_AuditFailingIdentityUow, sessions),
        pepper=PEPPER,
        bootstrap_token=BOOTSTRAP_TOKEN,
    )
    with pytest.raises(RuntimeError, match="simulated identity audit failure"):
        await service.create_principal(
            CreatePrincipalCommand(
                ManagementActor(root_id, True), "Must Roll Back", frozenset(), False
            )
        )
    async with sessions() as session:
        count = await session.scalar(
            text("SELECT count(*) FROM management_principals WHERE display_name = 'Must Roll Back'")
        )
        assert count == 0
    await engine.dispose()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_concurrent_bootstrap_commits_exactly_one_first_principal(
    runtime_database_url: str,
) -> None:
    engine = create_async_engine(runtime_database_url)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    factory = partial(SqlAlchemyManagementIdentityUnitOfWork, sessions)
    service_a = ManagementIdentityService(factory, pepper=PEPPER, bootstrap_token=BOOTSTRAP_TOKEN)
    service_b = ManagementIdentityService(factory, pepper=PEPPER, bootstrap_token=BOOTSTRAP_TOKEN)
    command = BootstrapCommand(BOOTSTRAP_TOKEN, "Concurrent Bootstrap", frozenset())
    results = await asyncio.gather(
        service_a.bootstrap(command), service_b.bootstrap(command), return_exceptions=True
    )
    assert sum(not isinstance(result, BaseException) for result in results) == 1
    assert sum(isinstance(result, BootstrapAlreadyCompleted) for result in results) == 1
    async with sessions() as session:
        assert await session.scalar(text("SELECT count(*) FROM management_principals")) == 1
        assert await session.scalar(text("SELECT count(*) FROM management_credentials")) == 1
    await engine.dispose()


@pytest.mark.integration
def test_invalid_expiry_and_non_manager_capability_are_sanitized(
    runtime_client: TestClient,
) -> None:
    principal_id = _create_principal(runtime_client)
    expired = runtime_client.post(
        f"/api/v1/management/principals/{principal_id}/credentials",
        json={"expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()},
    )
    assert expired.status_code == 422
    issued = _issue(runtime_client, principal_id, "ordinary")
    denied = runtime_client.post(
        "/api/v1/management/principals",
        headers={"Authorization": f"Bearer {issued['bearer_token']}"},
        json={"display_name": "Escalation", "tenant_ids": []},
    )
    assert denied.status_code == 404
