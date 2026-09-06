from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from valor.management_identity.domain.authentication_evidence import (
    ManagementAuthenticationEvidence,
    ManagementAuthenticationOutcome,
)
from valor.management_identity.infrastructure.models import ManagementAuthenticationEvidenceRow


class PostgresManagementAuthenticationEvidenceReader:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_evidence(
        self,
        *,
        credential_id: UUID | None,
        principal_id: UUID | None,
        start: datetime,
        end: datetime,
        limit: int,
    ) -> Sequence[ManagementAuthenticationEvidence]:
        statement = (
            select(ManagementAuthenticationEvidenceRow)
            .where(ManagementAuthenticationEvidenceRow.first_observed_at >= start)
            .where(ManagementAuthenticationEvidenceRow.first_observed_at < end)
            .order_by(
                ManagementAuthenticationEvidenceRow.first_observed_at.desc(),
                ManagementAuthenticationEvidenceRow.credential_id.asc(),
                ManagementAuthenticationEvidenceRow.outcome.asc(),
            )
            .limit(limit)
        )
        if credential_id is not None:
            statement = statement.where(
                ManagementAuthenticationEvidenceRow.credential_id == credential_id
            )
        if principal_id is not None:
            statement = statement.where(
                ManagementAuthenticationEvidenceRow.principal_id == principal_id
            )
        async with self._session_factory() as session:
            rows = await session.scalars(statement)
            return tuple(_from_row(row) for row in rows)


def _from_row(row: ManagementAuthenticationEvidenceRow) -> ManagementAuthenticationEvidence:
    return ManagementAuthenticationEvidence(
        row.credential_id,
        row.principal_id,
        ManagementAuthenticationOutcome(row.outcome),
        row.bucket_started_at,
        row.first_observed_at,
    )
