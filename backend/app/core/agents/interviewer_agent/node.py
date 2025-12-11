from app.core.state import InterviewState
from langchain_core.messages import AIMessage


def route_start(state: InterviewState):
    
    messages = state.get("messages", [])
    
    if not messages or messages[-1].type != "human":
        return "speak_node"
    else:
        return "save_response_node"

def speak_node(state: InterviewState):
    print("--- 🗣️ Interviewer Speaking ---")
    
    idx = state["current_index"]
    problem_set = state["problem_set"]
    
    question = problem_set[idx]
    text = question.content
    return {"messages": [AIMessage(content = text)]}

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
    
    
    return {"problem_set" : [updated_problem], "current_index": idx+1}


def finish_speak_node(state: InterviewState):
    return {"messages": [AIMessage(content="Thank you, Current interview stage is finished. We gonna move on Work simulation phase.")]}

def next_stage(state: InterviewState):
    print("--- Processing next stage ---")
    
    idx = state["current_index"]
    if idx < 3:# state["max_index"]:
        return "speak_node"
    
    return "finish_speak_node"