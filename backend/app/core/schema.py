import operator
from pydantic import BaseModel, Field, computed_field
from typing import Annotated, List, Literal, Optional
from typing_extensions import TypedDict


class Candidate(BaseModel):
    name: str = Field(description="The name of the candidate")
    apply_role: str = Field(description = "The role that candidate want to apply")
    skills: List[str] = Field(description="List of skills the candidate possesses related to applying job role")

class QuestionGenerationTask(TypedDict):
    competency: str
    target_id: int
    candidate_name: str
    candidate_skills: List[str] # passed for context
    
            
class Reference_answer(BaseModel):
    reference_answer: str
    key_criteria: List[str] = Field(description="List of details the candidate MUST say.")
    
class Grade(BaseModel):
    accuracy_score: int = Field(description="1-10: Correctness of technical facts.")
    communication_score: int = Field(description="1-10: Clarity, structure, and conciseness.")
    completeness_score: int = Field(description="1-10: Coverage of key criteria and depth.")
    
    feedback: str = Field(description="Specific advice on how to improve.")
    @computed_field
    def final_score(self) -> float:
        # Example weighting: Accuracy is king (50%), others are 25%
        return (self.accuracy_score * 0.5) + (self.communication_score * 0.25) + (self.completeness_score * 0.25)
    
class Problem(BaseModel):
    id: int
    difficulty: Literal["easy", "medium", "hard"]
    topic: str
    competency: str = Field(description="Specific skill (e.g. 'SQL Joins')")
    content: str = Field(description="The question to ask candidate")
    
    
    reference_answer: Optional[Reference_answer] = Field(default=None, description="Leave blank for now")
    candidate_response: Optional[str] = Field(default=None, description="Filled by user later")
    grade: Optional[Grade] = Field(default=None, description="Leave blank for now")
    
    
class SearchQuery(BaseModel):
    search_query: str = Field(None, description="Search query for retrieval.")