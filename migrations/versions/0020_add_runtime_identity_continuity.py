"""Add immutable Runtime identity continuity preparation.

Revision ID: 0020
Revises: 0019

Historical Invocation identities are intentionally not rewritten.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_ACTIONS = (
    "'agent_model_permission_set', 'management_principal_created', "
    "'management_credential_issued', 'management_credential_revoked', "
    "'management_principal_disabled', 'management_principal_scopes_set', "
    "'runtime_principal_created', 'runtime_credential_issued', "
    "'runtime_credential_revoked', 'runtime_principal_disabled', "
    "'runtime_principal_usage_limits_initialized'"
)
_NEW_ACTIONS = _OLD_ACTIONS + ", 'runtime_principal_identity_continuity_bound'"


def _audit_constraint(actions: str) -> None:
    op.create_check_constraint(
        "ck_management_audit_action",
        "management_audit_records",
        f"action IN ({actions})",
    )


def upgrade() -> None:
    op.add_column("runtime_principals", sa.Column("legacy_runtime_principal_id", sa.String(255)))
    op.add_column(
        "runtime_principals", sa.Column("identity_continuity_bound_at", sa.DateTime(timezone=True))
    )
    op.create_check_constraint(
        "ck_runtime_principal_continuity_together",
        "runtime_principals",
        "(legacy_runtime_principal_id IS NULL AND identity_continuity_bound_at IS NULL) OR "
        "(legacy_runtime_principal_id IS NOT NULL AND identity_continuity_bound_at IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_runtime_principal_legacy_id_nonblank",
        "runtime_principals",
        "legacy_runtime_principal_id IS NULL OR length(btrim(legacy_runtime_principal_id)) > 0",
    )
    op.create_index(
        "uq_runtime_principals_legacy_identity",
        "runtime_principals",
        ["legacy_runtime_principal_id"],
        unique=True,
    )
    op.drop_constraint("ck_management_audit_action", "management_audit_records", type_="check")
    _audit_constraint(_NEW_ACTIONS)


def downgrade() -> None:
    op.execute(
        "DELETE FROM management_audit_records "
        "WHERE action = 'runtime_principal_identity_continuity_bound'"
    )
    op.drop_constraint("ck_management_audit_action", "management_audit_records", type_="check")
    _audit_constraint(_OLD_ACTIONS)
    op.drop_index("uq_runtime_principals_legacy_identity", table_name="runtime_principals")
    op.drop_constraint(
        "ck_runtime_principal_legacy_id_nonblank", "runtime_principals", type_="check"
    )
    op.drop_constraint(
        "ck_runtime_principal_continuity_together", "runtime_principals", type_="check"
    )
    op.drop_column("runtime_principals", "identity_continuity_bound_at")
    op.drop_column("runtime_principals", "legacy_runtime_principal_id")
