import operator
from pydantic import BaseModel, Field
from typing import Annotated, List
from typing_extensions import TypedDict

class Candidate(BaseModel):
    name: str = Field(description="The name of the candidate")
    apply_role: str = Field(description = "The role that candidate want to apply")
    skills: List[str] = Field(description="List of skills the candidate possesses")