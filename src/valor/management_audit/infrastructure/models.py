from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from valor.infrastructure.sqlalchemy import SqlAlchemyBase


class ManagementAuditRecordRow(SqlAlchemyBase):
    __tablename__ = "management_audit_records"
    __table_args__ = (
        CheckConstraint(
            "action IN ('agent_model_permission_set', 'management_principal_created', "
            "'management_credential_issued', 'management_credential_revoked', "
            "'management_principal_disabled', 'management_principal_scopes_set')",
            name="ck_management_audit_action",
        ),
        CheckConstraint(
            "resource_type IN ('agent_model_permission', 'management_principal', "
            "'management_credential')",
            name="ck_management_audit_resource_type",
        ),
        CheckConstraint("outcome IN ('succeeded', 'failed')", name="ck_management_audit_outcome"),
        CheckConstraint(
            "before_fingerprint IS NULL OR before_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_management_audit_before_fingerprint",
        ),
        CheckConstraint(
            "after_fingerprint IS NULL OR after_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_management_audit_after_fingerprint",
        ),
        CheckConstraint(
            "outcome <> 'succeeded' OR after_fingerprint IS NOT NULL",
            name="ck_management_audit_success_after",
        ),
        Index("ix_management_audit_tenant_occurred", "tenant_id", "occurred_at"),
    )

    audit_id: Mapped[UUID] = mapped_column(primary_key=True)
    principal_id: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("tenants.id", name="fk_management_audit_tenant_id_tenants"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    before_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    after_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
