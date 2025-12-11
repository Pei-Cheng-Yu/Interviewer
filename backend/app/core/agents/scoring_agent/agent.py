from langgraph.graph import END, START, StateGraph
from app.core.state import InterviewState
from app.core.agents.scoring_agent.node import (
    index_checker,
    problem_extractor_node,
    accuracy_score_node,
    communication_score_node,
    completeness_score_node,
    summarize_node
)
def build_scoring_graph():

    workflow = StateGraph(InterviewState) 
  
    workflow.add_node("problem_extractor_node", problem_extractor_node)
    workflow.add_node("accuracy_score_node", accuracy_score_node)
    workflow.add_node("communication_score_node", communication_score_node)
    workflow.add_node("completeness_score_node", completeness_score_node)
    workflow.add_node("summarize_node", summarize_node)
    workflow.add_conditional_edges(
        START,
        index_checker,
        {
            "problem_extractor_node": "problem_extractor_node",
            "__end__": END
        }
    )
    # Parallel Fan-Out
    workflow.add_edge("problem_extractor_node", "accuracy_score_node")
    workflow.add_edge("problem_extractor_node", "communication_score_node")
    workflow.add_edge("problem_extractor_node", "completeness_score_node")
    
    # Fan-In
    workflow.add_edge("accuracy_score_node", "summarize_node")
    workflow.add_edge("communication_score_node", "summarize_node")
    workflow.add_edge("completeness_score_node", "summarize_node")
    
    workflow.add_conditional_edges(
        "summarize_node",
        index_checker,
        {
            "problem_extractor_node": "problem_extractor_node",
            "__end__": END
        }
    )
    return workflow.compile()