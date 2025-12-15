from typing import Optional, Any
from datetime import datetime
from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON
from sqlalchemy.sql import func
from app.db.base import Base

class InterviewSession(Base):
    __tablename__ = "interview_session"
    
    id: Mapped[str] = mapped_column(primary_key=True) # UUID
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    status: Mapped[str] = mapped_column(default="active") # active, completed
    
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), 
        onupdate=func.now()
    )
    # Relationship: One Session has Many Interactions
    interactions: Mapped[list["InterviewInteraction"]] = relationship(
        back_populates="session", 
        order_by="InterviewInteraction.order_index"
    )
    user: Mapped["User"] = relationship(back_populates="sessions")

class InterviewInteraction(Base):
    __tablename__ = "interview_interaction"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("interview_session.id"))
    
    # ORDERING is crucial so you know which is Q1, Q2, Q3
    order_index: Mapped[int] = mapped_column() 
    
    # 1. THE PROBLEM (Written by Prep Agent)
    question_content: Mapped[str] = mapped_column(Text)
    reference_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON) # Hidden from user
    audio_url: Mapped[Optional[str]] = mapped_column() # ElevenLabs URL
    
    # 2. THE ANSWER (Written by Interviewer API)
    user_answer_text: Mapped[Optional[str]] = mapped_column(Text)
    user_audio_url: Mapped[Optional[str]] = mapped_column()
    
    # 3. THE SCORE (Written by Scoring Agent)
    # Stores: {accuracy: 8, feedback: "Good...", completeness: 9}
    grade_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    
    # Relationship back to parent
    session: Mapped["InterviewSession"] = relationship(back_populates="interactions")