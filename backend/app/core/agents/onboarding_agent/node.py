from __future__ import annotations

from app.core.llm import get_llm
from app.core.state import InterviewState
from app.core.schema import Candidate, Problem, QuestionGenerationTask
from langgraph.types import Send

from app.db.session import AsyncSessionLocal
from app.db.repositories.interview_repo import InterviewRepo


async def extractor_node(state: InterviewState):
    print("--- 🚀 Starting Extractoring Node ---")
    llm = get_llm()
    extractor_llm = llm.with_structured_output(Candidate)

    extract_prompt = f"""
You are an expert recruiter. Extract the candidate's profile from the resume below.
You should consider the Job Description to identify a list of 3 skills that relevant to the Job Role.
Remember the skills should only be related to Job Role
For example, If job role is backend only, then the React shouldn't be identify as a skill for candidate

RESUME:
{state["raw_resume"]}

JOB DESCRIPTION:
{state["raw_jd"]}
""".strip()

    candidate_obj = await extractor_llm.ainvoke(extract_prompt)
    print(f"✅ Extracted: {candidate_obj.name} applying for {candidate_obj.apply_role}")
    return {"candidate": candidate_obj}


def initiate_generate_questions(state: InterviewState):
    """
    Dispatch parallel question generation tasks.
    IMPORTANT: we pass session_id so each task can write to DB.
    """
    print("--- 🔀 Dispatching Parallel Generation Tasks ---")
    candidate = state["candidate"]
    session_id = state["session_id"]

    # Use 0-based order_index to match your current_index default = 0
    return [
        Send("generate_questions_node", {
            "session_id": session_id,
            "competency": skill,
            "target_id": i,  # 0-based index
            "candidate_name": candidate.name,
            "candidate_skills": candidate.skills,
        })
        for i, skill in enumerate(candidate.skills)
    ]


async def generate_questions_node(state: QuestionGenerationTask):
    """
    Generate one Problem and upsert into DB at a fixed order_index (target_id).
    This avoids race conditions when tasks run in parallel.
    """
    print(f"--- ⚡ Generating Q#{state['target_id']} for {state['competency']} ---")
    llm = get_llm()
    generator_llm = llm.with_structured_output(Problem)

    question_prompt = f"""
Generate an interview question for {state['candidate_name']}.
The question should be answerable in words.

CRITICAL REQUIREMENTS:
- id: MUST be exactly {state['target_id']}
- competency: {state['competency']}
- topic: Based on {state['competency']}
- content: The question text.
- difficulty: easy or medium.

RESTRICTION:
- Do NOT generate 'reference_answer', 'candidate_response', 'grade'.
- Leave them null.
""".strip()

    problem = await generator_llm.ainvoke(question_prompt)
    problem.id = state["target_id"]

    # Store to DB
    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        await repo.upsert_question_at_index(
            session_id=state["session_id"],
            order_index=problem.id,
            question_content=problem.content,
            # Store meta (topic/competency/difficulty) into reference_data (safe extra keys)
            reference_data={
                "meta": {
                    "topic": problem.topic,
                    "competency": problem.competency,
                    "difficulty": problem.difficulty,
                }
            },
        )
        await db.commit()

    # Optional: still return to state if you want (not required if DB-first)
    return {"problem_set": [problem]}


async def next_phase_node(state: InterviewState):
    """
    Once initial questions are written to DB, set indices based on DB max index.
    """
    session_id = state["session_id"]

    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        max_idx = await repo.get_max_order_index(session_id)  # -1 if none
        await db.commit()

    current_count = max_idx + 1 if max_idx >= 0 else 0
    total_limit = current_count * 2

    print(f"   📊 Questions Ready: {current_count}")
    print(f"   🎯 Total Goal: {total_limit}")

    return {
        "max_index": total_limit - 1,
        "ready_question_index": max_idx,  # last question index available
    }
