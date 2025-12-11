from langgraph.graph import END, START, StateGraph
from app.core.state import InterviewState
from app.core.agents.onboarding_agent.node import (
    extractor_node, 
    initiate_generate_questions, 
    generate_questions_node,
    next_phase_node
)

def build_onboarding_graph():
    """
    Constructs the Onboarding Sub-Graph:
    1. Extract Candidate (Sequential)
    2. Generate Questions (Parallel 'Send')
    """
    
    workflow = StateGraph(InterviewState)
    
    workflow.add_node("extractor_node", extractor_node)
    workflow.add_node("generate_questions_node", generate_questions_node)
    workflow.add_node("next_phase_node", next_phase_node)
    
    workflow.add_edge(START, "extractor_node")
    workflow.add_conditional_edges(
        "extractor_node", 
        initiate_generate_questions,
        ["generate_questions_node"]
    )
    workflow.add_edge("generate_questions_node", "next_phase_node")
    workflow.add_edge("next_phase_node", END)
    
    return workflow.compile()