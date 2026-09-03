"""Create Runtime Gateway Invocation table.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invocations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(status = 'succeeded' AND output_text IS NOT NULL) OR "
            "(status = 'failed' AND output_text IS NULL)",
            name="ck_invocations_status_output",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_invocations_tenant_id_tenants"
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], name="fk_invocations_agent_id_agents"),
        sa.ForeignKeyConstraint(["model_id"], ["models.id"], name="fk_invocations_model_id_models"),
        sa.PrimaryKeyConstraint("id", name="pk_invocations"),
    )


def downgrade() -> None:
    op.drop_table("invocations")
