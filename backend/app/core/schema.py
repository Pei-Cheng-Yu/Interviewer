import operator
from pydantic import BaseModel, Field
from typing import Annotated, List, Literal, Optional
from typing_extensions import TypedDict


class Candidate(BaseModel):
    name: str = Field(description="The name of the candidate")
    apply_role: str = Field(description = "The role that candidate want to apply")
    skills: List[str] = Field(description="List of skills the candidate possesses")

class QuestionGenerationTask(TypedDict):
    competency: str
    target_id: int
    candidate_name: str
    candidate_skills: List[str] # passed for context
    
            
class Reference_answer(BaseModel):
    reference_answer: str
    key_criteria: List[str] = Field(description="List of details the candidate MUST say.")
    
class Problem(BaseModel):
    id: int
    difficulty: Literal["easy", "medium", "hard"]
    topic: str
    competency: str = Field(description="Specific skill (e.g. 'SQL Joins')")
    content: str = Field(description="The question to ask candidate")
    
    
    reference_answer: Optional[Reference_answer] = Field(default=None, description="Leave blank for now")
    candidate_response: Optional[str] = Field(default=None, description="Filled by user later")
    score: Optional[int] = Field(default=None, description="Filled by scorer later")
    feedback: Optional[str] = Field(default=None, description="Filled by scorer later")
    
    
class SearchQuery(BaseModel):
    search_query: str = Field(None, description="Search query for retrieval.")