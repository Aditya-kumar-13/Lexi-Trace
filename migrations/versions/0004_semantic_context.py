"""Add semantic context vectors.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "context_embeddings",
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
        sa.Column("model_name", sa.String(250), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column("vector_json", sa.Text(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("context_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "observation_id",
            "polarity",
            "model_name",
            name="uq_context_embedding_observation_model",
        ),
    )
    op.create_index("ix_context_embeddings_memory_id", "context_embeddings", ["memory_id"])
    op.create_index(
        "ix_context_embeddings_observation_id",
        "context_embeddings",
        ["observation_id"],
    )
    op.create_index(
        "ix_context_embeddings_memory_polarity",
        "context_embeddings",
        ["memory_id", "polarity"],
    )


def downgrade() -> None:
    op.drop_table("context_embeddings")
