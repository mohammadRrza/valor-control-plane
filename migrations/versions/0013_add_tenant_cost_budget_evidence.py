"""Add Tenant estimated-cost budget denial evidence.

Revision ID: 0013
Revises: 0012
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_invocations_status_output", "invocations", type_="check")
    op.create_check_constraint(
        "ck_invocations_status_output",
        "invocations",
        "(status = 'succeeded' AND output_text IS NOT NULL) OR "
        "(status IN ('failed', 'denied', 'limited', 'cost_limited') "
        "AND output_text IS NULL)",
    )
    op.add_column(
        "invocations", sa.Column("cost_budget_consumed", sa.Numeric(30, 12), nullable=True)
    )
    op.add_column("invocations", sa.Column("cost_budget_limit", sa.Numeric(30, 12), nullable=True))
    op.add_column(
        "invocations", sa.Column("cost_budget_allowance", sa.Numeric(30, 12), nullable=True)
    )
    op.add_column(
        "invocations",
        sa.Column("cost_budget_window_start", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "invocations",
        sa.Column("cost_budget_window_end", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_invocations_cost_budget_evidence",
        "invocations",
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
    )


def downgrade() -> None:
    op.execute("DELETE FROM invocations WHERE status = 'cost_limited'")
    op.drop_constraint("ck_invocations_cost_budget_evidence", "invocations", type_="check")
    op.drop_column("invocations", "cost_budget_window_end")
    op.drop_column("invocations", "cost_budget_window_start")
    op.drop_column("invocations", "cost_budget_allowance")
    op.drop_column("invocations", "cost_budget_limit")
    op.drop_column("invocations", "cost_budget_consumed")
    op.drop_constraint("ck_invocations_status_output", "invocations", type_="check")
    op.create_check_constraint(
        "ck_invocations_status_output",
        "invocations",
        "(status = 'succeeded' AND output_text IS NOT NULL) OR "
        "(status IN ('failed', 'denied', 'limited') AND output_text IS NULL)",
    )
