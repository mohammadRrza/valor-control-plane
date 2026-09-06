"""Add persisted Management principals and independent credentials.

Revision ID: 0015
Revises: 0014

Downgrade destroys persisted Management access configuration.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | Sequence[str] | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIONS = (
    "'agent_model_permission_set', 'management_principal_created', "
    "'management_credential_issued', 'management_credential_revoked', "
    "'management_principal_disabled', 'management_principal_scopes_set'"
)
_RESOURCES = "'agent_model_permission', 'management_principal', 'management_credential'"


def upgrade() -> None:
    op.create_table(
        "management_principals",
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("can_manage_principals", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("principal_id"),
    )
    op.create_table(
        "management_principal_tenant_scopes",
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["principal_id"],
            ["management_principals.principal_id"],
            name="fk_management_scope_principal",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_management_scope_tenant"),
        sa.PrimaryKeyConstraint("principal_id", "tenant_id"),
    )
    op.create_table(
        "management_credentials",
        sa.Column("credential_id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("secret_verifier", sa.String(length=64), nullable=False),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "secret_verifier ~ '^[0-9a-f]{64}$'", name="ck_management_credential_verifier"
        ),
        sa.ForeignKeyConstraint(
            ["principal_id"],
            ["management_principals.principal_id"],
            name="fk_management_credential_principal",
        ),
        sa.PrimaryKeyConstraint("credential_id"),
    )
    op.create_index(
        "ix_management_credentials_principal_id",
        "management_credentials",
        ["principal_id"],
        unique=False,
    )
    op.alter_column("management_audit_records", "tenant_id", nullable=True)
    op.drop_constraint("ck_management_audit_action", "management_audit_records", type_="check")
    op.drop_constraint(
        "ck_management_audit_resource_type", "management_audit_records", type_="check"
    )
    op.create_check_constraint(
        "ck_management_audit_action", "management_audit_records", f"action IN ({_ACTIONS})"
    )
    op.create_check_constraint(
        "ck_management_audit_resource_type",
        "management_audit_records",
        f"resource_type IN ({_RESOURCES})",
    )


def downgrade() -> None:
    op.execute("DELETE FROM management_audit_records WHERE tenant_id IS NULL")
    op.drop_constraint("ck_management_audit_action", "management_audit_records", type_="check")
    op.drop_constraint(
        "ck_management_audit_resource_type", "management_audit_records", type_="check"
    )
    op.create_check_constraint(
        "ck_management_audit_action",
        "management_audit_records",
        "action IN ('agent_model_permission_set')",
    )
    op.create_check_constraint(
        "ck_management_audit_resource_type",
        "management_audit_records",
        "resource_type IN ('agent_model_permission')",
    )
    op.alter_column("management_audit_records", "tenant_id", nullable=False)
    op.drop_index("ix_management_credentials_principal_id", table_name="management_credentials")
    op.drop_table("management_credentials")
    op.drop_table("management_principal_tenant_scopes")
    op.drop_table("management_principals")
