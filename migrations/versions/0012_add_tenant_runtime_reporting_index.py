"""Add the bounded Tenant Runtime reporting index.

Revision ID: 0012
Revises: 0011
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | Sequence[str] | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_invocations_tenant_started_at", "invocations", ["tenant_id", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_invocations_tenant_started_at", table_name="invocations")
