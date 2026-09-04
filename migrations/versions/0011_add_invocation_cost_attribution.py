"""Add immutable estimated Invocation cost snapshots.

Revision ID: 0011
Revises: 0010
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("invocations", sa.Column("cost_currency", sa.String(3), nullable=True))
    op.add_column("invocations", sa.Column("cost_input", sa.Numeric(30, 12), nullable=True))
    op.add_column("invocations", sa.Column("cost_output", sa.Numeric(30, 12), nullable=True))
    op.add_column("invocations", sa.Column("cost_total", sa.Numeric(30, 12), nullable=True))
    op.add_column("invocations", sa.Column("pricing_version", sa.String(255), nullable=True))
    op.add_column("invocations", sa.Column("pricing_basis_units", sa.Integer(), nullable=True))
    op.add_column("invocations", sa.Column("pricing_input_rate", sa.Numeric(18, 12), nullable=True))
    op.add_column(
        "invocations", sa.Column("pricing_output_rate", sa.Numeric(18, 12), nullable=True)
    )
    op.create_check_constraint(
        "ck_invocations_cost_snapshot_complete",
        "invocations",
        "(cost_currency IS NULL AND cost_input IS NULL AND cost_output IS NULL "
        "AND cost_total IS NULL AND pricing_version IS NULL "
        "AND pricing_basis_units IS NULL AND pricing_input_rate IS NULL "
        "AND pricing_output_rate IS NULL) OR "
        "(cost_currency = 'USD' AND cost_input >= 0 AND cost_output >= 0 "
        "AND cost_total = cost_input + cost_output AND pricing_version IS NOT NULL "
        "AND pricing_basis_units > 0 AND pricing_input_rate >= 0 "
        "AND pricing_output_rate >= 0)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_invocations_cost_snapshot_complete", "invocations", type_="check")
    op.drop_column("invocations", "pricing_output_rate")
    op.drop_column("invocations", "pricing_input_rate")
    op.drop_column("invocations", "pricing_basis_units")
    op.drop_column("invocations", "pricing_version")
    op.drop_column("invocations", "cost_total")
    op.drop_column("invocations", "cost_output")
    op.drop_column("invocations", "cost_input")
    op.drop_column("invocations", "cost_currency")
