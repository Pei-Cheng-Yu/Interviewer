from __future__ import annotations

from app.core.agents.scoring_agent.node import (
    accuracy_score_node,
    communication_score_node,
    completeness_score_node,
    has_target_router,
    maybe_complete_session_node,
    pick_target_node,
    summarize_and_save_node,
)
from app.core.state import ScoringState  # <-- use ScoringState, NOT BackGroundState
from langgraph.graph import END, START, StateGraph


def build_scoring_graph(checkpointer=None):
    workflow = StateGraph(ScoringState)

    workflow.add_node("pick_target_node", pick_target_node)
    workflow.add_node("accuracy_score_node", accuracy_score_node)
    workflow.add_node("communication_score_node", communication_score_node)
    workflow.add_node("completeness_score_node", completeness_score_node)
    workflow.add_node("summarize_and_save_node", summarize_and_save_node)
    workflow.add_node("maybe_complete_session_node", maybe_complete_session_node)

    workflow.add_edge(START, "pick_target_node")
    workflow.add_conditional_edges(
        "pick_target_node",
        has_target_router,
        {"accuracy_score_node": "accuracy_score_node", "__end__": END},
    )
    workflow.add_edge("accuracy_score_node", "communication_score_node")
    workflow.add_edge("communication_score_node", "completeness_score_node")
    workflow.add_edge("completeness_score_node", "summarize_and_save_node")
    workflow.add_edge("summarize_and_save_node", "maybe_complete_session_node")
    workflow.add_edge("maybe_complete_session_node", END)

    return workflow.compile(checkpointer=checkpointer)
