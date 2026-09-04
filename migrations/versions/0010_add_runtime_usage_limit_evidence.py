"""Add Runtime Principal usage-limit decision evidence.

Revision ID: 0010
Revises: 0009
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | Sequence[str] | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_invocations_status_output", "invocations", type_="check")
    op.create_check_constraint(
        "ck_invocations_status_output",
        "invocations",
        "(status = 'succeeded' AND output_text IS NOT NULL) OR "
        "(status IN ('failed', 'denied', 'limited') AND output_text IS NULL)",
    )
    op.add_column("invocations", sa.Column("usage_consumed_units", sa.Integer(), nullable=True))
    op.add_column("invocations", sa.Column("usage_limit_units", sa.Integer(), nullable=True))
    op.add_column("invocations", sa.Column("usage_allowance_units", sa.Integer(), nullable=True))
    op.add_column(
        "invocations", sa.Column("usage_window_start", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "invocations", sa.Column("usage_window_end", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        "ck_invocations_usage_consumed_non_negative",
        "invocations",
        "usage_consumed_units >= 0",
    )
    op.create_check_constraint(
        "ck_invocations_usage_limit_positive", "invocations", "usage_limit_units > 0"
    )
    op.create_check_constraint(
        "ck_invocations_usage_allowance_positive", "invocations", "usage_allowance_units > 0"
    )
    op.create_check_constraint(
        "ck_invocations_limited_evidence",
        "invocations",
        "(status = 'limited' AND usage_consumed_units IS NOT NULL "
        "AND usage_limit_units IS NOT NULL AND usage_allowance_units IS NOT NULL "
        "AND usage_window_start IS NOT NULL AND usage_window_end IS NOT NULL "
        "AND usage_consumed_units + usage_allowance_units > usage_limit_units "
        "AND usage_allowance_units <= usage_limit_units "
        "AND total_units IS NULL AND provider_response_id IS NULL) OR "
        "(status <> 'limited' AND usage_consumed_units IS NULL "
        "AND usage_limit_units IS NULL AND usage_allowance_units IS NULL "
        "AND usage_window_start IS NULL AND usage_window_end IS NULL)",
    )
    op.create_index(
        "ix_invocations_runtime_principal_started_at",
        "invocations",
        ["runtime_principal_id", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_invocations_runtime_principal_started_at", table_name="invocations")
    op.drop_constraint("ck_invocations_limited_evidence", "invocations", type_="check")
    op.drop_constraint("ck_invocations_usage_allowance_positive", "invocations", type_="check")
    op.drop_constraint("ck_invocations_usage_limit_positive", "invocations", type_="check")
    op.drop_constraint("ck_invocations_usage_consumed_non_negative", "invocations", type_="check")
    op.drop_column("invocations", "usage_window_end")
    op.drop_column("invocations", "usage_window_start")
    op.drop_column("invocations", "usage_allowance_units")
    op.drop_column("invocations", "usage_limit_units")
    op.drop_column("invocations", "usage_consumed_units")
    op.drop_constraint("ck_invocations_status_output", "invocations", type_="check")
    op.create_check_constraint(
        "ck_invocations_status_output",
        "invocations",
        "(status = 'succeeded' AND output_text IS NOT NULL) OR "
        "(status IN ('failed', 'denied') AND output_text IS NULL)",
    )
