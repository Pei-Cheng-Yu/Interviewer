import os
from app.core.state import InterviewState, BackGroundState
from app.core.agents.hard_question_agent.prompt import HARD_SCENARIO_PROMPT, QUERY_PROMPT
from app.core.llm import get_llm
from langchain_community.utilities import GoogleSerperAPIWrapper
from pydantic import BaseModel, Field
from app.core.schema import Problem, SearchQuery, Reference_answer
from dotenv import load_dotenv
from app.core.store import InterviewStore
load_dotenv()

os.environ["SERPER_API_KEY"] = os.getenv("SERPER_API_KEY")


search = GoogleSerperAPIWrapper()

class HardQuestionOutput(BaseModel):
    scenario_content: str = Field(
        description="The detailed engineering scenario and question to ask the candidate."
    )
    technical_focus: str = Field(
        description="The specific sub-concept being tested (e.g., 'Database Locking' or 'JWT Rotation')."
    )
    
def index_checker(state: BackGroundState):
    question_index = state.get("generate_target_index", 0)
    scoring_index = state.get("scoring_index", 0)
    max_index = state.get("max_index", 0)
    if question_index < (max_index+1)/2 and question_index <= scoring_index:
        return "generate_hard_node"
    else:
        return "__end__"
    
async def generate_hard_node(state: BackGroundState):
    print("--- 🧠 Generating Hard Scenario ---")
    llm = get_llm(temperature=0.7)
    
    problem_idx = state.get("generate_target_index", 0)
    basic_problem = state["problem_set"][problem_idx]
    #job_role = state["candidate"].apply_role
    
    prompt = HARD_SCENARIO_PROMPT.format(
        
        topic = basic_problem.topic,
        prev_question = basic_problem.content,
        prev_answer = basic_problem.candidate_response
        )
    
    structured_llm = llm.with_structured_output(HardQuestionOutput)
    result = await structured_llm.ainvoke(prompt)
    
    new_problem = Problem(
        id=len(state["problem_set"]) + 1,
        difficulty="hard",
        topic=basic_problem.topic,
        competency=result.technical_focus,
        content=result.scenario_content,
        candidate_response = None,
        reference_answer=None,
        grade=None
    )
    print(f" [HARD] new Question ready ID# {new_problem.id}")
    return {
        "problem_set": [new_problem],
        "generate_target_index": problem_idx+1,
        "research_target_index": new_problem.id-1,
    }
    
async def expert_query_node(state: BackGroundState):
    """
    Input: A 'Problem' object (with content but no reference_answer).
    Output: The same 'Problem' object with 'reference_answer' filled.
    """
    target_index = state.get("research_target_index")
    if not target_index:
        print("   [Expert] No target found. Skipping.")
        return {}
    
    problem = state["problem_set"][target_index]
    print(f"--- 🧠 Expert Agent Processing: {problem.topic} ---")
    
    llm = get_llm()
    
    query_prompt = QUERY_PROMPT.format(
        content = problem.content,
        topic = problem.topic,
        competency = problem.competency
        )
    
    
    structured_llm = llm.with_structured_output(SearchQuery)
    search_query = await structured_llm.ainvoke(query_prompt)
    
    search_results = await search.arun(search_query.search_query)
    context_text = f"\nOFFICIAL SPECS / DOCS:\n{search_results}\n"
    
    
    answer_prompt = f"""
    You are an Expert Interviewer. Fill the 'reference_answer' and 'key_criteria' for this question, according to the CONTEXT.
    
    QUESTION: {problem.content}
    CONTEXT: {context_text}
    
    INSTRUCTIONS:
    1. reference_answer: A concise technical summary (max 4 sentences).
    2. key_criteria: List 3 details the candidate MUST say.
    """
    
    answer_llm = llm.with_structured_output(Reference_answer)
    reference_answer =await answer_llm.ainvoke(answer_prompt)
    updated_problem = problem.model_copy(update={
        "reference_answer": reference_answer
    })
    InterviewStore.save_problem(updated_problem)
    return {
        "problem_set": [updated_problem],
        "research_target_index": None,
    }