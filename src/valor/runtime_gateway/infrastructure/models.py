"""SQLAlchemy persistence representation for completed Invocations."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from valor.infrastructure.sqlalchemy import SqlAlchemyBase


class InvocationRow(SqlAlchemyBase):
    __tablename__ = "invocations"
    __table_args__ = (
        CheckConstraint(
            "(status = 'succeeded' AND output_text IS NOT NULL) OR "
            "(status IN ('failed', 'denied') AND output_text IS NULL)",
            name="ck_invocations_status_output",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", name="fk_invocations_tenant_id_tenants"), nullable=False
    )
    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agents.id", name="fk_invocations_agent_id_agents"), nullable=False
    )
    model_id: Mapped[UUID] = mapped_column(
        ForeignKey("models.id", name="fk_invocations_model_id_models"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    policy_decision_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "policy_decisions.id",
            name="fk_invocations_policy_decision_id_policy_decisions",
        ),
        nullable=True,
    )
    runtime_principal_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
