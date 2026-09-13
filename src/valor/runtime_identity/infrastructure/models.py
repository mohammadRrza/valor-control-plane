from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from valor.infrastructure.sqlalchemy import SqlAlchemyBase


class RuntimePrincipalRow(SqlAlchemyBase):
    __tablename__ = "runtime_principals"
    __table_args__ = (Index("ix_runtime_principals_binding", "tenant_id", "agent_id"),)
    principal_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", name="fk_runtime_principal_tenant"), nullable=False
    )
    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", name="fk_runtime_principal_agent"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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
