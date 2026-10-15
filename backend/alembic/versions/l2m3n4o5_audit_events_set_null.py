"""Make AuditEvent user_id nullable with ON DELETE SET NULL for audit retention compliance.

Revision ID: l2m3n4o58901
Revises: k1l2m3n47890
"""
from alembic import op
import sqlalchemy as sa

revision = "l2m3n4o58901"
down_revision = "k1l2m3n47890"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table("audit_events") as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=True)
        if bind.dialect.name != "sqlite":
            batch_op.drop_constraint("audit_events_user_id_fkey", type_="foreignkey")
            batch_op.create_foreign_key("audit_events_user_id_fkey", "users", ["user_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table("audit_events") as batch_op:
        if bind.dialect.name != "sqlite":
            batch_op.drop_constraint("audit_events_user_id_fkey", type_="foreignkey")
            batch_op.create_foreign_key("audit_events_user_id_fkey", "users", ["user_id"], ["id"], ondelete="CASCADE")
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)

