from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("recording_id", name="uq_conversation_recording"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         nullable=False, index=True)
    recording_id: Mapped[int] = mapped_column(ForeignKey("recordings.id", ondelete="CASCADE"),
                                              nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Conversation")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Reserved for the later Project feature; no project behavior is implemented in Sprint 4.
    project_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False,
                                                 default=lambda: datetime.now(timezone.utc))

    speakers: Mapped[list["Speaker"]] = relationship(back_populates="conversation",
                                                       cascade="all, delete-orphan")


class Person(Base):
    """Minimal user-owned identity target required for FR-13 speaker mapping."""
    __tablename__ = "people"
    __table_args__ = (Index("ix_people_owner_name", "user_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"),
                                         nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Organization ownership/linkage is introduced with the later Organization feature.
    org_id: Mapped[int | None] = mapped_column(Integer)


class Speaker(Base):
    __tablename__ = "speakers"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("people.id", ondelete="SET NULL"))
    confidence: Mapped[float | None] = mapped_column()
    uncertain: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_user: Mapped[bool] = mapped_column(nullable=False, default=False)
    confirmed: Mapped[bool] = mapped_column(nullable=False, default=False)

    conversation: Mapped[Conversation] = relationship(back_populates="speakers")
