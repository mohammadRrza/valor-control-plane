from datetime import datetime

from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from valor.management_identity.application.principal_inventory import PrincipalInventoryRecord
from valor.management_identity.infrastructure.models import (
    ManagementCredentialRow,
    ManagementPrincipalRow,
    ManagementPrincipalTenantScopeRow,
)


class PostgresManagementPrincipalInventoryReader:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_principals(
        self, *, now: datetime, limit: int
    ) -> tuple[PrincipalInventoryRecord, ...]:
        scope_counts = (
            select(
                ManagementPrincipalTenantScopeRow.principal_id.label("principal_id"),
                func.count().label("tenant_scope_count"),
            )
            .group_by(ManagementPrincipalTenantScopeRow.principal_id)
            .subquery()
        )
        credential_counts = (
            select(
                ManagementCredentialRow.principal_id.label("principal_id"),
                func.count().label("credential_count"),
                func.sum(
                    case(
                        (
                            ManagementCredentialRow.revoked_at.is_(None)
                            & or_(
                                ManagementCredentialRow.expires_at.is_(None),
                                ManagementCredentialRow.expires_at > now,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("conditionally_usable_count"),
            )
            .group_by(ManagementCredentialRow.principal_id)
            .subquery()
        )
        statement = (
            select(
                ManagementPrincipalRow.principal_id,
                ManagementPrincipalRow.display_name,
                ManagementPrincipalRow.can_manage_principals,
                ManagementPrincipalRow.created_at,
                ManagementPrincipalRow.disabled_at,
                func.coalesce(scope_counts.c.tenant_scope_count, 0),
                func.coalesce(credential_counts.c.credential_count, 0),
                case(
                    (ManagementPrincipalRow.disabled_at.is_not(None), 0),
                    else_=func.coalesce(credential_counts.c.conditionally_usable_count, 0),
                ),
            )
            .outerjoin(
                scope_counts,
                scope_counts.c.principal_id == ManagementPrincipalRow.principal_id,
            )
            .outerjoin(
                credential_counts,
                credential_counts.c.principal_id == ManagementPrincipalRow.principal_id,
            )
            .order_by(
                ManagementPrincipalRow.created_at.desc(),
                ManagementPrincipalRow.principal_id.desc(),
            )
            .limit(limit)
        )
        async with self._session_factory() as session:
            rows = (await session.execute(statement)).all()
        return tuple(
            PrincipalInventoryRecord(
                row[0], row[1], row[2], row[3], row[4], int(row[5]), int(row[6]), int(row[7])
            )
            for row in rows
        )
