from collections.abc import Sequence
from datetime import timedelta
from uuid import UUID

from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from valor.identity_tenancy.infrastructure.models import TenantRow
from valor.management_identity.domain.authentication_evidence import (
    ManagementAuthenticationEvidence,
)
from valor.management_identity.domain.models import ManagementCredential, ManagementPrincipal
from valor.management_identity.infrastructure.models import (
    ManagementAuthenticationEvidenceRow,
    ManagementCredentialRow,
    ManagementPrincipalRow,
    ManagementPrincipalTenantScopeRow,
)


class SqlAlchemyManagementAuthenticationEvidenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def observe(self, evidence: ManagementAuthenticationEvidence) -> None:
        await self._session.execute(
            delete(ManagementAuthenticationEvidenceRow).where(
                ManagementAuthenticationEvidenceRow.bucket_started_at
                < evidence.bucket_started_at - timedelta(days=90)
            )
        )
        statement = (
            insert(ManagementAuthenticationEvidenceRow)
            .values(
                credential_id=evidence.credential_id,
                principal_id=evidence.principal_id,
                outcome=evidence.outcome.value,
                bucket_started_at=evidence.bucket_started_at,
                first_observed_at=evidence.first_observed_at,
            )
            .on_conflict_do_nothing(
                index_elements=("credential_id", "outcome", "bucket_started_at")
            )
        )
        await self._session.execute(statement)


class SqlAlchemyManagementPrincipalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, principal: ManagementPrincipal) -> None:
        self._session.add(
            ManagementPrincipalRow(
                principal_id=principal.principal_id,
                display_name=principal.display_name,
                can_manage_principals=principal.can_manage_principals,
                created_at=principal.created_at,
                disabled_at=principal.disabled_at,
            )
        )
        self._session.add_all(
            ManagementPrincipalTenantScopeRow(
                principal_id=principal.principal_id, tenant_id=tenant_id
            )
            for tenant_id in principal.tenant_ids
        )
        await self._session.flush()

    async def get(self, principal_id: UUID) -> ManagementPrincipal | None:
        row = await self._session.get(ManagementPrincipalRow, principal_id)
        if row is None:
            return None
        scopes = frozenset(
            await self._session.scalars(
                select(ManagementPrincipalTenantScopeRow.tenant_id).where(
                    ManagementPrincipalTenantScopeRow.principal_id == principal_id
                )
            )
        )
        return ManagementPrincipal(
            row.principal_id,
            row.display_name,
            row.can_manage_principals,
            scopes,
            row.created_at,
            row.disabled_at,
        )

    async def replace_scopes(self, principal: ManagementPrincipal) -> None:
        await self._session.execute(
            delete(ManagementPrincipalTenantScopeRow).where(
                ManagementPrincipalTenantScopeRow.principal_id == principal.principal_id
            )
        )
        self._session.add_all(
            ManagementPrincipalTenantScopeRow(
                principal_id=principal.principal_id, tenant_id=tenant_id
            )
            for tenant_id in principal.tenant_ids
        )
        await self._session.flush()

    async def disable(self, principal: ManagementPrincipal) -> None:
        await self._session.execute(
            update(ManagementPrincipalRow)
            .where(ManagementPrincipalRow.principal_id == principal.principal_id)
            .values(disabled_at=principal.disabled_at)
        )
        await self._session.flush()

    async def count(self) -> int:
        return int(
            await self._session.scalar(select(func.count(ManagementPrincipalRow.principal_id))) or 0
        )

    async def has_recoverable_manager(self, *, excluding_principal_id: UUID | None = None) -> bool:
        statement = select(
            exists()
            .where(ManagementPrincipalRow.disabled_at.is_(None))
            .where(ManagementPrincipalRow.can_manage_principals.is_(True))
            .where(ManagementCredentialRow.principal_id == ManagementPrincipalRow.principal_id)
            .where(ManagementCredentialRow.revoked_at.is_(None))
            .where(
                or_(
                    ManagementCredentialRow.expires_at.is_(None),
                    ManagementCredentialRow.expires_at > func.now(),
                )
            )
        )
        if excluding_principal_id is not None:
            statement = statement.where(
                ManagementPrincipalRow.principal_id != excluding_principal_id
            )
        return bool(await self._session.scalar(statement))


class SqlAlchemyManagementCredentialRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, credential: ManagementCredential) -> None:
        self._session.add(
            ManagementCredentialRow(
                credential_id=credential.credential_id,
                principal_id=credential.principal_id,
                secret_verifier=credential.secret_verifier,
                label=credential.label,
                created_at=credential.created_at,
                expires_at=credential.expires_at,
                revoked_at=credential.revoked_at,
            )
        )
        await self._session.flush()

    async def get(self, credential_id: UUID) -> ManagementCredential | None:
        row = await self._session.get(ManagementCredentialRow, credential_id)
        return None if row is None else _credential_from_row(row)

    async def list_for_principal(self, principal_id: UUID) -> Sequence[ManagementCredential]:
        rows = await self._session.scalars(
            select(ManagementCredentialRow).where(
                ManagementCredentialRow.principal_id == principal_id
            )
        )
        return tuple(_credential_from_row(row) for row in rows)

    async def revoke(self, credential: ManagementCredential) -> None:
        await self._session.execute(
            update(ManagementCredentialRow)
            .where(ManagementCredentialRow.credential_id == credential.credential_id)
            .values(revoked_at=credential.revoked_at)
        )
        await self._session.flush()

    async def has_usable_for_principal(self, principal_id: UUID) -> bool:
        return bool(
            await self._session.scalar(
                select(
                    exists()
                    .where(ManagementCredentialRow.principal_id == principal_id)
                    .where(ManagementCredentialRow.revoked_at.is_(None))
                    .where(
                        or_(
                            ManagementCredentialRow.expires_at.is_(None),
                            ManagementCredentialRow.expires_at > func.now(),
                        )
                    )
                )
            )
        )


class SqlAlchemyTenantExistence:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def all_exist(self, tenant_ids: frozenset[UUID]) -> bool:
        count = await self._session.scalar(
            select(func.count(TenantRow.id)).where(TenantRow.id.in_(tenant_ids))
        )
        return int(count or 0) == len(tenant_ids)


def _credential_from_row(row: ManagementCredentialRow) -> ManagementCredential:
    return ManagementCredential(
        row.credential_id,
        row.principal_id,
        row.secret_verifier,
        row.label,
        row.created_at,
        row.expires_at,
        row.revoked_at,
    )
