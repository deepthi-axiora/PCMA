"""Add Sprint 6 MOM management tables.

Revision ID: f6g7h8i92345
Revises: e5f6g7h81234
"""
from alembic import op
import sqlalchemy as sa

revision = "f6g7h8i92345"
down_revision = "e5f6g7h81234"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "moms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("is_uncertain", sa.Boolean(), nullable=False),
        sa.Column("is_user_edited", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("conversation_id", name="uq_mom_conversation"),
    )
    op.create_index("ix_moms_user_id", "moms", ["user_id"])
    op.create_index("ix_moms_conversation_id", "moms", ["conversation_id"])
    op.create_index("ix_moms_user_conv", "moms", ["user_id", "conversation_id"])
    op.create_index("ix_moms_user_status", "moms", ["user_id", "status"])

    op.create_table(
        "mom_sections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mom_id", sa.Integer(), nullable=False),
        sa.Column("section_type", sa.String(80), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["mom_id"], ["moms.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_mom_sections_mom_id", "mom_sections", ["mom_id"])

    op.create_table(
        "mom_edit_histories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mom_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("edited_field", sa.String(100), nullable=False),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["mom_id"], ["moms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_mom_edit_histories_mom_id", "mom_edit_histories", ["mom_id"])
    op.create_index("ix_mom_edit_histories_user_id", "mom_edit_histories", ["user_id"])


def downgrade() -> None:
    op.drop_table("mom_edit_histories")
    op.drop_table("mom_sections")
    op.drop_table("moms")
