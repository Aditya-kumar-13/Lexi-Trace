"""Add auditable provider-specific ASR outcomes.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "asr_outcomes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column(
            "memory_id",
            sa.String(36),
            sa.ForeignKey("memories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "decision_id",
            sa.String(36),
            sa.ForeignKey("decisions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "observation_id",
            sa.String(36),
            sa.ForeignKey("observations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("model_name", sa.String(150), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("source_form", sa.String(250), nullable=False),
        sa.Column("source_normalized", sa.String(250), nullable=False),
        sa.Column("target_form", sa.String(250), nullable=False),
        sa.Column("target_normalized", sa.String(250), nullable=False),
        sa.Column("provider_confidence", sa.Float(), nullable=True),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "decision_id",
            "memory_id",
            "source_normalized",
            name="uq_asr_outcome_decision_memory_source",
        ),
    )
    op.create_index("ix_asr_outcomes_user_id", "asr_outcomes", ["user_id"])
    op.create_index("ix_asr_outcomes_memory_id", "asr_outcomes", ["memory_id"])
    op.create_index("ix_asr_outcomes_decision_id", "asr_outcomes", ["decision_id"])
    op.create_index("ix_asr_outcomes_observation_id", "asr_outcomes", ["observation_id"])
    op.create_index(
        "ix_asr_outcomes_reliability_key",
        "asr_outcomes",
        [
            "user_id",
            "memory_id",
            "provider",
            "model_name",
            "rank",
            "source_normalized",
            "target_normalized",
        ],
    )


def downgrade() -> None:
    op.drop_table("asr_outcomes")
