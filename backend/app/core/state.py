import operator
from pydantic import BaseModel, Field
from typing import Annotated, List, Literal
from typing_extensions import TypedDict
from langgraph.graph import END, MessagesState, START, StateGraph

class Candidate(BaseModel):
    name: str = Field(description="The name of the candidate")
    apply_role: str = Field(description = "The role that candidate want to apply")
    skills: List[str] = Field(description="List of skills the candidate possesses")
    
class Problem(BaseModel):
    difficulty: Literal["easy", "medium", "hard"]
    content: str = Field(description="The question to ask candidate")
    reference_answer: str = Field(description="The reference answer for Evaluation")
    candidate_response: str = Field(description="The response from the candidate")
    
class InterviewState(MessagesState):
    problem_set: List[Problem] = []