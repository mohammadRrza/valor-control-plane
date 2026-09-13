from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import exists, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from valor.ai_asset_registry.infrastructure.models import AgentRow
from valor.identity_tenancy.infrastructure.models import TenantRow
from valor.runtime_identity.domain.models import RuntimeCredential, RuntimePrincipal
from valor.runtime_identity.infrastructure.models import RuntimeCredentialRow, RuntimePrincipalRow


class SqlAlchemyRuntimePrincipalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, value: RuntimePrincipal) -> None:
        self._session.add(
            RuntimePrincipalRow(
                principal_id=value.principal_id,
                tenant_id=value.tenant_id,
                agent_id=value.agent_id,
                created_at=value.created_at,
                disabled_at=value.disabled_at,
                daily_usage_limit_units=value.daily_usage_limit_units,
                per_invocation_allowance_units=value.per_invocation_allowance_units,
            )
        )
        await self._session.flush()

    async def get(self, principal_id: UUID) -> RuntimePrincipal | None:
        row = await self._session.get(RuntimePrincipalRow, principal_id)
        return (
            None
            if row is None
            else RuntimePrincipal(
                row.principal_id,
                row.tenant_id,
                row.agent_id,
                row.created_at,
                row.disabled_at,
                row.daily_usage_limit_units,
                row.per_invocation_allowance_units,
            )
        )

    async def disable(self, value: RuntimePrincipal) -> None:
        await self._session.execute(
            update(RuntimePrincipalRow)
            .where(RuntimePrincipalRow.principal_id == value.principal_id)
            .values(disabled_at=value.disabled_at)
        )
        await self._session.flush()

    async def initialize_usage_limits(self, value: RuntimePrincipal) -> bool:
        result = await self._session.execute(
            update(RuntimePrincipalRow)
            .where(
                RuntimePrincipalRow.principal_id == value.principal_id,
                RuntimePrincipalRow.daily_usage_limit_units.is_(None),
                RuntimePrincipalRow.per_invocation_allowance_units.is_(None),
            )
            .values(
                daily_usage_limit_units=value.daily_usage_limit_units,
                per_invocation_allowance_units=value.per_invocation_allowance_units,
            )
        )
        await self._session.flush()
        return cast(CursorResult[Any], result).rowcount == 1


class SqlAlchemyRuntimeCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, value: RuntimeCredential) -> None:
        self._session.add(
            RuntimeCredentialRow(
                credential_id=value.credential_id,
                principal_id=value.principal_id,
                secret_verifier=value.secret_verifier,
                label=value.label,
                created_at=value.created_at,
                expires_at=value.expires_at,
                revoked_at=value.revoked_at,
            )
        )
        await self._session.flush()

    async def get(self, credential_id: UUID) -> RuntimeCredential | None:
        row = await self._session.get(RuntimeCredentialRow, credential_id)
        return (
            None
            if row is None
            else RuntimeCredential(
                row.credential_id,
                row.principal_id,
                row.secret_verifier,
                row.label,
                row.created_at,
                row.expires_at,
                row.revoked_at,
            )
        )

    async def revoke(self, value: RuntimeCredential) -> None:
        await self._session.execute(
            update(RuntimeCredentialRow)
            .where(RuntimeCredentialRow.credential_id == value.credential_id)
            .values(revoked_at=value.revoked_at)
        )
        await self._session.flush()

    async def has_potentially_usable(self, principal_id: UUID, now: datetime) -> bool:
        return bool(
            await self._session.scalar(
                select(
                    exists().where(
                        RuntimeCredentialRow.principal_id == principal_id,
                        RuntimeCredentialRow.revoked_at.is_(None),
                        or_(
                            RuntimeCredentialRow.expires_at.is_(None),
                            RuntimeCredentialRow.expires_at > now,
                        ),
                    )
                )
            )
        )


class SqlAlchemyRuntimeBinding:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists(self, tenant_id: UUID, agent_id: UUID) -> bool:
        return (
            await self._session.scalar(
                select(AgentRow.id)
                .join(TenantRow, TenantRow.id == AgentRow.tenant_id)
                .where(AgentRow.id == agent_id, AgentRow.tenant_id == tenant_id)
            )
        ) is not None
