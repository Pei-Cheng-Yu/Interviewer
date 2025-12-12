from app.core.state import InterviewState, BackGroundState
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

class FeedBack(BaseModel):
    feedback: str
    
class Score(BaseModel):
    score: int
    feedback: FeedBack

class ScoringState(TypedDict):
    idx: int
    problem: Optional[Problem]
    accuracy_score: Optional[int]
    communication_score: Optional[int]
    completeness_score: Optional[int]
    feedbacks: Annotated[List[FeedBack], operator.add]
   
def get_interview_node(state: BackGroundState):
    problem_set = InterviewStore.get_all()

    return {
        "problem_set": problem_set,
    }
    
           
def index_checker(state: BackGroundState):
    scoring_index = state.get("scoring_index", 0) 
    response = state["problem_set"][scoring_index].candidate_response
    print(" Scoring Target Checking ......")
    #question_index = state.get("current_index", 0)
    if response :
        return "problem_extractor_node"
    return "__end__"
        
  
def problem_extractor_node(state: BackGroundState) -> ScoringState:
    idx = state.get("scoring_index", 0) 
    problem = state["problem_set"][idx]
    return{
        "idx": idx,
        "problem": problem,
        "feedbacks": []
    }     
    
async def accuracy_score_node(state: ScoringState) :
    print("--- 💾 Scoring Accuracy ---")
    llm = get_llm()
    criteria = SCORING_CRITERIA["accuracy"]

    problem = state["problem"]
    formatted_prompt = SCORING_SYSTEM_PROMPT.format(
        question= problem.content,
        reference_answer= problem.reference_answer,
        candidate_answer= problem.candidate_response,
        criteria_name= criteria["name"],
        criteria_definition= criteria["definition"]
    )
    
    structured_llm = llm.with_structured_output(Score)
    score_obj = await structured_llm.ainvoke(formatted_prompt)
    print(f" Accuracy Feedback: {score_obj.feedback}")
    return {
        "accuracy_score": score_obj.score,
        "feedbacks": [score_obj.feedback]
    }
    
async def communication_score_node(state: ScoringState) :
    print("--- 💾 Scoring Communication ---")
    llm = get_llm()
    criteria = SCORING_CRITERIA["communication"]
    

    problem = state["problem"]
    formatted_prompt = SCORING_SYSTEM_PROMPT.format(
        question= problem.content,
        reference_answer= problem.reference_answer,
        candidate_answer= problem.candidate_response,
        criteria_name= criteria["name"],
        criteria_definition= criteria["definition"]
    )
    
    structured_llm = llm.with_structured_output(Score)
    score_obj = await structured_llm.ainvoke(formatted_prompt)
    print(f" Communication Feedback: {score_obj.feedback}")
    return {
        "communication_score": score_obj.score,
        "feedbacks": [score_obj.feedback]
    }
    
async def completeness_score_node(state: ScoringState) :
    print("--- 💾 Scoring Completeness ---")
    llm = get_llm()
    criteria = SCORING_CRITERIA["completeness"]
    

    problem = state["problem"]
    formatted_prompt = SCORING_SYSTEM_PROMPT.format(
        question= problem.content,
        reference_answer= problem.reference_answer,
        candidate_answer= problem.candidate_response,
        criteria_name= criteria["name"],
        criteria_definition= criteria["definition"]
    )
    
    structured_llm = llm.with_structured_output(Score)
    score_obj = await structured_llm.ainvoke(formatted_prompt)
    print(f" Completeness Feedback: {score_obj.feedback}")
    return {
        "completeness_score": score_obj.score,
        "feedbacks": [score_obj.feedback]
    }
    
async def summarize_node(state: ScoringState) -> BackGroundState:
    print("--- 💾 Summarizing Score ---")
    idx = state["idx"]
    problem = state["problem"]
    
    llm = get_llm()
    feedback_prompt = f"""
    Please summary up a list of feedbacks into a well feedback contain structured sentences, focusing on helping candidate to make improvement.
    
    FeedBacks: {state["feedbacks"]}
    """
    structured_llm = llm.with_structured_output(FeedBack)
    result = await structured_llm.ainvoke(feedback_prompt)
    
    final_grade = Grade(
        accuracy_score = state["accuracy_score"],
        communication_score = state["communication_score"],
        completeness_score = state["completeness_score"],
        feedback = result.feedback
    )
    
    updated_problem = problem.model_copy(update={"grade": final_grade})
    #
    InterviewStore.save_problem(updated_problem)
    return {"problem_set": [updated_problem], "scoring_index": idx+1}
    