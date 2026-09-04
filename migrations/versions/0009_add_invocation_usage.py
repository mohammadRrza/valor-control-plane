"""Add provider-neutral observability facts to Invocations.

Revision ID: 0009
Revises: 0008
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | Sequence[str] | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("invocations", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column("invocations", sa.Column("input_units", sa.Integer(), nullable=True))
    op.add_column("invocations", sa.Column("output_units", sa.Integer(), nullable=True))
    op.add_column("invocations", sa.Column("total_units", sa.Integer(), nullable=True))
    op.add_column(
        "invocations",
        sa.Column("provider_response_id", sa.String(length=255), nullable=True),
    )
    op.create_check_constraint(
        "ck_invocations_duration_non_negative", "invocations", "duration_ms >= 0"
    )
    op.create_check_constraint(
        "ck_invocations_input_units_non_negative", "invocations", "input_units >= 0"
    )
    op.create_check_constraint(
        "ck_invocations_output_units_non_negative", "invocations", "output_units >= 0"
    )
    op.create_check_constraint(
        "ck_invocations_total_units_non_negative", "invocations", "total_units >= 0"
    )


def downgrade() -> None:
    op.drop_constraint("ck_invocations_total_units_non_negative", "invocations", type_="check")
    op.drop_constraint("ck_invocations_output_units_non_negative", "invocations", type_="check")
    op.drop_constraint("ck_invocations_input_units_non_negative", "invocations", type_="check")
    op.drop_constraint("ck_invocations_duration_non_negative", "invocations", type_="check")
    op.drop_column("invocations", "provider_response_id")
    op.drop_column("invocations", "total_units")
    op.drop_column("invocations", "output_units")
    op.drop_column("invocations", "input_units")
    op.drop_column("invocations", "duration_ms")
