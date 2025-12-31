import operator
from typing import Annotated, List, Literal, Optional, Union

from app.core.schema import Candidate, Problem
from app.core.utils.reduce_problems import reduce_problems
from langgraph.graph import MessagesState
from typing_extensions import TypedDict


def keep_max(old: int, new: int) -> int:
    return max(old, new)


class InterviewState(MessagesState):
    session_id: Optional[str] = None
    resume_pdf_input: Union[str, bytes] = None
    raw_resume: str
    raw_jd: str
    candidate: Optional[Candidate] = None
    problem_set: Annotated[List[Problem], reduce_problems]

    interview_state: Literal["ongoing", "waiting", "phase_end", "all_end"]

    current_index: int = 0
    max_index: int = 6
    ready_question_index: int = 0


class BackGroundState(TypedDict):
    session_id: str
    problem_set: Annotated[List[Problem], reduce_problems]
    current_index: int = 0
    generate_target_index: int = 0
    research_target_index: int = 0
    scoring_index: int = 0


class ScoringState(TypedDict):
    session_id: str
    interaction_id: Optional[int]  # DB PK id for InterviewInteraction
    problem: Optional[Problem]

    accuracy_score: Optional[int]
    communication_score: Optional[int]
    completeness_score: Optional[int]
    feedbacks: Annotated[List[str], operator.add]
