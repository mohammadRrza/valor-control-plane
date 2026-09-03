"""Create Agent-Model permissions and runtime policy decisions.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_model_permissions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.Uuid(), nullable=False),
        sa.Column("effect", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("effect IN ('allow', 'deny')", name="ck_permissions_effect"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_permissions_tenant_id_tenants"
        ),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], name="fk_permissions_agent_id_agents"),
        sa.ForeignKeyConstraint(["model_id"], ["models.id"], name="fk_permissions_model_id_models"),
        sa.PrimaryKeyConstraint("id", name="pk_agent_model_permissions"),
        sa.UniqueConstraint(
            "tenant_id", "agent_id", "model_id", name="uq_permissions_tenant_agent_model"
        ),
    )
    op.create_table(
        "policy_decisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invocation_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("model_id", sa.Uuid(), nullable=False),
        sa.Column("permission_id", sa.Uuid(), nullable=True),
        sa.Column("effect", sa.String(length=10), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("effect IN ('allow', 'deny')", name="ck_policy_decisions_effect"),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_policy_decisions_tenant_id_tenants"
        ),
        sa.ForeignKeyConstraint(
            ["agent_id"], ["agents.id"], name="fk_policy_decisions_agent_id_agents"
        ),
        sa.ForeignKeyConstraint(
            ["model_id"], ["models.id"], name="fk_policy_decisions_model_id_models"
        ),
        sa.ForeignKeyConstraint(
            ["permission_id"],
            ["agent_model_permissions.id"],
            name="fk_policy_decisions_permission_id_permissions",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_policy_decisions"),
    )
    op.create_index(
        "ix_policy_decisions_invocation_id", "policy_decisions", ["invocation_id"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_policy_decisions_invocation_id", table_name="policy_decisions")
    op.drop_table("policy_decisions")
    op.drop_table("agent_model_permissions")
