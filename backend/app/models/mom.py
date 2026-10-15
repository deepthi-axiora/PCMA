from datetime import datetime, timezone
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class MOM(Base):
    __tablename__ = "moms"
    __table_args__ = (
        UniqueConstraint("conversation_id", name="uq_mom_conversation"),
        Index("ix_moms_user_conv", "user_id", "conversation_id"),
        Index("ix_moms_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Minutes of Meeting")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    is_uncertain: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_user_edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sections: Mapped[list["MOMSection"]] = relationship(
        back_populates="mom", cascade="all, delete-orphan"
    )


class MOMSection(Base):
    __tablename__ = "mom_sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    mom_id: Mapped[int] = mapped_column(
        ForeignKey("moms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    mom: Mapped[MOM] = relationship(back_populates="sections")


class MOMEditHistory(Base):
    __tablename__ = "mom_edit_histories"

    id: Mapped[int] = mapped_column(primary_key=True)
    mom_id: Mapped[int] = mapped_column(
        ForeignKey("moms.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    edited_field: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    edited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
