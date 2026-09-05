"""Add immutable Management governance audit evidence.

Revision ID: 0014
Revises: 0013
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | Sequence[str] | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "management_audit_records",
        sa.Column("audit_id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("before_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("after_fingerprint", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "action IN ('agent_model_permission_set')", name="ck_management_audit_action"
        ),
        sa.CheckConstraint(
            "resource_type IN ('agent_model_permission')",
            name="ck_management_audit_resource_type",
        ),
        sa.CheckConstraint(
            "outcome IN ('succeeded', 'failed')", name="ck_management_audit_outcome"
        ),
        sa.CheckConstraint(
            "before_fingerprint IS NULL OR before_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_management_audit_before_fingerprint",
        ),
        sa.CheckConstraint(
            "after_fingerprint IS NULL OR after_fingerprint ~ '^[0-9a-f]{64}$'",
            name="ck_management_audit_after_fingerprint",
        ),
        sa.CheckConstraint(
            "outcome <> 'succeeded' OR after_fingerprint IS NOT NULL",
            name="ck_management_audit_success_after",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"], ["tenants.id"], name="fk_management_audit_tenant_id_tenants"
        ),
        sa.PrimaryKeyConstraint("audit_id"),
    )
    op.create_index(
        "ix_management_audit_tenant_occurred",
        "management_audit_records",
        ["tenant_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_management_audit_tenant_occurred", table_name="management_audit_records")
    op.drop_table("management_audit_records")
