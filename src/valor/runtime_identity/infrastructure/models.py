from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from valor.infrastructure.sqlalchemy import SqlAlchemyBase


class RuntimePrincipalRow(SqlAlchemyBase):
    __tablename__ = "runtime_principals"
    __table_args__ = (
        CheckConstraint(
            "(daily_usage_limit_units IS NULL AND per_invocation_allowance_units IS NULL) OR "
            "(daily_usage_limit_units IS NOT NULL AND "
            "per_invocation_allowance_units IS NOT NULL)",
            name="ck_runtime_principal_usage_limits_together",
        ),
        CheckConstraint(
            "daily_usage_limit_units IS NULL OR daily_usage_limit_units > 0",
            name="ck_runtime_principal_daily_usage_limit_positive",
        ),
        CheckConstraint(
            "per_invocation_allowance_units IS NULL OR per_invocation_allowance_units > 0",
            name="ck_runtime_principal_allowance_positive",
        ),
        CheckConstraint(
            "daily_usage_limit_units IS NULL OR "
            "per_invocation_allowance_units <= daily_usage_limit_units",
            name="ck_runtime_principal_allowance_within_limit",
        ),
        CheckConstraint(
            "(legacy_runtime_principal_id IS NULL AND identity_continuity_bound_at IS NULL) OR "
            "(legacy_runtime_principal_id IS NOT NULL AND "
            "identity_continuity_bound_at IS NOT NULL)",
            name="ck_runtime_principal_continuity_together",
        ),
        CheckConstraint(
            "legacy_runtime_principal_id IS NULL OR length(btrim(legacy_runtime_principal_id)) > 0",
            name="ck_runtime_principal_legacy_id_nonblank",
        ),
        Index("ix_runtime_principals_binding", "tenant_id", "agent_id"),
        Index(
            "uq_runtime_principals_legacy_identity",
            "legacy_runtime_principal_id",
            unique=True,
        ),
    )
    principal_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", name="fk_runtime_principal_tenant"), nullable=False
    )
    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", name="fk_runtime_principal_agent"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    daily_usage_limit_units: Mapped[int | None] = mapped_column(Integer)
    per_invocation_allowance_units: Mapped[int | None] = mapped_column(Integer)
    legacy_runtime_principal_id: Mapped[str | None] = mapped_column(String(255))
    identity_continuity_bound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RuntimeCredentialRow(SqlAlchemyBase):
    __tablename__ = "runtime_credentials"
    __table_args__ = (
        CheckConstraint(
            "secret_verifier ~ '^[0-9a-f]{64}$'", name="ck_runtime_credential_verifier"
        ),
    )
    credential_id: Mapped[UUID] = mapped_column(primary_key=True)
    principal_id: Mapped[UUID] = mapped_column(
        ForeignKey("runtime_principals.principal_id", name="fk_runtime_credential_principal"),
        nullable=False,
        index=True,
    )
    secret_verifier: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str | None] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
