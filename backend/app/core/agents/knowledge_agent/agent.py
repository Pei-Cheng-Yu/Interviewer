# backend/app/core/agents/knowledge_agent/graph.py

from app.core.agents.knowledge_agent.node import (
    expert_query_node,
    initiate_expert_query,
)
from app.core.state import InterviewState
from langgraph.graph import END, START, StateGraph


def build_knowledge_graph():
    workflow = StateGraph(InterviewState)
    workflow.add_node("expert_query_node", expert_query_node)

    # START routes to many Send("expert_query_node", {...})
    workflow.add_conditional_edges(
        START,
        initiate_expert_query,
        ["expert_query_node"],  # allowed targets
    )

    workflow.add_edge("expert_query_node", END)
    return workflow.compile()
