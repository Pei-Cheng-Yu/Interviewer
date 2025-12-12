from langgraph.graph import END, START, StateGraph
from app.core.state import InterviewState, BackGroundState
from app.core.agents.hard_question_agent.node import (
    generate_hard_node,
    expert_query_node,
    index_checker
)
from langgraph.checkpoint.base import BaseCheckpointSaver

def build_hard_question_graph(checkpointer: BaseCheckpointSaver = None):
    workflow = StateGraph(BackGroundState, input_schema=InterviewState, output_schema=BackGroundState) 
    workflow.add_node("generate_hard_node", generate_hard_node)
    workflow.add_node("expert_query_node", expert_query_node)
    
    workflow.add_conditional_edges(
        START, 
        index_checker,
        {
            "generate_hard_node": "generate_hard_node",
            "__end__": END
        }
    )
    workflow.add_edge("generate_hard_node", "expert_query_node")
    workflow.add_edge("expert_query_node", END)
    
    return workflow.compile(checkpointer=checkpointer)
