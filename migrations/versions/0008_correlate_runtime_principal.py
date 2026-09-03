"""Correlate Invocations with authenticated runtime principals.

Revision ID: 0008
Revises: 0007
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | Sequence[str] | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "invocations",
        sa.Column("runtime_principal_id", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("invocations", "runtime_principal_id")
