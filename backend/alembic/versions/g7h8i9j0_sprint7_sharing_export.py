"""Add Sprint 7 MOM sharing and export tables.

Revision ID: g7h8i9j03456
Revises: f6g7h8i92345
"""
from alembic import op
import sqlalchemy as sa

revision = "g7h8i9j03456"
down_revision = "f6g7h8i92345"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mom_recipients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mom_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("share_token", sa.String(128), nullable=False),
        sa.Column("permissions", sa.String(40), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False),
        sa.Column("shared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["mom_id"], ["moms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("share_token", name="uq_mom_recipient_share_token"),
    )
    op.create_index("ix_mom_recipients_mom_id", "mom_recipients", ["mom_id"])
    op.create_index("ix_mom_recipients_user_id", "mom_recipients", ["user_id"])
    op.create_index("ix_mom_recipients_token", "mom_recipients", ["share_token"], unique=True)

    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("mom_id", sa.Integer(), nullable=False),
        sa.Column("format", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mom_id"], ["moms.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_export_jobs_user_id", "export_jobs", ["user_id"])
    op.create_index("ix_export_jobs_mom_id", "export_jobs", ["mom_id"])


def downgrade() -> None:
    op.drop_table("export_jobs")
    op.drop_table("mom_recipients")
