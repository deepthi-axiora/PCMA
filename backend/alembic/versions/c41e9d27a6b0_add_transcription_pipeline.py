"""Add transcription jobs and encrypted transcript storage.

Revision ID: c41e9d27a6b0
Revises: 8a77b142c1d3
Create Date: 2026-09-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c41e9d27a6b0"
down_revision: Union[str, Sequence[str], None] = "8a77b142c1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_processing_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recording_id", sa.Integer(), nullable=False),
        sa.Column("stage", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("model_used", sa.String(length=120), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("recording_id", "stage", name="uq_processing_job_recording_stage"),
    )
    op.create_index("ix_ai_processing_jobs_recording_id", "ai_processing_jobs", ["recording_id"])
    op.create_index("ix_processing_jobs_claim", "ai_processing_jobs", ["status", "available_at"])

    op.create_table(
        "transcripts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recording_id", sa.Integer(), nullable=False),
        sa.Column("language", sa.String(length=40), nullable=True),
        sa.Column("detected_languages", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("encryption_key_ref", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("recording_id"),
    )
    op.create_table(
        "transcript_segments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("transcript_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column("text_ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("low_confidence", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["transcript_id"], ["transcripts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("transcript_id", "chunk_index", "segment_index",
                            name="uq_transcript_chunk_segment"),
    )
    op.create_index("ix_transcript_segments_transcript_id", "transcript_segments", ["transcript_id"])
    op.create_index("ix_transcript_segments_order", "transcript_segments", ["transcript_id", "start_ms"])


def downgrade() -> None:
    op.drop_index("ix_transcript_segments_order", table_name="transcript_segments")
    op.drop_index("ix_transcript_segments_transcript_id", table_name="transcript_segments")
    op.drop_table("transcript_segments")
    op.drop_table("transcripts")
    op.drop_index("ix_processing_jobs_claim", table_name="ai_processing_jobs")
    op.drop_index("ix_ai_processing_jobs_recording_id", table_name="ai_processing_jobs")
    op.drop_table("ai_processing_jobs")
