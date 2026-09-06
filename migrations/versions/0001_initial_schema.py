"""Initial LexiTrace schema.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("canonical_form", sa.String(250), nullable=False),
        sa.Column("canonical_normalized", sa.String(250), nullable=False),
        sa.Column("state", sa.String(30), nullable=False),
        sa.Column("scope_mode", sa.String(20), nullable=False),
        sa.Column("evidence_confidence", sa.Float(), nullable=False),
        sa.Column("support_count", sa.Integer(), nullable=False),
        sa.Column("contradiction_count", sa.Integer(), nullable=False),
        sa.Column("positive_context_json", sa.Text(), nullable=False),
        sa.Column("negative_context_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "canonical_normalized", name="uq_memory_user_canonical"),
    )
    op.create_index("ix_memories_user_id", "memories", ["user_id"])
    op.create_index("ix_memories_state", "memories", ["state"])
    op.create_index("ix_memories_user_state", "memories", ["user_id", "state"])

    op.create_table(
        "memory_variants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "memory_id",
            sa.String(36),
            sa.ForeignKey("memories.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("surface_form", sa.String(250), nullable=False),
        sa.Column("normalized_form", sa.String(250), nullable=False),
        sa.Column("metaphone_key", sa.String(250), nullable=False),
        sa.Column("support_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("memory_id", "normalized_form", name="uq_variant_memory_normalized"),
    )
    op.create_index("ix_memory_variants_memory_id", "memory_variants", ["memory_id"])
    op.create_index("ix_variants_normalized", "memory_variants", ["normalized_form"])

    op.create_table(
        "observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column(
            "memory_id",
            sa.String(36),
            sa.ForeignKey("memories.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("evidence_type", sa.String(40), nullable=False),
        sa.Column("raw_asr_text", sa.Text(), nullable=False),
        sa.Column("formatted_text", sa.Text(), nullable=False),
        sa.Column("accepted_text", sa.Text(), nullable=False),
        sa.Column("source_span", sa.String(250), nullable=False),
        sa.Column("target_span", sa.String(250), nullable=False),
        sa.Column("reliability", sa.Float(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=False),
        sa.Column("reason_code", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_observations_user_id", "observations", ["user_id"])
    op.create_index("ix_observations_memory_id", "observations", ["memory_id"])
    op.create_index("ix_observations_user_created", "observations", ["user_id", "created_at"])

    op.create_table(
        "decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("raw_asr_text", sa.Text(), nullable=False),
        sa.Column("formatted_text", sa.Text(), nullable=False),
        sa.Column("memory_aware_text", sa.Text(), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("trace_json", sa.Text(), nullable=False),
        sa.Column("total_latency_ms", sa.Float(), nullable=False),
        sa.Column("engine_version", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_decisions_user_id", "decisions", ["user_id"])
    op.create_index("ix_decisions_user_created", "decisions", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("decisions")
    op.drop_table("observations")
    op.drop_table("memory_variants")
    op.drop_table("memories")
