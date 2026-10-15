"""Create transcript_edit_histories table for transcript correction audit trail.

Revision ID: n4o5p6q78901
Revises: m3n4o5p69012
"""
from alembic import op
import sqlalchemy as sa


revision = "n4o5p6q78901"
down_revision = "m3n4o5p69012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "transcript_edit_histories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("transcript_id", sa.Integer(), nullable=False),
        sa.Column("segment_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("old_text", sa.Text(), nullable=False),
        sa.Column("new_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["segment_id"], ["transcript_segments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["transcript_id"], ["transcripts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("transcript_edit_histories") as batch_op:
        batch_op.create_index("ix_transcript_edit_histories_transcript", ["transcript_id"], unique=False)
        batch_op.create_index("ix_transcript_edit_histories_segment", ["segment_id"], unique=False)
        batch_op.create_index("ix_transcript_edit_histories_user", ["user_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("transcript_edit_histories") as batch_op:
        batch_op.drop_index("ix_transcript_edit_histories_user")
        batch_op.drop_index("ix_transcript_edit_histories_segment")
        batch_op.drop_index("ix_transcript_edit_histories_transcript")
    op.drop_table("transcript_edit_histories")
