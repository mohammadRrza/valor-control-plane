from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from valor.infrastructure.sqlalchemy import SqlAlchemyBase


class AgentModelPermissionRow(SqlAlchemyBase):
    __tablename__ = "agent_model_permissions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "agent_id", "model_id", name="uq_permissions_tenant_agent_model"
        ),
        CheckConstraint("effect IN ('allow', 'deny')", name="ck_permissions_effect"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", name="fk_permissions_tenant_id_tenants"), nullable=False
    )
    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", name="fk_permissions_agent_id_agents"), nullable=False
    )
    model_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.id", name="fk_permissions_model_id_models"), nullable=False
    )
    effect: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class PolicyDecisionRow(SqlAlchemyBase):
    __tablename__ = "policy_decisions"
    __table_args__ = (
        CheckConstraint("effect IN ('allow', 'deny')", name="ck_policy_decisions_effect"),
        Index("ix_policy_decisions_invocation_id", "invocation_id", unique=True),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    invocation_id: Mapped[UUID] = mapped_column(nullable=False)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", name="fk_policy_decisions_tenant_id_tenants"), nullable=False
    )
    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", name="fk_policy_decisions_agent_id_agents"), nullable=False
    )
    model_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.id", name="fk_policy_decisions_model_id_models"), nullable=False
    )
    permission_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "agent_model_permissions.id",
            name="fk_policy_decisions_permission_id_permissions",
        ),
        nullable=True,
    )
    effect: Mapped[str] = mapped_column(String(10), nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
