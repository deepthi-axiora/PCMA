"""Make ConsentRecord jurisdiction nullable to align with product decision removing jurisdiction requirement.

Revision ID: m3n4o5p69012
Revises: l2m3n4o58901
"""
from alembic import op
import sqlalchemy as sa

revision = "m3n4o5p69012"
down_revision = "l2m3n4o58901"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("consent_records") as batch_op:
        batch_op.alter_column("jurisdiction", existing_type=sa.String(length=100), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("consent_records") as batch_op:
        batch_op.alter_column("jurisdiction", existing_type=sa.String(length=100), nullable=False)
