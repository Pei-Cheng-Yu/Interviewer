from app.core.agents.onboarding_agent.node import (
    extractor_node,
    generate_questions_node,
    initiate_generate_questions,
    next_phase_node,
)
from app.core.state import InterviewState
from langgraph.graph import END, START, StateGraph


def build_onboarding_graph():
    """
    1) extractor_node (sequential)
    2) generate_questions_node (parallel fan-out via Send)
    3) join_node (collect)
    4) next_phase_node (run ONCE)
    """
    workflow = StateGraph(InterviewState)

    workflow.add_node("extractor_node", extractor_node)
    workflow.add_node("generate_questions_node", generate_questions_node)
    workflow.add_node("join_node", lambda state: {})  # <-- runs once after fan-out
    workflow.add_node("next_phase_node", next_phase_node)

    workflow.add_edge(START, "extractor_node")

    # Fan-out: extractor_node -> many generate_questions_node
    workflow.add_conditional_edges(
        "extractor_node",
        initiate_generate_questions,
        ["generate_questions_node"],
    )

    # Join: all parallel tasks flow into join_node
    workflow.add_edge("generate_questions_node", "join_node")

    # After join -> run next_phase once -> END
    workflow.add_edge("join_node", "next_phase_node")
    workflow.add_edge("next_phase_node", END)

    return workflow.compile()
