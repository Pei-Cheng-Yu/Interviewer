from app.core.agents.hard_question_agent.node import (
    expert_query_node,
    generate_hard_node,
    index_checker,
)
from app.core.state import BackGroundState
from langgraph.graph import END, StateGraph


def build_hard_question_graph():
    workflow = StateGraph(BackGroundState)  # ensure this schema includes session_id
    workflow.add_node("generate_hard_node", generate_hard_node)
    workflow.add_node("expert_query_node", expert_query_node)

    workflow.set_conditional_entry_point(
        index_checker,
        {
            "generate_hard_node": "generate_hard_node",
            "__end__": END,
        },
    )
    workflow.add_edge("generate_hard_node", "expert_query_node")
    workflow.add_edge("expert_query_node", END)
    return workflow.compile()
