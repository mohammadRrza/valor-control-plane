"""SQLAlchemy persistence representation for completed Invocations."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from valor.infrastructure.sqlalchemy import SqlAlchemyBase


class InvocationRow(SqlAlchemyBase):
    __tablename__ = "invocations"
    __table_args__ = (
        CheckConstraint(
            "(status = 'succeeded' AND output_text IS NOT NULL) OR "
            "(status IN ('failed', 'denied', 'limited', 'cost_limited') "
            "AND output_text IS NULL)",
            name="ck_invocations_status_output",
        ),
        CheckConstraint("duration_ms >= 0", name="ck_invocations_duration_non_negative"),
        CheckConstraint("input_units >= 0", name="ck_invocations_input_units_non_negative"),
        CheckConstraint("output_units >= 0", name="ck_invocations_output_units_non_negative"),
        CheckConstraint("total_units >= 0", name="ck_invocations_total_units_non_negative"),
        CheckConstraint(
            "usage_consumed_units >= 0", name="ck_invocations_usage_consumed_non_negative"
        ),
        CheckConstraint("usage_limit_units > 0", name="ck_invocations_usage_limit_positive"),
        CheckConstraint(
            "usage_allowance_units > 0", name="ck_invocations_usage_allowance_positive"
        ),
        CheckConstraint(
            "(status = 'limited' AND usage_consumed_units IS NOT NULL "
            "AND usage_limit_units IS NOT NULL AND usage_allowance_units IS NOT NULL "
            "AND usage_window_start IS NOT NULL AND usage_window_end IS NOT NULL "
            "AND usage_consumed_units + usage_allowance_units > usage_limit_units "
            "AND usage_allowance_units <= usage_limit_units "
            "AND total_units IS NULL AND provider_response_id IS NULL) OR "
            "(status <> 'limited' AND usage_consumed_units IS NULL "
            "AND usage_limit_units IS NULL AND usage_allowance_units IS NULL "
            "AND usage_window_start IS NULL AND usage_window_end IS NULL)",
            name="ck_invocations_limited_evidence",
        ),
        Index(
            "ix_invocations_runtime_principal_started_at",
            "runtime_principal_id",
            "started_at",
        ),
        Index("ix_invocations_tenant_started_at", "tenant_id", "started_at"),
        CheckConstraint(
            "(cost_currency IS NULL AND cost_input IS NULL AND cost_output IS NULL "
            "AND cost_total IS NULL AND pricing_version IS NULL "
            "AND pricing_basis_units IS NULL AND pricing_input_rate IS NULL "
            "AND pricing_output_rate IS NULL) OR "
            "(cost_currency = 'USD' AND cost_input >= 0 AND cost_output >= 0 "
            "AND cost_total = cost_input + cost_output AND pricing_version IS NOT NULL "
            "AND pricing_basis_units > 0 AND pricing_input_rate >= 0 "
            "AND pricing_output_rate >= 0)",
            name="ck_invocations_cost_snapshot_complete",
        ),
        CheckConstraint(
            "(status = 'cost_limited' AND cost_budget_consumed IS NOT NULL "
            "AND cost_budget_limit IS NOT NULL AND cost_budget_allowance IS NOT NULL "
            "AND cost_budget_window_start IS NOT NULL AND cost_budget_window_end IS NOT NULL "
            "AND cost_budget_consumed >= 0 AND cost_budget_limit > 0 "
            "AND cost_budget_allowance > 0 AND cost_budget_allowance <= cost_budget_limit "
            "AND cost_budget_consumed + cost_budget_allowance > cost_budget_limit "
            "AND cost_budget_window_end > cost_budget_window_start "
            "AND input_units IS NULL AND output_units IS NULL AND total_units IS NULL "
            "AND provider_response_id IS NULL AND cost_total IS NULL) OR "
            "(status <> 'cost_limited' AND cost_budget_consumed IS NULL "
            "AND cost_budget_limit IS NULL AND cost_budget_allowance IS NULL "
            "AND cost_budget_window_start IS NULL AND cost_budget_window_end IS NULL)",
            name="ck_invocations_cost_budget_evidence",
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
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    provider_response_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    usage_consumed_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_limit_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_allowance_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    usage_window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    usage_window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cost_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    cost_input: Mapped[Decimal | None] = mapped_column(Numeric(30, 12), nullable=True)
    cost_output: Mapped[Decimal | None] = mapped_column(Numeric(30, 12), nullable=True)
    cost_total: Mapped[Decimal | None] = mapped_column(Numeric(30, 12), nullable=True)
    pricing_version: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pricing_basis_units: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pricing_input_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 12), nullable=True)
    pricing_output_rate: Mapped[Decimal | None] = mapped_column(Numeric(18, 12), nullable=True)
    cost_budget_consumed: Mapped[Decimal | None] = mapped_column(Numeric(30, 12), nullable=True)
    cost_budget_limit: Mapped[Decimal | None] = mapped_column(Numeric(30, 12), nullable=True)
    cost_budget_allowance: Mapped[Decimal | None] = mapped_column(Numeric(30, 12), nullable=True)
    cost_budget_window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cost_budget_window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
