from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from app.db.base import Base
from sqlalchemy import ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from sqlalchemy.types import JSON

if TYPE_CHECKING:
    from .user import User


class InterviewSession(Base):
    __tablename__ = "interview_session"

    id: Mapped[str] = mapped_column(primary_key=True)  # UUID
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), nullable=False)
    job_title: Mapped[str] = mapped_column(nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now(), nullable=False
    )

    status: Mapped[str] = mapped_column(
        default="active", nullable=False
    )  # active, completed
    max_index: Mapped[int] = mapped_column(default=0, nullable=False)
    interactions: Mapped[list["InterviewInteraction"]] = relationship(
        back_populates="session",
        order_by="InterviewInteraction.order_index",
        cascade="all, delete-orphan",  # <-- recommended
        passive_deletes=True,  # <-- recommended if FK has ondelete
    )
    user: Mapped["User"] = relationship(back_populates="sessions")


class InterviewInteraction(Base):
    __tablename__ = "interview_interaction"
    __table_args__ = (
        UniqueConstraint("session_id", "order_index", name="uq_session_order"),
        Index("ix_session_order", "session_id", "order_index"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    session_id: Mapped[str] = mapped_column(
        ForeignKey("interview_session.id", ondelete="CASCADE"),
        nullable=False,
    )

    order_index: Mapped[int] = mapped_column(nullable=False)

    question_content: Mapped[str] = mapped_column(Text, nullable=False)
    reference_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )
    audio_url: Mapped[Optional[str]] = mapped_column(nullable=True)

    user_answer_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_audio_url: Mapped[Optional[str]] = mapped_column(nullable=True)

    grade_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)

    session: Mapped["InterviewSession"] = relationship(back_populates="interactions")
