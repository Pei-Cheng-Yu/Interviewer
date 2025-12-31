import os

from app.core.agents.hard_question_agent.prompt import (
    HARD_SCENARIO_PROMPT,
    QUERY_PROMPT,
)
from app.core.llm import get_llm
from app.core.schema import ReferenceAnswer, SearchQuery
from app.core.state import BackGroundState
from app.db.repositories.interview_repo import InterviewRepo
from app.db.session import AsyncSessionLocal
from dotenv import load_dotenv
from langchain_community.utilities import GoogleSerperAPIWrapper
from pydantic import BaseModel, Field

load_dotenv()
os.environ["SERPER_API_KEY"] = os.getenv("SERPER_API_KEY")
search = GoogleSerperAPIWrapper()


class HardQuestionOutput(BaseModel):
    scenario_content: str = Field(
        description="The detailed engineering scenario and question to ask the candidate."
    )
    technical_focus: str = Field(
        description="The specific sub-concept being tested (e.g., 'Database Locking')."
    )


async def index_checker(state: BackGroundState):
    session_id = state["session_id"]

    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)

        session = await repo.get_session(session_id)
        max_total = (session.max_index + 1) if session.max_index is not None else 7

        total = await repo.count_interactions(session_id)
        if total >= max_total:
            return "__end__"

        base_idx = await repo.get_next_base_idx_for_hard(session_id)
        print(f"auto-picked base_idx: {base_idx}")

        if base_idx is None:
            return "__end__"

        # put it into state so generate_hard_node knows which parent to use
        state["generate_target_index"] = int(base_idx)
        return "generate_hard_node"


async def generate_hard_node(state: BackGroundState):
    print("--- 🧠 Generating Hard Scenario ---")
    llm = get_llm(temperature=0.7)

    session_id = state["session_id"]
    base_idx = state.get("generate_target_index", 0)

    # Load base question + user answer from DB
    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        base_row = await repo.get_by_order(session_id, base_idx)
        if not base_row or not base_row.user_answer_text:
            # Nothing to build on
            return {"generate_target_index": base_idx + 1}

    prompt = HARD_SCENARIO_PROMPT.format(
        topic=(base_row.reference_data or {}).get("meta", {}).get("topic", "general"),
        prev_question=base_row.question_content,
        prev_answer=base_row.user_answer_text,
    )

    result = await llm.with_structured_output(HardQuestionOutput).ainvoke(prompt)

    # Append new hard question to DB (max+1)
    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        new_row = await repo.append_question(
            session_id=session_id,
            question_content=result.scenario_content,
            reference_data={
                "meta": {
                    "topic": (base_row.reference_data or {})
                    .get("meta", {})
                    .get("topic", "general"),
                    "competency": result.technical_focus,
                    "difficulty": "hard",
                    "parent_order_index": base_idx,
                }
            },
        )
        await db.commit()

    print(f" [HARD] new Question ready order_index# {new_row.order_index}")

    return {
        "generate_target_index": base_idx + 1,
        "research_target_index": new_row.order_index,
    }


async def expert_query_node(state: BackGroundState):
    target_index = state.get("research_target_index")
    if target_index is None:
        print("   [Expert] No target found. Skipping.")
        return {}

    session_id = state["session_id"]

    # Load target question from DB
    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        row = await repo.get_by_order(session_id, target_index)
        if not row:
            return {"research_target_index": None}

    llm = get_llm()

    query_prompt = QUERY_PROMPT.format(
        content=row.question_content,
        topic=(row.reference_data or {}).get("meta", {}).get("topic", "general"),
        competency=(row.reference_data or {})
        .get("meta", {})
        .get("competency", "general"),
    )

    search_query = await llm.with_structured_output(SearchQuery).ainvoke(query_prompt)
    search_results = await search.arun(search_query.search_query)
    context_text = f"\nOFFICIAL SPECS / DOCS:\n{search_results}\n"

    answer_prompt = f"""
You are an Expert Interviewer. Fill the 'reference_answer' and 'key_criteria' for this question, according to the CONTEXT.

QUESTION: {row.question_content}
CONTEXT: {context_text}

INSTRUCTIONS:
1. reference_answer: A concise technical summary (max 4 sentences).
2. key_criteria: List 3 details the candidate MUST say.
""".strip()

    reference_answer = await llm.with_structured_output(ReferenceAnswer).ainvoke(
        answer_prompt
    )

    # Save reference into DB
    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        await repo.merge_reference_data(
            session_id=session_id,
            order_index=target_index,
            patch={
                "reference_answer": reference_answer.reference_answer,
                "key_criteria": reference_answer.key_criteria,
            },
        )
        await db.commit()

    return {"research_target_index": None}
