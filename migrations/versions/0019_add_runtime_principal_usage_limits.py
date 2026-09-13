"""Add persisted Runtime Principal usage-limit cutover preparation.

Revision ID: 0019
Revises: 0018

Existing Runtime Principals remain explicitly unconfigured; no values are invented.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_ACTIONS = (
    "'agent_model_permission_set', 'management_principal_created', "
    "'management_credential_issued', 'management_credential_revoked', "
    "'management_principal_disabled', 'management_principal_scopes_set', "
    "'runtime_principal_created', 'runtime_credential_issued', "
    "'runtime_credential_revoked', 'runtime_principal_disabled'"
)
_NEW_ACTIONS = _OLD_ACTIONS + ", 'runtime_principal_usage_limits_initialized'"


def _audit_constraint(actions: str) -> None:
    op.create_check_constraint(
        "ck_management_audit_action",
        "management_audit_records",
        f"action IN ({actions})",
    )


def upgrade() -> None:
    op.add_column(
        "runtime_principals", sa.Column("daily_usage_limit_units", sa.Integer(), nullable=True)
    )
    op.add_column(
        "runtime_principals",
        sa.Column("per_invocation_allowance_units", sa.Integer(), nullable=True),
    )
    op.create_check_constraint(
        "ck_runtime_principal_usage_limits_together",
        "runtime_principals",
        "(daily_usage_limit_units IS NULL AND per_invocation_allowance_units IS NULL) OR "
        "(daily_usage_limit_units IS NOT NULL AND "
        "per_invocation_allowance_units IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_runtime_principal_daily_usage_limit_positive",
        "runtime_principals",
        "daily_usage_limit_units IS NULL OR daily_usage_limit_units > 0",
    )
    op.create_check_constraint(
        "ck_runtime_principal_allowance_positive",
        "runtime_principals",
        "per_invocation_allowance_units IS NULL OR per_invocation_allowance_units > 0",
    )
    op.create_check_constraint(
        "ck_runtime_principal_allowance_within_limit",
        "runtime_principals",
        "daily_usage_limit_units IS NULL OR "
        "per_invocation_allowance_units <= daily_usage_limit_units",
    )
    op.drop_constraint("ck_management_audit_action", "management_audit_records", type_="check")
    _audit_constraint(_NEW_ACTIONS)


def downgrade() -> None:
    op.execute(
        "DELETE FROM management_audit_records "
        "WHERE action = 'runtime_principal_usage_limits_initialized'"
    )
    op.drop_constraint("ck_management_audit_action", "management_audit_records", type_="check")
    _audit_constraint(_OLD_ACTIONS)
    op.drop_constraint(
        "ck_runtime_principal_allowance_within_limit", "runtime_principals", type_="check"
    )
    op.drop_constraint(
        "ck_runtime_principal_allowance_positive", "runtime_principals", type_="check"
    )
    op.drop_constraint(
        "ck_runtime_principal_daily_usage_limit_positive", "runtime_principals", type_="check"
    )
    op.drop_constraint(
        "ck_runtime_principal_usage_limits_together", "runtime_principals", type_="check"
    )
    op.drop_column("runtime_principals", "per_invocation_allowance_units")
    op.drop_column("runtime_principals", "daily_usage_limit_units")
