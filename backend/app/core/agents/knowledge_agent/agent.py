from langgraph.graph import END, START, StateGraph
from app.core.state import InterviewState
from app.core.agents.knowledge_agent.node import (
    initiate_expert_query, 
    expert_query_node
)

def build_knowledge_graph():
    """
    Constructs the Onboarding Sub-Graph:
    1. Extract Candidate (Sequential)
    2. Generate Questions (Parallel 'Send')
    """
    
    workflow = StateGraph(InterviewState)
    
    workflow.add_node("expert_query_node", expert_query_node)
    
    workflow.add_conditional_edges(
        START, 
        initiate_expert_query,
        ["expert_query_node"]
    )
    workflow.add_edge("expert_query_node", END)
    
    return workflow.compile()