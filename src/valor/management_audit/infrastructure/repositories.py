from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from valor.identity_tenancy.infrastructure.models import TenantRow
from valor.management_audit.application.query import ManagementAuditUnavailable
from valor.management_audit.domain.audit_record import (
    ManagementAuditAction,
    ManagementAuditOutcome,
    ManagementAuditRecord,
    ManagementAuditResourceType,
)
from valor.management_audit.infrastructure.models import ManagementAuditRecordRow


def record_from_row(row: ManagementAuditRecordRow) -> ManagementAuditRecord:
    return ManagementAuditRecord(
        row.audit_id,
        row.principal_id,
        row.tenant_id,
        ManagementAuditAction(row.action),
        ManagementAuditResourceType(row.resource_type),
        row.resource_id,
        ManagementAuditOutcome(row.outcome),
        row.occurred_at,
        row.before_fingerprint,
        row.after_fingerprint,
    )


class SqlAlchemyManagementAuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(self, record: ManagementAuditRecord) -> None:
        self._session.add(
            ManagementAuditRecordRow(
                audit_id=record.audit_id,
                principal_id=record.principal_id,
                tenant_id=record.tenant_id,
                action=record.action.value,
                resource_type=record.resource_type.value,
                resource_id=record.resource_id,
                outcome=record.outcome.value,
                occurred_at=record.occurred_at,
                before_fingerprint=record.before_fingerprint,
                after_fingerprint=record.after_fingerprint,
            )
        )
        await self._session.flush()


class PostgresManagementAuditReader:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def tenant_exists(self, tenant_id: UUID) -> bool:
        try:
            async with self._sessions() as session:
                return (
                    await session.scalar(select(TenantRow.id).where(TenantRow.id == tenant_id))
                    is not None
                )
        except SQLAlchemyError as error:
            raise ManagementAuditUnavailable from error

    async def list_for_tenant(
        self, *, tenant_id: UUID, start: datetime, end: datetime, limit: int
    ) -> Sequence[ManagementAuditRecord]:
        statement = (
            select(ManagementAuditRecordRow)
            .where(
                ManagementAuditRecordRow.tenant_id == tenant_id,
                ManagementAuditRecordRow.occurred_at >= start,
                ManagementAuditRecordRow.occurred_at < end,
            )
            .order_by(
                ManagementAuditRecordRow.occurred_at.desc(),
                ManagementAuditRecordRow.audit_id.desc(),
            )
            .limit(limit)
        )
        try:
            async with self._sessions() as session:
                return tuple(record_from_row(row) for row in (await session.scalars(statement)))
        except SQLAlchemyError as error:
            raise ManagementAuditUnavailable from error
