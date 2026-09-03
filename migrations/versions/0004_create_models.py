"""Create governed Model reference table.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "models",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("provider_model_reference", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name="fk_models_tenant_id_tenants",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_models"),
        sa.UniqueConstraint(
            "tenant_id",
            "normalized_name",
            name="uq_models_tenant_id_normalized_name",
        ),
    )


def downgrade() -> None:
    op.drop_table("models")
