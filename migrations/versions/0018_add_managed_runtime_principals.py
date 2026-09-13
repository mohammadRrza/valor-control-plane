"""Add persisted Runtime principals and credentials for provisioning.

Revision ID: 0018
Revises: 0017

Downgrade destroys inactive persisted Runtime provisioning state; static Runtime auth is unaffected.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | Sequence[str] | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_ACTIONS = (
    "'agent_model_permission_set', 'management_principal_created', "
    "'management_credential_issued', 'management_credential_revoked', "
    "'management_principal_disabled', 'management_principal_scopes_set'"
)
_NEW_ACTIONS = (
    _OLD_ACTIONS + ", 'runtime_principal_created', 'runtime_credential_issued', "
    "'runtime_credential_revoked', 'runtime_principal_disabled'"
)
_OLD_RESOURCES = "'agent_model_permission', 'management_principal', 'management_credential'"
_NEW_RESOURCES = _OLD_RESOURCES + ", 'runtime_principal', 'runtime_credential'"


def _audit_constraints(actions: str, resources: str) -> None:
    op.create_check_constraint(
        "ck_management_audit_action", "management_audit_records", f"action IN ({actions})"
    )
    op.create_check_constraint(
        "ck_management_audit_resource_type",
        "management_audit_records",
        f"resource_type IN ({resources})",
    )


def upgrade() -> None:
    op.create_table(
        "runtime_principals",
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disabled_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], name="fk_runtime_principal_tenant"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], name="fk_runtime_principal_agent"),
        sa.PrimaryKeyConstraint("principal_id"),
    )
    op.create_index(
        "ix_runtime_principals_binding", "runtime_principals", ["tenant_id", "agent_id"]
    )
    op.create_table(
        "runtime_credentials",
        sa.Column("credential_id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("secret_verifier", sa.String(64), nullable=False),
        sa.Column("label", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "secret_verifier ~ '^[0-9a-f]{64}$'", name="ck_runtime_credential_verifier"
        ),
        sa.ForeignKeyConstraint(
            ["principal_id"],
            ["runtime_principals.principal_id"],
            name="fk_runtime_credential_principal",
        ),
        sa.PrimaryKeyConstraint("credential_id"),
    )
    op.create_index("ix_runtime_credentials_principal_id", "runtime_credentials", ["principal_id"])
    op.drop_constraint("ck_management_audit_action", "management_audit_records", type_="check")
    op.drop_constraint(
        "ck_management_audit_resource_type", "management_audit_records", type_="check"
    )
    _audit_constraints(_NEW_ACTIONS, _NEW_RESOURCES)


def downgrade() -> None:
    op.execute(
        "DELETE FROM management_audit_records "
        "WHERE resource_type IN ('runtime_principal', 'runtime_credential')"
    )
    op.drop_constraint("ck_management_audit_action", "management_audit_records", type_="check")
    op.drop_constraint(
        "ck_management_audit_resource_type", "management_audit_records", type_="check"
    )
    _audit_constraints(_OLD_ACTIONS, _OLD_RESOURCES)
    op.drop_index("ix_runtime_credentials_principal_id", table_name="runtime_credentials")
    op.drop_table("runtime_credentials")
    op.drop_index("ix_runtime_principals_binding", table_name="runtime_principals")
    op.drop_table("runtime_principals")
