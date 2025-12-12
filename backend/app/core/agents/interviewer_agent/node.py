from app.core.state import InterviewState, BackGroundState
from langchain_core.messages import AIMessage
from app.core.store import InterviewStore

def route_start(state: InterviewState):
    
    messages = state.get("messages", [])
    status = state.get("interview_state", "ongoing")
    # We were waiting. Is the question ready now?
    if status == "waiting":
        current = state.get("current_index", 0)
        ready = state.get("ready_question_index", 0)
        
        if ready >= current:
            return "speak_node"  # Resume!
        else:
            return "__end__"     # Still not ready, go back to sleep.
        
    # 1. No messages? Start Interview.
    if not messages:
        return "speak_node"
    
    last_msg = messages[-1]
    
    # 2. User just spoke? -> Save Response
    if last_msg.type == "human":
        return "save_response_node"
        
    # 3. AI just spoke? (e.g. Filler Message or Resume) -> Check Readiness
    # Do NOT go to save_response_node!
    # We go to the router to decide: "Is the new question ready now?"
    if last_msg.type == "ai":
        return "next_stage" # <--- THIS IS THE FIX
        
    return "speak_node"

def speak_node(state: InterviewState):
    print("--- 🗣️ Interviewer Speaking ---")
    
    idx = state["current_index"]
    problem_set = state["problem_set"]
    
    question = problem_set[idx]
    text = question.content
    return {"messages": [AIMessage(content = text)],  "interview_state": "ongoing"}

def save_response_node(state: InterviewState):
    print("--- 💾 Saving User Response ---")
    
    idx = state["current_index"]
    problem_set = state["problem_set"]
    
    messages = state.get("messages", [])
    
    
    user_text = messages[-1].content
    current_problem = problem_set[idx]
    
    if messages[-1].type == "human":
        updated_problem = current_problem.model_copy(update={
        "candidate_response": user_text
        })
    else:
        raise ValueError(f"CRITICAL ERROR: 'save_response_node' triggered, but the last message was type: {messages[-1].type if messages else 'None'}")
    
    InterviewStore.save_problem(updated_problem)
    return {"problem_set" : [updated_problem], "current_index": idx+1}


def finish_speak_node(state: InterviewState):
    return {"messages": [AIMessage(content="Thank you, Current interview stage is finished. We gonna move on Work simulation phase.")],
            "interview_state": "phase_end"
            }

def waiting_question_node(state: InterviewState):
    return {
        "messages": [AIMessage(content="Let me take some note and I'll give a follow-up question for you")],
        "interview_state": "waiting"
        }
    
def get_back_ground_node(state: InterviewState) :
    problem_set = InterviewStore.get_all()

    if problem_set:
        question_index = len(problem_set)-1
    else:
        question_index = 0 
    print(f"get back ground problem length: {question_index}")
    return {
        "problem_set": problem_set,
        "ready_question_index": question_index
    }
    

def next_stage(state: InterviewState):
    print("--- Processing next stage ---")
    
    idx = state["current_index"]
    ready_idx = state.get("ready_question_index", 0)
    
    if idx <= ready_idx:
        return "speak_node"
    elif idx < state["max_index"]:
        return "waiting_question_node"
    return "finish_speak_node"