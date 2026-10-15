"""Add the consent-linked recording lifecycle and encrypted audio metadata.

Revision ID: 8a77b142c1d3
Revises: fe30553f2bba
Create Date: 2026-09-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8a77b142c1d3"
down_revision: Union[str, Sequence[str], None] = "fe30553f2bba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Keep legacy status rows intact. Their historical consent/audio cannot be
    # reconstructed truthfully; new API-created recordings use the validated state.
    op.add_column("recordings", sa.Column("state", sa.String(length=32), nullable=True))
    op.add_column("recordings", sa.Column("audio_source", sa.String(length=40), nullable=True))
    op.add_column("recordings", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("recordings", sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("recordings", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.create_index(
        "uq_recordings_one_open_per_user", "recordings", ["user_id"], unique=True,
        postgresql_where=sa.text("state IN ('active', 'paused')"),
        sqlite_where=sa.text("state IN ('active', 'paused')"),
    )

    op.create_table(
        "consent_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recording_id", sa.Integer(), nullable=False),
        sa.Column("jurisdiction", sa.String(length=100), nullable=False),
        sa.Column("prompt_shown", sa.Boolean(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("recording_id", name="uq_consent_recording"),
    )
    op.create_index("ix_consent_records_recording_id", "consent_records", ["recording_id"])

    op.create_table(
        "audio_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recording_id", sa.Integer(), nullable=False),
        sa.Column("storage_ref", sa.String(length=512), nullable=False),
        sa.Column("encryption_key_ref", sa.String(length=80), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("recording_id", name="uq_audio_file_recording"),
        sa.UniqueConstraint("storage_ref"),
    )
    op.create_index("ix_audio_files_recording_id", "audio_files", ["recording_id"])

    op.create_table(
        "recording_pauses",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recording_id", sa.Integer(), nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_recording_pauses_recording_id", "recording_pauses", ["recording_id"])

    op.create_table(
        "audio_source_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recording_id", sa.Integer(), nullable=False),
        sa.Column("from_source", sa.String(length=40), nullable=False),
        sa.Column("to_source", sa.String(length=40), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_audio_source_events_recording_id", "audio_source_events", ["recording_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("metadata_json", sa.String(length=2000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_user_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_recording_pauses_recording_id", table_name="recording_pauses")
    op.drop_table("recording_pauses")
    op.drop_index("ix_audio_source_events_recording_id", table_name="audio_source_events")
    op.drop_table("audio_source_events")
    op.drop_index("ix_audio_files_recording_id", table_name="audio_files")
    op.drop_table("audio_files")
    op.drop_index("ix_consent_records_recording_id", table_name="consent_records")
    op.drop_table("consent_records")
    op.drop_index("uq_recordings_one_open_per_user", table_name="recordings")
    op.drop_column("recordings", "duration_ms")
    op.drop_column("recordings", "stopped_at")
    op.drop_column("recordings", "started_at")
    op.drop_column("recordings", "audio_source")
    op.drop_column("recordings", "state")
