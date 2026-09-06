"""Add idempotent observation lifecycle evidence.

Revision ID: 0006
Revises: 0005
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("observations", sa.Column("source_event_id", sa.String(150), nullable=True))
    op.add_column("observations", sa.Column("context_fingerprint", sa.String(64), nullable=True))
    op.create_index(
        "uq_observation_user_event_memory",
        "observations",
        ["user_id", "source_event_id", "memory_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_observation_user_event_memory", table_name="observations")
    op.drop_column("observations", "context_fingerprint")
    op.drop_column("observations", "source_event_id")
