import os
import pprint
from langchain_community.utilities import GoogleSerperAPIWrapper
from app.core.llm import get_llm
from app.core.schema import Problem, SearchQuery, Reference_answer
from app.core.state import InterviewState
from langgraph.types import Send
from dotenv import load_dotenv
load_dotenv()

os.environ["SERPER_API_KEY"] = os.getenv("SERPER_API_KEY")


search = GoogleSerperAPIWrapper()

    
def initiate_expert_query(state: InterviewState):
    print("--- 🔀 Dispatching Parallel Expert Query ---")
    problem_set = state["problem_set"]
    return[
        Send("expert_query_node", 
            problem
        ) 
        for problem in problem_set
        if problem.reference_answer is None
    ]
    
async def expert_query_node(problem: Problem):
    """
    Input: A 'Problem' object (with content but no reference_answer).
    Output: The same 'Problem' object with 'reference_answer' filled.
    """
    print(f"--- 🧠 Expert Agent Processing: {problem.topic} ---")
    llm = get_llm()
    
    query_prompt = f"""
    You are a Tech Lead preparing an query for web-searching for a interview answer.
    Your goal is to generate a well-structured query for use in retrieval and / or web-search
    
    below is the original interview question:
    QUESTION: "{problem.content}"
    TOPIC: {problem.topic}
    COMPETENCY: {problem.competency}
    
    Task:
    1. First, analyze the Question information
    2. Pay particular attention to the COMPETENCY
    3. Generate a well-structured web search query
    Return ONLY the query
    """
    
    structured_llm = llm.with_structured_output(SearchQuery)
    search_query = await structured_llm.ainvoke(query_prompt)
    
    search_results = await search.arun(search_query.search_query)
    context_text = f"\nOFFICIAL SPECS / DOCS:\n{search_results}\n"
    
    
    
    
    answer_prompt = f"""
    You are an Expert Interviewer. Fill the 'reference_answer' and 'key_criteria' for this question, according to the CONTEXT.
    
    QUESTION: {problem.content}
    CONTEXT: {context_text}
    
    INSTRUCTIONS:
    1. reference_answer: A concise technical summary (max 3 sentences).
    2. key_criteria: List 2 details the candidate MUST say.
    """
    
    answer_llm = llm.with_structured_output(Reference_answer)
    reference_answer =await answer_llm.ainvoke(answer_prompt)
    problem.reference_answer = reference_answer
    
    return {"problem_set": [problem]}
    