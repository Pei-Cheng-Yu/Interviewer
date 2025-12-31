from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from app.db.models import InterviewInteraction, InterviewSession
from sqlalchemy import String, cast, desc, exists, func, select, update
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased


class InterviewRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ---------- session ----------
    async def create_session(self, user_id: int) -> str:
        sid = str(uuid4())
        self.db.add(InterviewSession(id=sid, user_id=user_id))
        await self.db.flush()
        return sid

    async def set_session_max_index(self, session_id: str, max_index: int) -> None:
        """
        Persist onboarding-computed max_index into interview_session.max_index
        """
        await self.db.execute(
            update(InterviewSession)
            .where(InterviewSession.id == session_id)
            .values(max_index=max_index)
        )

    async def get_session(self, session_id: str) -> InterviewSession | None:
        """
        Load session row (must include max_index + status).
        """
        res = await self.db.execute(
            select(InterviewSession).where(InterviewSession.id == session_id)
        )
        return res.scalar_one_or_none()

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

    async def set_session_job_title(self, session_id: str, job_title: str):
        sess = await self.get_session(session_id)
        if not sess:
            return
        sess.job_title = job_title

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

    async def get_by_order(
        self, session_id: str, order_index: int
    ) -> Optional[InterviewInteraction]:
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
        stmt = (
            insert(InterviewInteraction)
            .values(
                session_id=session_id,
                order_index=order_index,
                question_content=question_content,
                reference_data=reference_data,
                audio_url=audio_url,
            )
            .on_conflict_do_nothing(index_elements=["session_id", "order_index"])
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
            raise ValueError(
                f"Interaction not found: session={session_id}, idx={order_index}"
            )

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

    async def get_current_asked_unanswered(
        self, session_id: str
    ) -> Optional[InterviewInteraction]:
        """
        The question the user is currently answering:
        - audio_url exists (we already served it)
        - user_answer_text still null
        Pick the newest served unanswered.
        """
        return await self.db.scalar(
            select(InterviewInteraction)
            .where(
                InterviewInteraction.session_id == session_id,
                InterviewInteraction.audio_url.is_not(None),
                InterviewInteraction.user_answer_text.is_(None),
            )
            .order_by(InterviewInteraction.order_index.desc())
            .limit(1)
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

    async def save_user_answer(
        self, session_id: str, order_index: int, answer_text: str
    ) -> None:
        await self.db.execute(
            update(InterviewInteraction)
            .where(
                InterviewInteraction.session_id == session_id,
                InterviewInteraction.order_index == order_index,
            )
            .values(user_answer_text=answer_text)
        )

    async def save_question_audio_url(
        self, interaction_id: int, audio_url: str
    ) -> None:
        await self.db.execute(
            update(InterviewInteraction)
            .where(InterviewInteraction.id == interaction_id)
            .values(audio_url=audio_url)
        )

    async def save_user_audio_url(
        self, session_id: str, order_index: int, user_audio_url: str
    ) -> None:
        await self.db.execute(
            update(InterviewInteraction)
            .where(
                InterviewInteraction.session_id == session_id,
                InterviewInteraction.order_index == order_index,
            )
            .values(user_audio_url=user_audio_url)
        )

    # ---------- scoring queue ----------
    async def next_ungraded_answered(
        self, session_id: str
    ) -> Optional[InterviewInteraction]:
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

    async def save_grade_by_id(
        self, interaction_id: int, grade_data: dict[str, Any]
    ) -> None:
        await self.db.execute(
            update(InterviewInteraction)
            .where(InterviewInteraction.id == interaction_id)
            .values(grade_data=grade_data)
        )

    async def count_interactions(self, session_id: str) -> int:
        n = await self.db.scalar(
            select(func.count())
            .select_from(InterviewInteraction)
            .where(InterviewInteraction.session_id == session_id)
        )
        return int(n or 0)

    async def get_next_base_idx_for_hard(self, session_id: str) -> int | None:
        base = aliased(InterviewInteraction)
        hard = aliased(InterviewInteraction)

        base_diff = base.reference_data["meta"]["difficulty"].as_string()
        hard_diff = hard.reference_data["meta"]["difficulty"].as_string()
        hard_parent = hard.reference_data["meta"]["parent_order_index"].as_string()

        hard_exists = exists().where(
            hard.session_id == session_id,
            hard_diff == "hard",
            hard_parent == cast(base.order_index, String),
        )

        q = (
            select(base.order_index)
            .where(
                base.session_id == session_id,
                base.user_answer_text.isnot(None),
                base.grade_data.isnot(None),
                (base_diff.is_(None)) | (base_diff != "hard"),
                ~hard_exists,
            )
            .order_by(base.order_index.asc())
            .limit(1)
        )
        return await self.db.scalar(q)

    async def hard_exists_for_base(self, session_id: str, base_idx: int) -> bool:

        ref = cast(InterviewInteraction.reference_data, JSONB)

        difficulty = func.jsonb_extract_path_text(ref, "meta", "difficulty")
        parent = func.jsonb_extract_path_text(ref, "meta", "parent_order_index")

        q = (
            select(func.count())
            .select_from(InterviewInteraction)
            .where(
                InterviewInteraction.session_id == session_id,
                difficulty == "hard",
                parent == str(base_idx),
            )
        )
        n = await self.db.scalar(q)
        print(f"hard for base n is : {n}")
        return int(n or 0) > 0

    async def set_session_status(self, session_id: str, status: str) -> None:
        await self.db.execute(
            update(InterviewSession)
            .where(InterviewSession.id == session_id)
            .values(status=status)
        )

    async def count_ungraded_answered(self, session_id: str) -> int:
        n = await self.db.scalar(
            select(func.count())
            .select_from(InterviewInteraction)
            .where(
                InterviewInteraction.session_id == session_id,
                InterviewInteraction.user_answer_text.is_not(None),
                InterviewInteraction.grade_data.is_(None),
            )
        )
        return int(n or 0)

    async def count_unanswered_upto(self, session_id: str, max_index: int) -> int:
        n = await self.db.scalar(
            select(func.count())
            .select_from(InterviewInteraction)
            .where(
                InterviewInteraction.session_id == session_id,
                InterviewInteraction.order_index <= max_index,
                InterviewInteraction.user_answer_text.is_(None),
            )
        )
        return int(n or 0)

    async def list_sessions(self, user_id: int) -> list[InterviewSession]:
        res = await self.db.execute(
            select(InterviewSession)
            .where(InterviewSession.user_id == user_id)
            .order_by(InterviewSession.created_at.desc())
        )
        return list(res.scalars().all())

    async def get_pending_asked_unanswered(
        self, session_id: str
    ) -> InterviewInteraction | None:
        return await self.db.scalar(
            select(InterviewInteraction)
            .where(
                InterviewInteraction.session_id == session_id,
                InterviewInteraction.audio_url.is_not(None),  # asked
                InterviewInteraction.user_answer_text.is_(None),  # unanswered
            )
            .order_by(InterviewInteraction.order_index.desc())
            .limit(1)
        )

    async def list_sessions_for_user(
        self, user_id: str, limit: int = 50, offset: int = 0
    ):
        # If you have an InterviewSession table, use that instead.
        # Otherwise derive sessions from interactions.
        from app.db.models.interview import InterviewSession  # adjust

        q = (
            select(InterviewSession)
            .where(InterviewSession.user_id == user_id)
            .order_by(desc(InterviewSession.created_at))
            .limit(limit)
            .offset(offset)
        )
        return (await self.db.execute(q)).scalars().all()

    async def get_session_review_rows(self, session_id: str):
        from app.db.models.interview import InterviewInteraction  # adjust

        q = (
            select(InterviewInteraction)
            .where(InterviewInteraction.session_id == session_id)
            .order_by(InterviewInteraction.order_index.asc())
        )
        return (await self.db.execute(q)).scalars().all()
