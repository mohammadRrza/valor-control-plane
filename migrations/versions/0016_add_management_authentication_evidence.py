"""Add bounded Management credential authentication evidence.

Revision ID: 0016
Revises: 0015
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | Sequence[str] | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "management_authentication_evidence",
        sa.Column("credential_id", sa.Uuid(), nullable=False),
        sa.Column("principal_id", sa.Uuid(), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("bucket_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("first_observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('succeeded', 'credential_mismatch', 'revoked', 'expired', "
            "'principal_disabled')",
            name="ck_management_authentication_evidence_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["management_credentials.credential_id"],
            name="fk_management_auth_evidence_credential",
        ),
        sa.ForeignKeyConstraint(
            ["principal_id"],
            ["management_principals.principal_id"],
            name="fk_management_auth_evidence_principal",
        ),
        sa.PrimaryKeyConstraint("credential_id", "outcome", "bucket_started_at"),
    )
    op.create_index(
        "ix_management_auth_evidence_bucket",
        "management_authentication_evidence",
        ["bucket_started_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_management_auth_evidence_bucket",
        table_name="management_authentication_evidence",
    )
    op.drop_table("management_authentication_evidence")
