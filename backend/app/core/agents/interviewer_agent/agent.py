# backend/app/core/agents/interviewer_agent/graph.py

from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.core.state import InterviewState
from app.core.agents.interviewer_agent.node import (
    route_start,
    ensure_session_node,
    speak_node,
    save_response_node,
    finish_speak_node,
    next_stage,
    waiting_question_node,
    get_back_ground_node,
)


def build_interviewer_graph(checkpointer: BaseCheckpointSaver = None):
    workflow = StateGraph(InterviewState)

    # Nodes
    workflow.add_node("ensure_session_node", ensure_session_node)
    workflow.add_node("get_back_ground_node", get_back_ground_node)
    workflow.add_node("speak_node", speak_node)
    workflow.add_node("save_response_node", save_response_node)
    workflow.add_node("waiting_question_node", waiting_question_node)
    workflow.add_node("finish_speak_node", finish_speak_node)

    # START -> route_start (via conditional entry on get_back_ground_node is optional)
    # We will:
    # 1) Ensure session if needed
    # 2) Refresh ready_question_index when needed
    # 3) Speak once, END

    # Entry routing
    workflow.add_conditional_edges(
        START,
        route_start,
        {
            "ensure_session_node": "ensure_session_node",
            "get_back_ground_node": "get_back_ground_node",
            "speak_node": "speak_node",
            "save_response_node": "save_response_node",
            "next_stage": "get_back_ground_node",  # if route_start returns next_stage, we refresh then decide
            "__end__": END,
        },
    )

    # After ensure session -> (refresh DB ready index) -> decide next
    workflow.add_edge("ensure_session_node", "get_back_ground_node")

    # After get_back_ground_node -> decide what to do next (speak/wait/finish)
    workflow.add_conditional_edges(
        "get_back_ground_node",
        next_stage,
        {
            "speak_node": "speak_node",
            "waiting_question_node": "waiting_question_node",
            "finish_speak_node": "finish_speak_node",
        },
    )

    # After speak -> END (wait for next user message)
    workflow.add_edge("speak_node", END)

    # After waiting/finish -> END
    workflow.add_edge("waiting_question_node", END)
    workflow.add_edge("finish_speak_node", END)

    # After save response -> refresh readiness -> decide next
    workflow.add_edge("save_response_node", "get_back_ground_node")

    return workflow.compile(checkpointer=checkpointer)
