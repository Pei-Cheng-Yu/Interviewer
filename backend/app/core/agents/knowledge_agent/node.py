import os

from app.core.llm import get_llm
from app.core.schema import ReferenceAnswer, SearchQuery
from app.core.state import InterviewState
from app.db.repositories.interview_repo import InterviewRepo
from app.db.session import AsyncSessionLocal
from dotenv import load_dotenv
from langchain_community.utilities import GoogleSerperAPIWrapper
from langgraph.types import Send

load_dotenv()

os.environ["SERPER_API_KEY"] = os.getenv("SERPER_API_KEY")

search = GoogleSerperAPIWrapper()


def initiate_expert_query(state: InterviewState):
    print("--- 🔀 Dispatching Parallel Expert Query ---")
    session_id = state["session_id"]
    problem_set = state.get("problem_set", [])

    # If you want DB-first 100%, dispatch based on DB instead of problem_set.
    # For now, we use problem_set to choose which indices to enrich.
    return [
        Send(
            "expert_query_node",
            {
                "session_id": session_id,
                "order_index": p.id,  # p.id == order_index
                "topic": p.topic,
                "competency": p.competency,
            },
        )
        for p in problem_set
        if p.reference_answer is None
    ]


async def expert_query_node(state: dict):
    session_id = state["session_id"]
    order_index = state["order_index"]

    # 1) Load question from DB
    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        row = await repo.get_by_order(session_id, order_index)
        if not row:
            raise ValueError(
                f"Interaction not found: session={session_id} idx={order_index}"
            )

    llm = get_llm()

    query_prompt = f"""
You are a Tech Lead preparing a query for web-searching for an interview answer.
Return ONLY the query.

QUESTION: "{row.question_content}"
TOPIC: {state.get("topic")}
COMPETENCY: {state.get("competency")}
""".strip()

    structured_llm = llm.with_structured_output(SearchQuery)
    search_query = await structured_llm.ainvoke(query_prompt)

    search_results = search.run(search_query.search_query)
    context_text = f"\nOFFICIAL SPECS / DOCS:\n{search_results}\n"

    answer_prompt = f"""
You are an Expert Interviewer. Fill the 'reference_answer' and 'key_criteria' for this question, according to the CONTEXT.

QUESTION: {row.question_content}
CONTEXT: {context_text}

INSTRUCTIONS:
1. reference_answer: A concise technical summary (max 3 sentences).
2. key_criteria: List 2 details the candidate MUST say.
""".strip()

    answer_llm = llm.with_structured_output(ReferenceAnswer)
    reference_answer = await answer_llm.ainvoke(answer_prompt)

    # 2) Save reference_answer into DB reference_data (merge with existing meta if any)
    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        await repo.merge_reference_data(
            session_id=session_id,
            order_index=order_index,
            patch={
                "reference_answer": reference_answer.reference_answer,
                "key_criteria": reference_answer.key_criteria,
            },
        )
        await db.commit()

    return {}
