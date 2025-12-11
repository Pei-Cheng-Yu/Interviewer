import operator
from pydantic import BaseModel, Field
from typing import Annotated, List, Literal, Optional
from typing_extensions import TypedDict
from langgraph.graph import END, MessagesState, START, StateGraph
from app.core.utils.reduce_problems import reduce_problems
from app.core.schema import Problem, Candidate

class InterviewState(MessagesState):
    raw_resume: str
    raw_jd: str
    candidate: Optional[Candidate] = None
    problem_set: Annotated[List[Problem], reduce_problems]
    current_index: int = 0
    max_index: int = 3
    scoring_index: int = 0