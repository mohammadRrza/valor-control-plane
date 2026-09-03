"""Link Invocations to policy decisions and add denied status.

Revision ID: 0007
Revises: 0006
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | Sequence[str] | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("invocations", sa.Column("policy_decision_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_invocations_policy_decision_id_policy_decisions",
        "invocations",
        "policy_decisions",
        ["policy_decision_id"],
        ["id"],
    )
    op.drop_constraint("ck_invocations_status_output", "invocations", type_="check")
    op.create_check_constraint(
        "ck_invocations_status_output",
        "invocations",
        "(status = 'succeeded' AND output_text IS NOT NULL) OR "
        "(status IN ('failed', 'denied') AND output_text IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_invocations_status_output", "invocations", type_="check")
    op.create_check_constraint(
        "ck_invocations_status_output",
        "invocations",
        "(status = 'succeeded' AND output_text IS NOT NULL) OR "
        "(status = 'failed' AND output_text IS NULL)",
    )
    op.drop_constraint(
        "fk_invocations_policy_decision_id_policy_decisions",
        "invocations",
        type_="foreignkey",
    )
    op.drop_column("invocations", "policy_decision_id")
