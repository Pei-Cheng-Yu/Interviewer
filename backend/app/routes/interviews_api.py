# backend/app/api/routes/interviews_api.py
from __future__ import annotations

import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

import anyio
import httpx
from app.auth.protected import get_current_user
from app.core.agents.hard_question_agent.agent import build_hard_question_graph
from app.core.agents.interviewer_agent.agent import build_interviewer_graph
from app.core.agents.knowledge_agent.agent import build_knowledge_graph

# Your LangGraph apps
from app.core.agents.onboarding_agent.agent import build_onboarding_graph
from app.core.agents.scoring_agent.agent import build_scoring_graph

# IMPORTANT: adjust these imports to your actual model paths if needed
from app.db.models.interview import InterviewInteraction, InterviewSession
from app.db.models.user import User
from app.db.repositories.interview_repo import InterviewRepo
from app.db.session import AsyncSessionLocal, get_db
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from gtts import gTTS
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/api/interviews", tags=["interviews"])
Status = Literal["in_progress", "waiting", "completed"]

# -----------------------------
# Media settings (local file storage)
# -----------------------------
# You MUST mount this directory in FastAPI main:

MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", "media")).resolve()
INTERVIEW_MEDIA_DIR = MEDIA_ROOT / "interviews"
INTERVIEW_MEDIA_DIR.mkdir(parents=True, exist_ok=True)

MEDIA_BASE_URL = os.getenv("MEDIA_BASE_URL", "/media")  # where StaticFiles is mounted


# -----------------------------
# ElevenLabs TTS settings
# -----------------------------
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.getenv(
    "ELEVENLABS_VOICE_ID", "Rachel"
)  # set your actual voice id
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")

if not ELEVENLABS_API_KEY:
    # We won't crash import; but endpoints will error clearly when TTS is requested
    pass


# -----------------------------
# Response schemas
# -----------------------------
class CreateInterviewResponse(BaseModel):
    session_id: str
    status: Status = "in_progress"


class StartResponse(BaseModel):
    status: Status = "in_progress"
    question_text: str
    question_audio_url: Optional[str] = None


class AnswerResponse(BaseModel):
    status: Status = "in_progress"
    question_text: Optional[str] = None  # None if completed
    question_audio_url: Optional[str] = None
    message: Optional[str] = None  # optional info (e.g., "Interview completed")


class InterviewHistoryItem(BaseModel):
    session_id: str
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class InterviewHistoryResponse(BaseModel):
    items: list[InterviewHistoryItem]


class ReviewItem(BaseModel):
    order_index: int
    question_text: Optional[str] = None
    question_audio_url: Optional[str] = None
    user_answer_text: Optional[str] = None
    user_answer_audio_url: Optional[str] = None

    # whatever you store in grade_data (jsonb)
    grade_data: Optional[dict[str, Any]] = None


class InterviewReviewResponse(BaseModel):
    session_id: str
    status: str
    max_index: Optional[int] = None
    total_questions: int
    graded_questions: int
    items: list[ReviewItem]


# -----------------------------
# Graph singletons
# -----------------------------
_CHECKPOINTER = MemorySaver()

ONBOARDING_APP = build_onboarding_graph()
KNOWLEDGE_APP = build_knowledge_graph()
INTERVIEWER_APP = build_interviewer_graph(checkpointer=_CHECKPOINTER)

SCORING_APP = build_scoring_graph()
HARD_APP = build_hard_question_graph()


# -----------------------------
# Helpers
# -----------------------------
async def _read_upload_as_text(file: UploadFile) -> str:
    content = await file.read()
    return content.decode("utf-8", errors="ignore")


def _public_media_url(abs_path: Path) -> str:
    # Convert ".../media/interviews/xxx.mp3" -> "/media/interviews/xxx.mp3"
    try:
        rel = abs_path.relative_to(MEDIA_ROOT)
    except ValueError:
        # fallback
        rel = abs_path.name
    return f"{MEDIA_BASE_URL}/{rel.as_posix()}"


async def _save_upload_file(
    file: UploadFile, prefix: str, ext_hint: Optional[str] = None
) -> str:
    """
    Saves UploadFile to media/interviews and returns a public URL.
    """
    # best-effort ext
    ext = ext_hint
    if not ext:
        if file.filename and "." in file.filename:
            ext = file.filename.rsplit(".", 1)[-1].lower()
        else:
            ext = "bin"

    fname = f"{prefix}_{uuid.uuid4().hex}.{ext}"
    out_path = INTERVIEW_MEDIA_DIR / fname

    data = await file.read()
    out_path.write_bytes(data)

    return _public_media_url(out_path)


async def _gtts_to_url(
    text: str,
    session_id: str,
    order_index: int,
    *,
    lang: str = "en",  # e.g. "en", "zh-TW"
    tld: str = "com",  # e.g. "com", "co.uk", "com.tw" (changes accent/voice sometimes)
    slow: bool = False,
) -> Optional[str]:
    """
    Uses gTTS (Google Translate TTS wrapper) and saves mp3 under media/interviews.
    Returns public URL (same behavior as your ElevenLabs helper).
    """
    if not text or not text.strip():
        return None

    fname = f"tts_{session_id}_{order_index}_{uuid.uuid4().hex}.mp3"
    out_path = INTERVIEW_MEDIA_DIR / fname

    def _sync_generate():
        tts = gTTS(text=text, lang=lang, tld=tld, slow=slow)
        tts.save(str(out_path))  # writes mp3
        return True

    try:
        await anyio.to_thread.run_sync(_sync_generate)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"gTTS failed: {str(e)[:300]}")

    return _public_media_url(out_path)


async def _elevenlabs_tts_to_url(
    text: str, session_id: str, order_index: int
) -> Optional[str]:
    """
    Calls ElevenLabs TTS and saves mp3 under media/interviews.
    Returns public URL.
    """
    if not text.strip():
        return None
    if not ELEVENLABS_API_KEY:
        raise HTTPException(
            status_code=500, detail="ELEVENLABS_API_KEY is not configured"
        )

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "accept": "audio/mpeg",
        "content-type": "application/json",
    }
    payload = {
        "text": text,
        "model_id": ELEVENLABS_MODEL_ID,
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=502,
                detail=f"ElevenLabs TTS failed: {resp.status_code} {resp.text[:300]}",
            )

        audio_bytes = resp.content

    fname = f"tts_{session_id}_{order_index}_{uuid.uuid4().hex}.mp3"
    out_path = INTERVIEW_MEDIA_DIR / fname
    out_path.write_bytes(audio_bytes)
    return _public_media_url(out_path)


def _detect_completed(out: dict[str, Any], last_text: str) -> bool:
    """
    Best-effort completion detection.
    Prefer explicit graph keys; fallback to common sentinel phrases.
    """
    # explicit keys (adjust if your graph uses different names)
    for k in ("completed", "is_completed", "done", "finished"):
        v = out.get(k)
        if isinstance(v, bool) and v:
            return True

    st = out.get("interview_state") or out.get("status")
    if isinstance(st, str) and st.lower() in (
        "completed",
        "done",
        "finished",
        "ended",
        "end",
    ):
        return True

    # fallback: if your interviewer says something like "Interview completed."
    lowered = (last_text or "").strip().lower()
    if any(
        p in lowered
        for p in (
            "interview completed",
            "end of interview",
            "we are done",
            "that's all",
        )
    ):
        return True

    return False


async def _get_latest_interaction(
    db: AsyncSession, session_id: str
) -> Optional[InterviewInteraction]:
    """
    Returns the latest interaction by max(order_index).
    """
    stmt = (
        select(InterviewInteraction)
        .where(InterviewInteraction.session_id == session_id)
        .order_by(InterviewInteraction.order_index.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def _get_pending_answer_interaction(
    db: AsyncSession, session_id: str
) -> Optional[InterviewInteraction]:
    """
    Finds the latest interaction that still needs a user answer (user_answer_text is NULL).
    This is where we attach user's transcript/audio for scoring graph.
    """
    stmt = (
        select(InterviewInteraction)
        .where(
            InterviewInteraction.session_id == session_id,
            InterviewInteraction.user_answer_text.is_(None),
        )
        .order_by(InterviewInteraction.order_index.desc())
        .limit(1)
    )
    res = await db.execute(stmt)
    return res.scalar_one_or_none()


async def _set_session_completed(db: AsyncSession, session_id: str) -> None:
    await db.execute(
        update(InterviewSession)
        .where(InterviewSession.id == session_id)
        .values(status="completed", updated_at=func.now())
    )


async def _run_background_once(session_id: str) -> None:
    """
    Runs ONE background cycle:
    1) score ONE answered-but-ungraded interaction (if exists)
    2) generate ONE hard question (if eligible)
    """
    await SCORING_APP.ainvoke(
        {"session_id": session_id},
        config={"configurable": {"thread_id": f"{session_id}:score"}},
    )

    await HARD_APP.ainvoke(
        {"session_id": session_id},
        config={"configurable": {"thread_id": f"{session_id}:hard"}},
    )


# -----------------------------
# Routes
# -----------------------------
@router.get("", response_model=InterviewHistoryResponse)
async def list_interviews(user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as db:
        # Only sessions owned by this user
        stmt = (
            select(InterviewSession)
            .where(InterviewSession.user_id == user.id)
            .order_by(InterviewSession.updated_at.desc())
            .limit(50)
        )
        res = await db.execute(stmt)
        sessions = res.scalars().all()

        items: list[InterviewHistoryItem] = []
        for s in sessions:
            items.append(
                InterviewHistoryItem(
                    session_id=s.id,
                    status=getattr(s, "status", "active"),
                    created_at=getattr(s, "created_at", None),
                    updated_at=getattr(s, "updated_at", None),
                )
            )

        return InterviewHistoryResponse(items=items)


@router.get("/{session_id}", response_model=dict)
async def get_interview_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    repo = InterviewRepo(db)
    await repo.assert_session_owner(session_id, user.id)

    sess = await repo.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    return {
        "session_id": sess.id,
        "status": sess.status,
        "max_index": sess.max_index,
        "created_at": getattr(sess, "created_at", None),
    }


@router.get("/{session_id}/review", response_model=InterviewReviewResponse)
async def get_interview_review(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    repo = InterviewRepo(db)
    await repo.assert_session_owner(session_id, user.id)

    sess = await repo.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")

    rows = await repo.get_session_review_rows(session_id)

    total = len(rows)
    graded = sum(1 for r in rows if getattr(r, "grade_data", None) is not None)

    items = []
    for r in rows:
        items.append(
            ReviewItem(
                order_index=r.order_index,
                question_text=getattr(r, "question_text", None),
                question_audio_url=getattr(r, "question_audio_url", None),
                user_answer_text=getattr(r, "user_answer_text", None),
                user_answer_audio_url=getattr(r, "user_answer_audio_url", None),
                grade_data=getattr(r, "grade_data", None),
            )
        )

    return InterviewReviewResponse(
        session_id=sess.id,
        status=sess.status,
        max_index=sess.max_index,
        total_questions=total,
        graded_questions=graded,
        items=items,
    )


@router.post("", response_model=CreateInterviewResponse)
async def create_interview(
    background: BackgroundTasks,
    raw_jd: str = Form(...),
    raw_resume: Optional[str] = Form(None),
    resume_file: Optional[UploadFile] = File(None),
    user: User = Depends(get_current_user),
):
    # 1) Create DB session row
    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        session_id = await repo.create_session(user_id=user.id)
        await db.commit()

    # 2) Prepare initial state
    resume_text = raw_resume or ""

    resume_pdf_bytes: bytes = b""
    if resume_file:
        # PDF only for upload
        is_pdf = resume_file.content_type == "application/pdf" or (
            resume_file.filename or ""
        ).lower().endswith(".pdf")
        if not is_pdf:
            raise HTTPException(status_code=400, detail="resume_file must be a PDF")

        data = await resume_file.read()

        # optional but recommended: signature check
        if not data.startswith(b"%PDF"):
            raise HTTPException(
                status_code=400, detail="Invalid PDF (missing %PDF header)"
            )

        resume_pdf_bytes = data

    init_state = {
        "session_id": session_id,
        "raw_resume": resume_text,  # ✅ keep raw resume text
        "raw_jd": raw_jd,
        "resume_pdf_input": resume_pdf_bytes,  # ✅ bytes for your graph
        "problem_set": [],
        "current_index": 0,
        "interview_state": "ongoing",
    }

    # 3) Run onboarding synchronously
    await ONBOARDING_APP.ainvoke(
        init_state, config={"configurable": {"thread_id": session_id}}
    )

    # 4) Kick knowledge in background
    background.add_task(
        KNOWLEDGE_APP.ainvoke,
        init_state,
        {"configurable": {"thread_id": f"{session_id}:know"}},
    )

    return CreateInterviewResponse(session_id=session_id, status="in_progress")


@router.post("/{session_id}/start", response_model=StartResponse)
async def start_interview(session_id: str, user: User = Depends(get_current_user)):
    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        await repo.assert_session_owner(session_id, user.id)

        sess = await repo.get_session(session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        if sess.status != "active":
            return StartResponse(
                status="completed",
                question_text="Interview completed.",
                question_audio_url=None,
            )

        row = await repo.next_unanswered(session_id)

        # no question yet -> waiting (background may create more)
        if not row:
            return StartResponse(
                status="waiting",
                question_text="Generating next question...",
                question_audio_url=None,
            )

        # if already has audio_url, just return it (polling safe)
        if row.audio_url:
            return StartResponse(
                status="in_progress",
                question_text=row.question_content,
                question_audio_url=row.audio_url,
            )

        # generate once
        audio_url = await _gtts_to_url(
            row.question_content, session_id=session_id, order_index=row.order_index
        )
        if audio_url:
            row.audio_url = audio_url
            await db.commit()

        return StartResponse(
            status="in_progress",
            question_text=row.question_content,
            question_audio_url=audio_url,
        )


@router.post("/{session_id}/answer", response_model=AnswerResponse)
async def submit_answer(
    session_id: str,
    background: BackgroundTasks,
    answer_text: Optional[str] = Form(None),
    answer_audio: Optional[UploadFile] = File(None),
    user: User = Depends(get_current_user),
):
    if not answer_audio:
        raise HTTPException(status_code=400, detail="answer_audio is required")
    if not answer_text or not answer_text.strip():
        raise HTTPException(
            status_code=400, detail="answer_text transcript is required"
        )

    # 1) save answer to the CURRENT asked question (audio_url != null, unanswered)
    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        await repo.assert_session_owner(session_id, user.id)

        sess = await repo.get_session(session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        if sess.status != "active":
            return AnswerResponse(
                status="completed", question_text=None, question_audio_url=None
            )

        current = await repo.get_current_asked_unanswered(session_id)
        if not current:
            raise HTTPException(
                status_code=409,
                detail="No active question is waiting for your answer (maybe still generating).",
            )

        user_audio_url = await _save_upload_file(
            answer_audio, prefix=f"user_{session_id}", ext_hint="webm"
        )
        current.user_audio_url = user_audio_url
        current.user_answer_text = answer_text.strip()
        await db.commit()

    # 2) background: score + hard gen
    background.add_task(_run_background_once, session_id)

    # 3) return next question (same as /start behavior)
    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        sess = await repo.get_session(session_id)

        row = await repo.next_unanswered(session_id)

        # completion logic based on onboarding max_index
        max_idx = getattr(sess, "max_index", None)
        if row is None:
            if max_idx is not None:
                # ✅ must ensure 0..max_idx all exist (no gaps)
                covered = await repo.count_interactions(session_id)
                if covered < (max_idx + 1):
                    # still generating / missing rows
                    return AnswerResponse(
                        status="waiting",
                        question_text="Generating next question...",
                        question_audio_url=None,
                    )

                # ✅ now safe to check unanswered
                unanswered = await repo.count_unanswered_upto(session_id, max_idx)
                if unanswered == 0:
                    await repo.set_session_status(session_id, "completed")
                    await db.commit()
                    return AnswerResponse(
                        status="completed", question_text=None, question_audio_url=None
                    )

            return AnswerResponse(
                status="waiting",
                question_text="Generating next question...",
                question_audio_url=None,
            )
        # ensure audio url exists (polling safe)
        if not row.audio_url:
            audio_url = await _gtts_to_url(
                row.question_content, session_id=session_id, order_index=row.order_index
            )
            if audio_url:
                row.audio_url = audio_url
                await db.commit()
        else:
            audio_url = row.audio_url

        return AnswerResponse(
            status="in_progress",
            question_text=row.question_content,
            question_audio_url=audio_url,
        )
