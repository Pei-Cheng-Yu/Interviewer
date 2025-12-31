from app.core.state import InterviewState, BackGroundState
from langchain_core.messages import AIMessage
from app.core.store import InterviewStore
from langchain_core.messages import AIMessage
from app.db.session import AsyncSessionLocal
from app.db.repositories.interview_repo import InterviewRepo



# 1) create session if needed
async def ensure_session_node(state: InterviewState, config):
    user_id = config["configurable"]["user_id"]  # for now you can hardcode in test
    session_id = state.get("session_id")

    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        if not session_id:
            session_id = await repo.create_session(user_id)
            await db.commit()

    return {"session_id": session_id}



def interviewer_route(state: InterviewState):
    msgs = state.get("messages", [])
    if not msgs:
        return "speak_node"
    if msgs[-1].type == "human":
        return "save_response_node"
    return "speak_node"

def route_start(state: InterviewState):
    # 0) ensure session exists
    if not state.get("session_id"):
        return "ensure_session_node"

    messages = state.get("messages", [])
    status = state.get("interview_state", "ongoing")

    # 1) Waiting -> refresh ready index from DB, then decide next stage
    if status == "waiting":
        return "get_back_ground_node"

    # 2) No messages? Start interview -> speak
    if not messages:
        return "speak_node"

    last_msg = messages[-1]

    # 3) user spoke -> save response
    if last_msg.type == "human":
        return "save_response_node"

    # 4) AI spoke -> decide if next question ready / wait / end
    if last_msg.type == "ai":
        return "next_stage"

    return "speak_node"

# 2) speak: fetch next unanswered question and speak it
async def speak_node(state: InterviewState, config):
    session_id = state["session_id"]

    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        row = await repo.next_unanswered(session_id)
        await db.commit()

    if not row:
        return {
            "messages": [AIMessage(content="No more questions right now.")],
            "interview_state": "phase_end",
        }

    # We store order_index in state so save_response knows which Q this answer belongs to
    return {
        "messages": [AIMessage(content=row.question_content)],
        "current_index": row.order_index,
        "interview_state": "ongoing",
    }
    
# 3) save response: write human answer to the row (session_id, current_index)
async def save_response_node(state: InterviewState, config):
    session_id = state["session_id"]
    idx = state["current_index"]
    messages = state.get("messages", [])
    if not messages or messages[-1].type != "human":
        raise ValueError("save_response_node triggered without a human message.")

    answer_text = messages[-1].content

    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        await repo.save_user_answer(session_id=session_id, order_index=idx, answer_text=answer_text)
        await db.commit()

    return {}



def finish_speak_node(state: InterviewState):
    return {"messages": [AIMessage(content="Thank you, Current interview stage is finished. We gonna move on Work simulation phase.")],
            "interview_state": "phase_end"
            }

def waiting_question_node(state: InterviewState):
    return {
        "messages": [AIMessage(content="Let me take some note and I'll give a follow-up question for you")],
        "interview_state": "waiting"
        }
    
async def get_back_ground_node(state: InterviewState, config):
    session_id = state["session_id"]

    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        # max existing question index in DB
        ready_idx = await repo.get_max_order_index(session_id)
        # no commit needed for read

    return {"ready_question_index": ready_idx}
    

def next_stage(state: InterviewState):
    idx = state.get("current_index", 0)
    ready_idx = state.get("ready_question_index", -1)
    max_idx = state.get("max_index", 6)

    # If DB already has a question at/after idx, speak (speak_node will fetch next unanswered anyway)
    if ready_idx >= idx:
        return "speak_node"

    # If not ready but still within limits -> waiting message
    if idx < max_idx:
        return "waiting_question_node"

    return "finish_speak_node"
