from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from valor.management_audit.domain.audit_record import ManagementAuditRecord


class ManagementAuditRecordResponse(BaseModel):
    audit_id: UUID
    principal_id: str
    tenant_id: UUID | None
    action: str
    resource_type: str
    resource_id: UUID
    outcome: str
    occurred_at: datetime
    before_fingerprint: str | None
    after_fingerprint: str | None

    @classmethod
    def from_domain(cls, record: ManagementAuditRecord) -> "ManagementAuditRecordResponse":
        return cls(
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
