import asyncio
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.core.llm import get_llm
from app.core.state import InterviewState
from app.db.session import AsyncSessionLocal
from app.db.repositories.interview_repo import InterviewRepo

from app.core.agents.onboarding_agent.agent import build_onboarding_graph
from app.core.agents.knowledge_agent.agent import build_knowledge_graph
from app.core.agents.interviewer_agent.agent import build_interviewer_graph
from app.core.agents.scoring_agent.agent import build_scoring_graph
from app.core.agents.hard_question_agent.agent import build_hard_question_graph

from sqlalchemy import select
from app.db.models import User

USER_ID = 1  # make sure this exists in DB

async def ensure_test_user(user_id: int):
    async with AsyncSessionLocal() as db:
        exists = await db.scalar(select(User.id).where(User.id == user_id))
        if exists:
            return
        db.add(User(
            id=user_id,
            email=f"test{user_id}@example.com",
            hashed_password="not-a-real-hash",
            full_name="Test User",
        ))
        await db.commit()
        
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


async def db_max_index(session_id: str) -> int:
    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        return await repo.get_max_order_index(session_id)


async def main():
    await ensure_test_user(USER_ID)

    # ---------------------------------------------------------
    # 0) Create DB session_id first (DB-first pipeline)
    # ---------------------------------------------------------
    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        session_id = await repo.create_session(USER_ID)
        await db.commit()

    print(f"\n✅ Created InterviewSession: {session_id}\n")

    # ---------------------------------------------------------
    # 1) Phase 1: Onboarding + Knowledge (Prep)
    # ---------------------------------------------------------
    initial_state: dict = {
        "session_id": session_id,
        "raw_resume": "I am Pei-Cheng. I know Python and React, have wrote some backend API for my school's lab.",
        "raw_jd": "Looking for a Backend Engineer.",
        "problem_set": [],
        "current_index": 0,
        "ready_question_index": 0,
        "max_index": 6,
        "interview_state": "ongoing",
        "messages": [],
    }

    onboarding_graph = build_onboarding_graph()
    knowledge_graph = build_knowledge_graph()

    print("--- 🏃 Running Onboarding Graph ---")
    prepared_state = await onboarding_graph.ainvoke(initial_state)
    print("--- 🧠 Running Knowledge Graph ---")
    prepared_state = await knowledge_graph.ainvoke(prepared_state)

    print("\n✅ Prep complete.")
    print("NOTE: reference_answer/key_criteria are stored in DB (knowledge node returns {}).")

    # ---------------------------------------------------------
    # 2) Phase 2: Interviewer loop (with checkpoint memory)
    # ---------------------------------------------------------
    shared_memory = MemorySaver()
    interview_app = build_interviewer_graph(checkpointer=shared_memory)

    # scoring: DB-first (scores next ungraded answered)
    scoring_app = build_scoring_graph(checkpointer=shared_memory, with_hard=False)

    # hard question graph (DB-first hard agent you pasted)
    hard_app = build_hard_question_graph()

    thread_config = {"configurable": {"thread_id": "test_session_1", "user_id": USER_ID}}

    # Seed the interview graph state into memory
    interview_app.update_state(thread_config, prepared_state)

    print("\n--- 🔵 PHASE 2: INTERVIEW LOOP (Simulated) ---")

    # Start interview: ask first question
    step = await interview_app.ainvoke({}, config=thread_config)
    ai_msg = step["messages"][-1].content
    print(f"\n🤖 AI: {ai_msg}")

    while True:
        # Candidate answer
        candidate_reply = await generate_candidate_response(
            ai_msg,
            persona="A junior backend developer who is nervous but knows Python basics"
        )
        print(f"\n👤 Candidate: {candidate_reply}")

        # Interviewer saves answer and either speaks next or says waiting
        step = await interview_app.ainvoke(
            {"messages": [HumanMessage(content=candidate_reply)]},
            config=thread_config,
        )

        state_obj = await interview_app.aget_state(thread_config)
        state = state_obj.values
        status = state.get("interview_state", "ongoing")

        # Trigger scoring (DB-first): grade the next answered-but-ungraded item
        print("   [Background] 🧾 Triggering scoring...")
        await scoring_app.ainvoke({"session_id": session_id}, config={"configurable": {"thread_id": "score_1"}})

        # Trigger hard question generation (optional)
        # Your hard agent's index_checker depends on generate_target_index/scoring_index/max_index.
        # For a simple test: try generating exactly one hard question after each scoring.
        print("   [Background] 🧠 Triggering hard-question generation...")
        await hard_app.ainvoke({
            "session_id": session_id,
            "generate_target_index": state.get("generate_target_index", 0),
            "research_target_index": state.get("research_target_index", None),
            "scoring_index": state.get("scoring_index", 0),
            "max_index": state.get("max_index", 6),
        })

        # Print interviewer output
        ai_msg = step["messages"][-1].content
        print(f"\n🤖 AI: {ai_msg}")

        # If waiting, poll DB for new question, then resume interviewer
        if status == "waiting":
            print("   [System] Buffer empty. Polling DB for new question...")

            while True:
                ready_idx = await db_max_index(session_id)
                curr = state.get("current_index", 0)
                if ready_idx >= curr:
                    print(f"\n   [System] Ready! (DB max idx {ready_idx} >= current {curr})")
                    break
                print(".", end="", flush=True)
                await asyncio.sleep(1)

            # Resume interviewer to ask the new hard question
            step = await interview_app.ainvoke({}, config=thread_config)
            ai_msg = step["messages"][-1].content
            print(f"\n🤖 AI (Resumed): {ai_msg}")

        if status == "phase_end":
            print("\n🏁 Interview Finished.")
            break

    # Final transcript from checkpointed messages
    print("\n\n📜 FINAL TRANSCRIPT 📜")
    final_state_obj = await interview_app.aget_state(thread_config)
    for m in final_state_obj.values["messages"]:
        m.pretty_print()


if __name__ == "__main__":
    asyncio.run(main())
