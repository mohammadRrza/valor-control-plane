from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from valor.management_identity.application.credential_inventory import (
    CredentialInventoryRead,
    CredentialInventoryRecord,
)
from valor.management_identity.infrastructure.models import (
    ManagementCredentialRow,
    ManagementPrincipalRow,
)


class PostgresManagementCredentialInventoryReader:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_for_principal(
        self, *, principal_id: UUID, limit: int
    ) -> CredentialInventoryRead | None:
        async with self._session_factory() as session:
            principal = await session.get(ManagementPrincipalRow, principal_id)
            if principal is None:
                return None
            rows = await session.scalars(
                select(ManagementCredentialRow)
                .where(ManagementCredentialRow.principal_id == principal_id)
                .order_by(
                    ManagementCredentialRow.created_at.desc(),
                    ManagementCredentialRow.credential_id.desc(),
                )
                .limit(limit)
            )
            return CredentialInventoryRead(
                principal.disabled_at is not None,
                tuple(
                    CredentialInventoryRecord(
                        row.credential_id,
                        row.principal_id,
                        row.label,
                        row.created_at,
                        row.expires_at,
                        row.revoked_at,
                    )
                    for row in rows
                ),
            )
