from typing import Protocol

from valor.management_audit.domain.audit_record import ManagementAuditRecord


class ManagementAuditRepository(Protocol):
    async def append(self, record: ManagementAuditRecord) -> None: ...
