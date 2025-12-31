import asyncio

from app.core.agents.hard_question_agent.agent import build_hard_question_graph
from app.core.agents.interviewer_agent.agent import build_interviewer_graph
from app.core.agents.knowledge_agent.agent import build_knowledge_graph  # optional
from app.core.agents.onboarding_agent.agent import build_onboarding_graph
from app.core.agents.scoring_agent.agent import build_scoring_graph
from app.core.llm import get_llm
from app.db.models import InterviewInteraction, User
from app.db.repositories.interview_repo import InterviewRepo
from app.db.session import AsyncSessionLocal
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from sqlalchemy import Integer, cast, func, select

USER_ID = 1


# -----------------------------
# Helpers
# -----------------------------
async def ensure_test_user(user_id: int):
    async with AsyncSessionLocal() as db:
        exists = await db.scalar(select(User.id).where(User.id == user_id))
        if exists:
            return
        db.add(
            User(
                id=user_id,
                email=f"test{user_id}@example.com",
                hashed_password="not-a-real-hash",
                full_name="Test User",
            )
        )
        await db.commit()


async def create_session_for_user(user_id: int) -> str:
    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        sid = await repo.create_session(user_id)
        await db.commit()
        return sid


async def generate_candidate_response(question_text: str, persona: str) -> str:
    llm = get_llm()
    prompt = f"""
You are a job candidate in an interview.
PERSONA: {persona}
QUESTION: "{question_text}"

Give a concise, spoken-style answer (1-2 sentences).
""".strip()
    res = await llm.ainvoke(prompt)
    return res.content


async def db_next_unanswered(session_id: str):
    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        return await repo.next_unanswered(session_id)


async def db_counts(session_id: str) -> dict:
    """Counts for debugging & stopping conditions."""
    meta = InterviewInteraction.reference_data["meta"]

    async with AsyncSessionLocal() as db:
        total = await db.scalar(
            select(func.count())
            .select_from(InterviewInteraction)
            .where(InterviewInteraction.session_id == session_id)
        )
        unanswered = await db.scalar(
            select(func.count())
            .select_from(InterviewInteraction)
            .where(
                InterviewInteraction.session_id == session_id,
                InterviewInteraction.user_answer_text.is_(None),
            )
        )
        ungraded_answered = await db.scalar(
            select(func.count())
            .select_from(InterviewInteraction)
            .where(
                InterviewInteraction.session_id == session_id,
                InterviewInteraction.user_answer_text.is_not(None),
                InterviewInteraction.grade_data.is_(None),
            )
        )
        hard_total = await db.scalar(
            select(func.count())
            .select_from(InterviewInteraction)
            .where(
                InterviewInteraction.session_id == session_id,
                meta["difficulty"].as_string() == "hard",
            )
        )

    return {
        "total": int(total or 0),
        "unanswered": int(unanswered or 0),
        "ungraded_answered": int(ungraded_answered or 0),
        "hard_total": int(hard_total or 0),
    }


async def hard_exists_for_base(session_id: str, base_idx: int) -> bool:
    """
    Checks if a hard follow-up already exists for base question order_index=base_idx.
    Requires hard rows store:
      reference_data.meta.difficulty = "hard"
      reference_data.meta.parent_order_index = <base_idx>
    """
    meta = InterviewInteraction.reference_data["meta"]
    async with AsyncSessionLocal() as db:
        n = await db.scalar(
            select(func.count())
            .select_from(InterviewInteraction)
            .where(
                InterviewInteraction.session_id == session_id,
                meta["difficulty"].as_string() == "hard",
                cast(meta["parent_order_index"].as_string(), Integer) == base_idx,
            )
        )
    return (n or 0) > 0


async def base_is_graded(session_id: str, base_idx: int) -> bool:
    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        row = await repo.get_by_order(session_id, base_idx)
        if not row:
            return False
        return (row.user_answer_text is not None) and (row.grade_data is not None)


# -----------------------------
# Background worker (parallel)
# -----------------------------
async def background_worker(
    session_id: str,
    base_count: int,
    max_total: int,
    knowledge_state: dict | None = None,
    *,
    tick: float = 0.25,
):
    """
    Producer in parallel:
    - scores answered-but-ungraded
    - generates hard follow-ups (at most one per base question)
    - (optional) fills missing reference answers via knowledge graph
    """
    scoring_app = build_scoring_graph()
    hard_app = build_hard_question_graph()
    knowledge_app = build_knowledge_graph() if knowledge_state else None

    base_ptr = 0  # which base question index we're trying to generate hard for

    while True:
        # Stop producing once we've reached the target total
        counts = await db_counts(session_id)
        if counts["total"] >= max_total:
            # still allow scoring to finish if any leftover ungraded
            if counts["ungraded_answered"] == 0:
                await asyncio.sleep(tick)
                continue

        # 1) Score (DB-first). Safe no-op if nothing to score.
        if counts["ungraded_answered"] > 0:
            try:
                await scoring_app.ainvoke({"session_id": session_id})
            except Exception as e:
                print(f"[BG] scoring error: {e}")

        # 2) Generate hard follow-up only when eligible:
        #    - base_ptr < base_count
        #    - base is graded
        #    - hard doesn't exist for base
        #    - total < max_total
        counts = await db_counts(session_id)
        if counts["total"] < max_total and base_ptr < base_count:
            try:
                if await base_is_graded(
                    session_id, base_ptr
                ) and not await hard_exists_for_base(session_id, base_ptr):
                    # One hard generation attempt for this base
                    await hard_app.ainvoke(
                        {
                            "session_id": session_id,
                            "generate_target_index": base_ptr,
                            "research_target_index": None,
                            "scoring_index": 999999,  # ignored if DB-gated in your hard agent
                            "max_index": max_total - 1,
                        }
                    )

                    # Optionally fill reference for newly created hard questions
                    if knowledge_app and knowledge_state:
                        try:
                            await knowledge_app.ainvoke(knowledge_state)
                        except Exception as e:
                            print(f"[BG] knowledge error: {e}")

                    # Move to next base after successfully generating/attempting for this base
                    base_ptr += 1
                else:
                    # If base not ready yet, don't advance ptr; wait a bit
                    pass
            except Exception as e:
                print(f"[BG] hard gen error: {e}")

        # yield to let interviewer continue
        await asyncio.sleep(tick)


# -----------------------------
# Main test
# -----------------------------
async def main():
    await ensure_test_user(USER_ID)
    session_id = await create_session_for_user(USER_ID)
    print(f"\n✅ Created InterviewSession: {session_id}\n")

    # Phase 1: Onboarding + (optional) knowledge
    onboarding_graph = build_onboarding_graph()
    knowledge_graph = build_knowledge_graph()

    initial_state = {
        "session_id": session_id,
        "raw_resume": "I am Pei-Cheng. I know Python and React, have wrote some backend api for my school's lab.",
        "raw_jd": "Looking for a Backend Engineer.",
        "problem_set": [],
        "current_index": 0,
        "ready_question_index": 0,
        "max_index": 6,
        "interview_state": "ongoing",
        "messages": [],
    }

    print("--- 🏃 Running Onboarding Graph ---")
    prepared_state = await onboarding_graph.ainvoke(initial_state)

    # This is optional; if it’s slow / rate-limited, you can comment it out
    print("--- 🧠 Running Knowledge Graph ---")
    try:
        prepared_state = await knowledge_graph.ainvoke(prepared_state)
    except Exception as e:
        print(f"[Prep] knowledge graph failed (ok for test): {e}")

    # Base count = number of initial questions in DB BEFORE hard generation starts
    # Since we haven't generated hard yet, total interactions == base_count.
    counts = await db_counts(session_id)
    base_count = counts["total"]
    max_total = base_count * 2
    print(
        f"\n✅ Prep complete. DB has {base_count} base interactions. Target total={max_total}.\n"
    )

    # Phase 2: Interviewer (consumer) + background worker (producer)
    shared_memory = MemorySaver()
    interview_app = build_interviewer_graph(checkpointer=shared_memory)

    thread_config = {
        "configurable": {"thread_id": "test_interview", "user_id": USER_ID}
    }
    interview_app.update_state(thread_config, prepared_state)

    # Start background worker (DO NOT await)
    # Pass prepared_state as knowledge_state so knowledge graph can run DB-first dispatch
    bg_task = asyncio.create_task(
        background_worker(
            session_id=session_id,
            base_count=base_count,
            max_total=max_total,
            knowledge_state=prepared_state,  # set to None if you want to disable knowledge in background
            tick=0.25,
        )
    )

    print("\n--- 🔵 PHASE 2: INTERVIEW LOOP (parallel background) ---\n")

    # Ask first question
    step = await interview_app.ainvoke({}, config=thread_config)
    ai_msg = step["messages"][-1].content
    print(f"🤖 AI: {ai_msg}")

    while True:
        # If interviewer ever returns "No more questions", we poll DB until producer adds one,
        # or we end when we've reached target and nothing remains unanswered.
        row = await db_next_unanswered(session_id)
        if not row:
            c = await db_counts(session_id)
            if c["total"] >= max_total and c["unanswered"] == 0:
                print("\n🏁 Reached target and no unanswered questions left. Ending.")
                break

            print("\n[Interviewer] No available question yet. Polling DB...")
            while True:
                row = await db_next_unanswered(session_id)
                if row:
                    break
                c = await db_counts(session_id)
                if c["total"] >= max_total and c["unanswered"] == 0:
                    print(
                        "\n🏁 Reached target and no unanswered questions left. Ending."
                    )
                    bg_task.cancel()
                    try:
                        await bg_task
                    except asyncio.CancelledError:
                        pass
                    return
                await asyncio.sleep(0.25)

            # Resume interviewer to speak the now-available question
            step = await interview_app.ainvoke({}, config=thread_config)
            ai_msg = step["messages"][-1].content
            print(f"\n🤖 AI: {ai_msg}")

        # Candidate answers
        candidate_reply = await generate_candidate_response(
            ai_msg,
            persona="A junior backend dev who is nervous but knows Python basics",
        )
        print(f"\n👤 Candidate: {candidate_reply}")

        # Interviewer saves answer
        await interview_app.ainvoke(
            {"messages": [HumanMessage(content=candidate_reply)]},
            config=thread_config,
        )

        # Immediately ask next question (do NOT wait for scoring/hard)
        step = await interview_app.ainvoke({}, config=thread_config)
        ai_msg = step["messages"][-1].content
        print(f"\n🤖 AI: {ai_msg}")

        # Debug stats (optional)
        c = await db_counts(session_id)
        print(
            f"   [DB] total={c['total']} unanswered={c['unanswered']} ungraded_answered={c['ungraded_answered']} hard_total={c['hard_total']}"
        )

        # End condition if we've reached 2N and nothing left unanswered
        if c["total"] >= max_total and c["unanswered"] == 0:
            print("\n🏁 Finished: reached 2N and answered all.")
            break

    # Cleanup background worker
    bg_task.cancel()
    try:
        await bg_task
    except asyncio.CancelledError:
        pass

    print("\n✅ Test finished cleanly.")


if __name__ == "__main__":
    asyncio.run(main())
