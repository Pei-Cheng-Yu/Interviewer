from app.core.llm import get_llm
from app.core.state import InterviewState
from app.core.schema import Candidate, Problem, QuestionGenerationTask
from langgraph.types import Send

async def extractor_node(state: InterviewState):
    print("--- 🚀 Starting Extractoring Node ---")
    llm = get_llm()
    
    extractor_llm = llm.with_structured_output(Candidate)
    
    extract_prompt = f"""
    You are an expert recruiter. Extract the candidate's profile from the resume below.
    You should consider the Job Description to identify a list of 3 skills that relevant to the Job Role.
    Remember the skills should only be related to Job Role
    For example, If job role is backend only, then the React shouldn't be identify as a skill for candidate
    
    RESUME:
    {state["raw_resume"]}
    
    JOB DESCRIPTION:
    {state["raw_jd"]}
    """
    
    candidate_obj = await extractor_llm.ainvoke(extract_prompt)
    print(f"✅ Extracted: {candidate_obj.name} applying for {candidate_obj.apply_role}")
    
    return {"candidate": candidate_obj}
    
    
def initiate_generate_questions(state: InterviewState):
    print("--- 🔀 Dispatching Parallel Generation Tasks ---")
    candidate = state["candidate"]
    return[
        Send("generate_questions_node", {
            "competency": skill,
            "target_id": i + 1, 
            "candidate_name": candidate.name,
            "candidate_skills": candidate.skills
        }) 
        for i, skill in enumerate(candidate.skills)
    ]
    
    
async def generate_questions_node(state: QuestionGenerationTask):    
    print(f"--- ⚡ Generating Q#{state['target_id']} for {state['competency']} ---")
    llm = get_llm()
    generator_llm = llm.with_structured_output(Problem)
    
    question_prompt = f"""
    Generate an interview question for {state['candidate_name']}.
    The question should be able to answer by candidate in words.
    
    CRITICAL REQUIREMENTS:
    - id: MUST be exactly {state['target_id']}
    - competency: {state['competency']}
    - topic: Base on {state['competency']}
    - content: The question text.
    - difficulty: easy or medium.
    
    
    RESTRICTION:
    - Do NOT generate 'reference_answer', 'candidate_response', 'score', and 'feedback'. 
    - Leave them null.
    """
    
    problem = await generator_llm.ainvoke(question_prompt)
    
    problem.id = state['target_id']
    
    return {"problem_set": [problem]}


def next_phase_node(state: InterviewState):
    current_count = len(state["problem_set"])
    total_limit = current_count*2
    print(f"   📊 Questions Ready: {current_count}")
    print(f"   🎯 Total Goal: {total_limit}")
    return {"max_index": total_limit}