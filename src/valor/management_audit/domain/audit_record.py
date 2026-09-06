from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class ManagementAuditAction(StrEnum):
    AGENT_MODEL_PERMISSION_SET = "agent_model_permission_set"
    MANAGEMENT_PRINCIPAL_CREATED = "management_principal_created"
    MANAGEMENT_CREDENTIAL_ISSUED = "management_credential_issued"
    MANAGEMENT_CREDENTIAL_REVOKED = "management_credential_revoked"
    MANAGEMENT_PRINCIPAL_DISABLED = "management_principal_disabled"
    MANAGEMENT_PRINCIPAL_SCOPES_SET = "management_principal_scopes_set"


class ManagementAuditResourceType(StrEnum):
    AGENT_MODEL_PERMISSION = "agent_model_permission"
    MANAGEMENT_PRINCIPAL = "management_principal"
    MANAGEMENT_CREDENTIAL = "management_credential"


class ManagementAuditOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ManagementAuditRecord:
    audit_id: UUID
    principal_id: str
    tenant_id: UUID | None
    action: ManagementAuditAction
    resource_type: ManagementAuditResourceType
    resource_id: UUID
    outcome: ManagementAuditOutcome
    occurred_at: datetime
    before_fingerprint: str | None
    after_fingerprint: str | None

    def __post_init__(self) -> None:
        if not self.principal_id.strip():
            raise ValueError("principal_id must not be empty")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        for fingerprint in (self.before_fingerprint, self.after_fingerprint):
            if fingerprint is not None and (
                len(fingerprint) != 64
                or fingerprint.lower() != fingerprint
                or any(character not in "0123456789abcdef" for character in fingerprint)
            ):
                raise ValueError("fingerprints must be lowercase SHA-256 hex digests")
        if self.outcome is ManagementAuditOutcome.SUCCEEDED and self.after_fingerprint is None:
            raise ValueError("successful audit records require an after fingerprint")
