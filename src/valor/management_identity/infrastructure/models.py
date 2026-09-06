from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from valor.infrastructure.sqlalchemy import SqlAlchemyBase


class ManagementPrincipalRow(SqlAlchemyBase):
    __tablename__ = "management_principals"

    principal_id: Mapped[UUID] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    can_manage_principals: Mapped[bool] = mapped_column(Boolean, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ManagementPrincipalTenantScopeRow(SqlAlchemyBase):
    __tablename__ = "management_principal_tenant_scopes"

    principal_id: Mapped[UUID] = mapped_column(
        ForeignKey("management_principals.principal_id", name="fk_management_scope_principal"),
        primary_key=True,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", name="fk_management_scope_tenant"), primary_key=True
    )


class ManagementCredentialRow(SqlAlchemyBase):
    __tablename__ = "management_credentials"
    __table_args__ = (
        CheckConstraint(
            "secret_verifier ~ '^[0-9a-f]{64}$'", name="ck_management_credential_verifier"
        ),
    )

    credential_id: Mapped[UUID] = mapped_column(primary_key=True)
    principal_id: Mapped[UUID] = mapped_column(
        ForeignKey("management_principals.principal_id", name="fk_management_credential_principal"),
        nullable=False,
        index=True,
    )
    secret_verifier: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ManagementAuthenticationEvidenceRow(SqlAlchemyBase):
    __tablename__ = "management_authentication_evidence"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('succeeded', 'credential_mismatch', 'revoked', 'expired', "
            "'principal_disabled')",
            name="ck_management_authentication_evidence_outcome",
        ),
        Index("ix_management_auth_evidence_bucket", "bucket_started_at"),
        Index(
            "ix_management_auth_evidence_credential_observed",
            "credential_id",
            "first_observed_at",
        ),
        Index(
            "ix_management_auth_evidence_principal_observed",
            "principal_id",
            "first_observed_at",
        ),
    )

    credential_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "management_credentials.credential_id",
            name="fk_management_auth_evidence_credential",
        ),
        primary_key=True,
    )
    principal_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "management_principals.principal_id",
            name="fk_management_auth_evidence_principal",
        ),
        nullable=False,
    )
    outcome: Mapped[str] = mapped_column(String(32), primary_key=True)
    bucket_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
