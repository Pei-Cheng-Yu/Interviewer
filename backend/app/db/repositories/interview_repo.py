from __future__ import annotations
from typing import Optional, Any
from uuid import uuid4

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import InterviewSession, InterviewInteraction
from sqlalchemy.dialects.postgresql import insert

class InterviewRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- session ----------
    async def create_session(self, user_id: int) -> str:
        sid = str(uuid4())
        self.db.add(InterviewSession(id=sid, user_id=user_id))
        await self.db.flush()
        return sid

    async def assert_session_owner(self, session_id: str, user_id: int) -> None:
        exists = await self.db.scalar(
            select(InterviewSession.id).where(
                InterviewSession.id == session_id,
                InterviewSession.user_id == user_id,
            )
        )
        if not exists:
            raise ValueError("Session not found or not owned by user.")

    async def get_max_order_index(self, session_id: str) -> int:
        max_idx = await self.db.scalar(
            select(func.max(InterviewInteraction.order_index)).where(
                InterviewInteraction.session_id == session_id
            )
        )
        return int(max_idx) if max_idx is not None else -1

    # ---------- interaction insert/append ----------
    async def append_question(
        self,
        session_id: str,
        question_content: str,
        reference_data: Optional[dict[str, Any]] = None,
        audio_url: Optional[str] = None,
    ) -> InterviewInteraction:
        next_idx = (await self.get_max_order_index(session_id)) + 1
        row = InterviewInteraction(
            session_id=session_id,
            order_index=next_idx,
            question_content=question_content,
            reference_data=reference_data,
            audio_url=audio_url,
        )
        self.db.add(row)
        await self.db.flush()
        return row

    async def get_by_order(self, session_id: str, order_index: int) -> Optional[InterviewInteraction]:
        return await self.db.scalar(
            select(InterviewInteraction).where(
                InterviewInteraction.session_id == session_id,
                InterviewInteraction.order_index == order_index,
            )
        )
    async def upsert_question_at_index(
        self,
        session_id: str,
        order_index: int,
        question_content: str,
        reference_data: Optional[dict[str, Any]] = None,
        audio_url: Optional[str] = None,
        ) -> None:
        """
        Insert a question at a specific order_index.
        Safe for parallel generation (OnboardingAgent).
        Requires DB unique constraint on (session_id, order_index).
        """
        stmt = insert(InterviewInteraction).values(
            session_id=session_id,
            order_index=order_index,
            question_content=question_content,
            reference_data=reference_data,
            audio_url=audio_url,
        ).on_conflict_do_nothing(
            index_elements=["session_id", "order_index"]
        )
        await self.db.execute(stmt)

    async def merge_reference_data(
        self,
        session_id: str,
        order_index: int,
        patch: dict[str, Any],
    ) -> None:
        """
        Merge patch into existing reference_data dict.
        Useful for saving reference_answer/key_criteria without overwriting meta.
        """
        row = await self.get_by_order(session_id, order_index)
        if not row:
            raise ValueError(f"Interaction not found: session={session_id}, idx={order_index}")

        current = row.reference_data or {}
        current.update(patch)

        await self.db.execute(
            update(InterviewInteraction)
            .where(
                InterviewInteraction.session_id == session_id,
                InterviewInteraction.order_index == order_index,
            )
            .values(reference_data=current)
        )


    # ---------- interviewer queue ----------
    async def next_unanswered(self, session_id: str) -> Optional[InterviewInteraction]:
        return await self.db.scalar(
            select(InterviewInteraction)
            .where(
                InterviewInteraction.session_id == session_id,
                InterviewInteraction.user_answer_text.is_(None),
            )
            .order_by(InterviewInteraction.order_index.asc())
            .limit(1)
        )

    async def save_user_answer(self, session_id: str, order_index: int, answer_text: str) -> None:
        await self.db.execute(
            update(InterviewInteraction)
            .where(
                InterviewInteraction.session_id == session_id,
                InterviewInteraction.order_index == order_index,
            )
            .values(user_answer_text=answer_text)
        )

    # ---------- scoring queue ----------
    async def next_ungraded_answered(self, session_id: str) -> Optional[InterviewInteraction]:
        return await self.db.scalar(
            select(InterviewInteraction)
            .where(
                InterviewInteraction.session_id == session_id,
                InterviewInteraction.user_answer_text.is_not(None),
                InterviewInteraction.grade_data.is_(None),
            )
            .order_by(InterviewInteraction.order_index.asc())
            .limit(1)
        )

    async def save_grade_by_id(self, interaction_id: int, grade_data: dict[str, Any]) -> None:
        await self.db.execute(
            update(InterviewInteraction)
            .where(InterviewInteraction.id == interaction_id)
            .values(grade_data=grade_data)
        )



    async def count_interactions(self, session_id: str) -> int:
        n = await self.db.scalar(
            select(func.count()).select_from(InterviewInteraction)
            .where(InterviewInteraction.session_id == session_id)
        )
        return int(n or 0)

    async def hard_exists_for_base(self, session_id: str, base_idx: int) -> bool:
        meta = InterviewInteraction.reference_data["meta"]

        q = (
            select(func.count())
            .select_from(InterviewInteraction)
            .where(
                InterviewInteraction.session_id == session_id,
                meta["difficulty"].as_string() == "hard",
                meta["parent_order_index"].as_string() == str(base_idx),
            )
        )
        n = await self.db.scalar(q)
        return (n or 0) > 0