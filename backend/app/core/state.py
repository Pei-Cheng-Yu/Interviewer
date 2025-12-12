import operator
from pydantic import BaseModel, Field
from typing import Annotated, List, Literal, Optional
from typing_extensions import TypedDict
from langgraph.graph import END, MessagesState, START, StateGraph
from app.core.utils.reduce_problems import reduce_problems
from app.core.schema import Problem, Candidate

def keep_max(old: int, new: int) -> int:
    return max(old, new)

class InterviewState(MessagesState):
    raw_resume: str
    raw_jd: str
    candidate: Optional[Candidate] = None
    problem_set: Annotated[List[Problem], reduce_problems]
    
    interview_state: Literal["ongoing", "waiting", "phase_end", "all_end"]
    
    current_index: int = 0
    max_index: int = 6
    ready_question_index: int = 0
    

    
class BackGroundState(TypedDict):
    problem_set: Annotated[List[Problem], reduce_problems]
    current_index: int = 0
    generate_target_index: int = 0
    research_target_index: int = 0
    scoring_index: int = 0
    