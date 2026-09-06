"""Add observation-backed context evidence.

Revision ID: 0003
Revises: 0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "context_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "memory_id",
            sa.String(36),
            sa.ForeignKey("memories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "observation_id",
            sa.String(36),
            sa.ForeignKey("observations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("polarity", sa.String(10), nullable=False),
        sa.Column("feature", sa.String(250), nullable=False),
        sa.Column("feature_kind", sa.String(20), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("context_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "observation_id",
            "polarity",
            "feature",
            name="uq_context_evidence_observation_feature",
        ),
    )
    op.create_index("ix_context_evidence_memory_id", "context_evidence", ["memory_id"])
    op.create_index(
        "ix_context_evidence_observation_id",
        "context_evidence",
        ["observation_id"],
    )
    op.create_index(
        "ix_context_evidence_memory_polarity",
        "context_evidence",
        ["memory_id", "polarity"],
    )
    op.create_index("ix_context_evidence_feature", "context_evidence", ["feature"])


def downgrade() -> None:
    op.drop_table("context_evidence")
