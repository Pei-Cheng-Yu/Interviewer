from langgraph.graph import END, START, StateGraph
from app.core.state import InterviewState, BackGroundState
from app.core.agents.scoring_agent.node import (
    index_checker,
    problem_extractor_node,
    accuracy_score_node,
    communication_score_node,
    completeness_score_node,
    summarize_node,
    get_interview_node
)
from app.core.agents.hard_question_agent.agent import build_hard_question_graph

from langgraph.checkpoint.base import BaseCheckpointSaver
def build_scoring_graph(checkpointer: BaseCheckpointSaver = None):

    workflow = StateGraph(BackGroundState, input_schema=InterviewState, output_schema=BackGroundState) 
    
    workflow.add_node("problem_extractor_node", problem_extractor_node)
    workflow.add_node("accuracy_score_node", accuracy_score_node)
    workflow.add_node("communication_score_node", communication_score_node)
    workflow.add_node("completeness_score_node", completeness_score_node)
    workflow.add_node("summarize_node", summarize_node)
    workflow.add_node("get_interview_node", get_interview_node)
    
    hard_question_graph = build_hard_question_graph()
    workflow.add_node("hard_question_graph", hard_question_graph)
    
    workflow.add_edge(START, "get_interview_node")
    workflow.add_conditional_edges(
        "get_interview_node",
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
    
    workflow.add_edge("summarize_node", "hard_question_graph")
    
    workflow.add_conditional_edges(
        "hard_question_graph",
        index_checker,
        {
            "problem_extractor_node": "problem_extractor_node",
            "__end__": END
        }
    )

    return workflow.compile(checkpointer=checkpointer)