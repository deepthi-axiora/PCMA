"""Add Sprint 9 Reminders table.

Revision ID: i9j0k1l25678
Revises: h8i9j0k14567
"""
from alembic import op
import sqlalchemy as sa

revision = "i9j0k1l25678"
down_revision = "h8i9j0k14567"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "reminders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("commitment_id", sa.Integer(), nullable=True),
        sa.Column("action_item_id", sa.Integer(), nullable=True),
        sa.Column("deadline_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.String(80), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("priority", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["commitment_id"], ["commitments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["action_item_id"], ["action_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["deadline_id"], ["deadlines.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_reminders_user_id", "reminders", ["user_id"])
    op.create_index("ix_reminders_user_status", "reminders", ["user_id", "status"])
    op.create_index("ix_reminders_remind_at", "reminders", ["status", "remind_at"])


def downgrade() -> None:
    op.drop_table("reminders")
