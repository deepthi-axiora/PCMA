from datetime import datetime, timezone
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class Reminder(Base):
    __tablename__ = "reminders"
    __table_args__ = (
        Index("ix_reminders_user_status", "user_id", "status"),
        Index("ix_reminders_remind_at", "status", "remind_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commitment_id: Mapped[int | None] = mapped_column(
        ForeignKey("commitments.id", ondelete="CASCADE"), index=True
    )
    action_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("action_items.id", ondelete="CASCADE"), index=True
    )
    deadline_id: Mapped[int | None] = mapped_column(
        ForeignKey("deadlines.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="UTC")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending")
    priority: Mapped[str] = mapped_column(String(40), nullable=False, default="normal")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
