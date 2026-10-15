"""Add Sprint 4 conversation and speaker diarization storage.

Revision ID: d4a6b2c91e73
Revises: c41e9d27a6b0
"""
from alembic import op
import sqlalchemy as sa

revision = "d4a6b2c91e73"
down_revision = "c41e9d27a6b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "people",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_people_user_id", "people", ["user_id"])
    op.create_index("ix_people_owner_name", "people", ["user_id", "name"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recording_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recording_id"], ["recordings.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("recording_id", name="uq_conversation_recording"),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    op.create_table(
        "speakers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("uncertain", sa.Boolean(), nullable=False),
        sa.Column("is_user", sa.Boolean(), nullable=False),
        sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_speakers_conversation_id", "speakers", ["conversation_id"])
    with op.batch_alter_table("transcripts") as batch:
        batch.add_column(sa.Column("conversation_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_transcripts_conversation_id", "conversations",
                                 ["conversation_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_transcripts_conversation_id", "transcripts", ["conversation_id"])
    with op.batch_alter_table("transcript_segments") as batch:
        batch.add_column(sa.Column("speaker_id", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("speaker_uncertain", sa.Boolean(),
                                   nullable=False, server_default=sa.false()))
        batch.create_foreign_key("fk_transcript_segments_speaker_id", "speakers",
                                 ["speaker_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_transcript_segments_speaker_id", "transcript_segments", ["speaker_id"])
    with op.batch_alter_table("transcript_segments") as batch:
        batch.alter_column("speaker_uncertain", existing_type=sa.Boolean(), server_default=None)


def downgrade() -> None:
    op.drop_index("ix_transcript_segments_speaker_id", table_name="transcript_segments")
    with op.batch_alter_table("transcript_segments") as batch:
        batch.drop_constraint("fk_transcript_segments_speaker_id", type_="foreignkey")
        batch.drop_column("speaker_uncertain")
        batch.drop_column("speaker_id")
    op.drop_index("ix_transcripts_conversation_id", table_name="transcripts")
    with op.batch_alter_table("transcripts") as batch:
        batch.drop_constraint("fk_transcripts_conversation_id", type_="foreignkey")
        batch.drop_column("conversation_id")
    op.drop_index("ix_speakers_conversation_id", table_name="speakers")
    op.drop_table("speakers")
    op.drop_index("ix_conversations_user_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_people_owner_name", table_name="people")
    op.drop_index("ix_people_user_id", table_name="people")
    op.drop_table("people")
