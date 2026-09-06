"""Index bounded Management authentication evidence queries.

Revision ID: 0017
Revises: 0016
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0017"
down_revision: str | Sequence[str] | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_management_auth_evidence_credential_observed",
        "management_authentication_evidence",
        ["credential_id", "first_observed_at"],
        unique=False,
    )
    op.create_index(
        "ix_management_auth_evidence_principal_observed",
        "management_authentication_evidence",
        ["principal_id", "first_observed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_management_auth_evidence_principal_observed",
        table_name="management_authentication_evidence",
    )
    op.drop_index(
        "ix_management_auth_evidence_credential_observed",
        table_name="management_authentication_evidence",
    )
