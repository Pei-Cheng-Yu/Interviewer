from app.core.state import ScoringState
from app.core.schema import Problem, Grade
from pydantic import BaseModel, Field
from typing import Annotated, List, Literal, Optional
from typing_extensions import TypedDict
import operator
from app.core.llm import get_llm
from app.core.agents.scoring_agent.prompt import SCORING_SYSTEM_PROMPT
from app.core.agents.scoring_agent.config import SCORING_CRITERIA
from langgraph.graph import END
from app.core.store import InterviewStore
from app.db.session import AsyncSessionLocal
from app.db.repositories.interview_repo import InterviewRepo
from .utils import _row_to_problem

class Score(BaseModel):
    score: int = Field(..., description="1-10 score")
    feedback: str = Field(..., description="One clear feedback item")


class SummaryFeedback(BaseModel):
    feedback: str


   
async def pick_target_node(state: ScoringState) -> ScoringState:
    """
    Load the next answered-but-ungraded interaction from DB,
    and prepare problem for scoring.
    """
    session_id = state["session_id"]

    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        row = await repo.next_ungraded_answered(session_id)

    # Nothing to score
    if not row:
        return {
            "session_id": session_id,
            "interaction_id": None,
            "problem": None,
            "accuracy_score": None,
            "communication_score": None,
            "completeness_score": None,
            "feedbacks": [],
        }

    return {
        "session_id": session_id,
        "interaction_id": row.id,
        "problem": _row_to_problem(row),
        "feedbacks": [],
    }


def has_target_router(state: ScoringState):
    """
    Conditional router for graph wiring:
    - if interaction_id is None -> END
    - else -> continue scoring pipeline
    """
    return "accuracy_score_node" if state.get("interaction_id") else "__end__"


async def accuracy_score_node(state: ScoringState):
    print("--- 💾 Scoring Accuracy ---")

    problem = state["problem"]
    if not problem:
        return {}

    llm = get_llm()
    criteria = SCORING_CRITERIA["accuracy"]

    formatted_prompt = SCORING_SYSTEM_PROMPT.format(
        question=problem.content,
        reference_answer=problem.reference_answer.model_dump() if problem.reference_answer else None,
        candidate_answer=problem.candidate_response,
        criteria_name=criteria["name"],
        criteria_definition=criteria["definition"],
    )

    score_obj = await llm.with_structured_output(Score).ainvoke(formatted_prompt)
    return {"accuracy_score": score_obj.score, "feedbacks": [score_obj.feedback]}


async def communication_score_node(state: ScoringState):
    print("--- 💾 Scoring Communication ---")

    problem = state["problem"]
    if not problem:
        return {}

    llm = get_llm()
    criteria = SCORING_CRITERIA["communication"]

    formatted_prompt = SCORING_SYSTEM_PROMPT.format(
        question=problem.content,
        reference_answer=problem.reference_answer.model_dump() if problem.reference_answer else None,
        candidate_answer=problem.candidate_response,
        criteria_name=criteria["name"],
        criteria_definition=criteria["definition"],
    )

    score_obj = await llm.with_structured_output(Score).ainvoke(formatted_prompt)
    return {"communication_score": score_obj.score, "feedbacks": [score_obj.feedback]}


async def completeness_score_node(state: ScoringState):
    print("--- 💾 Scoring Completeness ---")

    problem = state["problem"]
    if not problem:
        return {}

    llm = get_llm()
    criteria = SCORING_CRITERIA["completeness"]

    formatted_prompt = SCORING_SYSTEM_PROMPT.format(
        question=problem.content,
        reference_answer=problem.reference_answer.model_dump() if problem.reference_answer else None,
        candidate_answer=problem.candidate_response,
        criteria_name=criteria["name"],
        criteria_definition=criteria["definition"],
    )

    score_obj = await llm.with_structured_output(Score).ainvoke(formatted_prompt)
    return {"completeness_score": score_obj.score, "feedbacks": [score_obj.feedback]}


async def summarize_and_save_node(state: ScoringState):
    """
    Summarize feedbacks, build Grade, save into InterviewInteraction.grade_data in DB.
    """
    print("--- 💾 Summarizing + Saving Grade ---")

    interaction_id = state.get("interaction_id")
    problem = state.get("problem")

    if not interaction_id or not problem:
        return {}

    llm = get_llm()

    summary_prompt = f"""
Please summarize the following feedback items into ONE improvement-focused paragraph.
Keep it constructive and specific.

Feedback items:
{state.get("feedbacks", [])}
""".strip()

    summary = await llm.with_structured_output(SummaryFeedback).ainvoke(summary_prompt)

    final_grade = Grade(
        accuracy_score=state.get("accuracy_score") or 0,
        communication_score=state.get("communication_score") or 0,
        completeness_score=state.get("completeness_score") or 0,
        feedback=summary.feedback,
    )

    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        await repo.save_grade_by_id(interaction_id, final_grade.model_dump(mode="json"))
        await db.commit()

    # Optionally return something small; most pipelines just END after save
    return {}


# -----------------------------
# Optional: loop router
# -----------------------------

def loop_or_end_router(state: ScoringState):
    """
    If you want to score ALL available answers in one run:
    After summarize_and_save_node -> go back to pick_target_node.
    Otherwise, just END in your graph wiring.
    """
    return "pick_target_node"