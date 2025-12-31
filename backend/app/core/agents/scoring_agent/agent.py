from __future__ import annotations

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.base import BaseCheckpointSaver

from app.core.state import ScoringState  # <-- use ScoringState, NOT BackGroundState

from app.core.agents.scoring_agent.node import (
    pick_target_node,
    has_target_router,
    accuracy_score_node,
    communication_score_node,
    completeness_score_node,
    summarize_and_save_node,
)

from app.core.agents.hard_question_agent.agent import build_hard_question_graph


def build_scoring_graph(checkpointer: BaseCheckpointSaver = None, *, with_hard: bool = True):
    workflow = StateGraph(ScoringState)

    # Nodes
    workflow.add_node("pick_target_node", pick_target_node)
    workflow.add_node("accuracy_score_node", accuracy_score_node)
    workflow.add_node("communication_score_node", communication_score_node)
    workflow.add_node("completeness_score_node", completeness_score_node)
    workflow.add_node("summarize_and_save_node", summarize_and_save_node)

    # Optional subgraph
    if with_hard:
        hard_graph = build_hard_question_graph()
        workflow.add_node("hard_question_graph", hard_graph)

    # Entry
    workflow.add_edge(START, "pick_target_node")

    # If no target => END, else continue
    workflow.add_conditional_edges(
        "pick_target_node",
        has_target_router,
        {
            "accuracy_score_node": "accuracy_score_node",
            "__end__": END,
        },
    )

    # Sequential scoring (recommended)
    workflow.add_edge("accuracy_score_node", "communication_score_node")
    workflow.add_edge("communication_score_node", "completeness_score_node")
    workflow.add_edge("completeness_score_node", "summarize_and_save_node")

    # After save: optionally generate hard question, then END
    if with_hard:
        workflow.add_edge("summarize_and_save_node", "hard_question_graph")
        workflow.add_edge("hard_question_graph", END)
    else:
        workflow.add_edge("summarize_and_save_node", END)

    return workflow.compile(checkpointer=checkpointer)
