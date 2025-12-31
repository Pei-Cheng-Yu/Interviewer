from app.core.state import InterviewState
from app.db.repositories.interview_repo import InterviewRepo
from app.db.session import AsyncSessionLocal
from langchain_core.messages import AIMessage


# 1) create session if needed
async def ensure_session_node(state: InterviewState, config):
    user_id = config["configurable"]["user_id"]
    session_id = state.get("session_id")

    if session_id:
        return {}

    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        session_id = await repo.create_session(user_id)
        await db.commit()

    return {"session_id": session_id}


def route_start(state: InterviewState):
    # ensure session
    if not state.get("session_id"):
        return "ensure_session_node"

    msgs = state.get("messages", [])
    if msgs and msgs[-1].type == "human":
        return "save_response_node"

    return "speak_node"


# 2) speak: fetch next unanswered question and speak it
async def speak_node(state: InterviewState, config):
    session_id = state["session_id"]

    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        row = await repo.next_unanswered(session_id)

    if not row:
        return {
            "messages": [AIMessage(content="Generating next question...")],
            "interview_state": "waiting",
        }

    return {
        "messages": [AIMessage(content=row.question_content)],
        "current_index": row.order_index,
        "interview_state": "ongoing",
    }


# 3) save response: write human answer to the row we last asked
async def save_response_node(state: InterviewState, config):
    session_id = state["session_id"]
    idx = state.get("current_index")

    # IMPORTANT: if idx missing, DO NOT guess by next_unanswered
    # (guessing can save answer into the wrong question and make questions “disappear”)
    if idx is None:
        raise ValueError(
            "Missing current_index. Pass it from API or keep checkpointer state."
        )

    messages = state.get("messages", [])
    if not messages or messages[-1].type != "human":
        raise ValueError("save_response_node triggered without a human message.")

    answer_text = messages[-1].content

    async with AsyncSessionLocal() as db:
        repo = InterviewRepo(db)
        await repo.save_user_answer(
            session_id=session_id, order_index=idx, answer_text=answer_text
        )
        await db.commit()

    # do NOT return a “waiting” AI message here
    # we want the graph to continue to speak_node immediately
    return {
        "interview_state": "ongoing",
    }
