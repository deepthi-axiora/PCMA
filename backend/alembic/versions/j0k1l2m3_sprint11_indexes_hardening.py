"""Add Sprint 11 performance indexes and hardening constraints.

Revision ID: j0k1l2m36789
Revises: i9j0k1l25678
"""
from alembic import op
import sqlalchemy as sa

revision = "j0k1l2m36789"
down_revision = "i9j0k1l25678"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # TRD Section 17 required indexes:
    # Conversation (user_id, occurred_at)
    op.create_index("ix_conversations_user_occurred", "conversations", ["user_id", "occurred_at"])
    # AuditEvent (user_id, created_at)
    op.create_index("ix_audit_events_user_created", "audit_events", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_events_user_created", table_name="audit_events")
    op.drop_index("ix_conversations_user_occurred", table_name="conversations")
