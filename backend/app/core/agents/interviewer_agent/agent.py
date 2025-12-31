from app.core.agents.interviewer_agent.node import (
    ensure_session_node,
    route_start,
    save_response_node,
    speak_node,
)
from app.core.state import InterviewState
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph


def build_interviewer_graph(checkpointer: BaseCheckpointSaver = None):
    workflow = StateGraph(InterviewState)

    workflow.add_node("ensure_session_node", ensure_session_node)
    workflow.add_node("speak_node", speak_node)
    workflow.add_node("save_response_node", save_response_node)

    workflow.add_conditional_edges(
        START,
        route_start,
        {
            "ensure_session_node": "ensure_session_node",
            "save_response_node": "save_response_node",
            "speak_node": "speak_node",
        },
    )

    workflow.add_edge("ensure_session_node", "speak_node")
    workflow.add_edge("save_response_node", "speak_node")  # ✅ THIS is the key
    workflow.add_edge("speak_node", END)

    return workflow.compile(checkpointer=checkpointer)
