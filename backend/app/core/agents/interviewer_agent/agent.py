from langgraph.graph import END, START, StateGraph
from app.core.state import InterviewState
from app.core.agents.interviewer_agent.node import (
    route_start,
    speak_node,
    save_response_node,
    finish_speak_node,
    next_stage,
    waiting_question_node,
    get_back_ground_node
)

from langgraph.checkpoint.base import BaseCheckpointSaver

def build_interviewer_graph(checkpointer: BaseCheckpointSaver = None):
    workflow = StateGraph(InterviewState)
    workflow.add_node("speak_node", speak_node)
    workflow.add_node("save_response_node", save_response_node)
    workflow.add_node("finish_speak_node", finish_speak_node)
    workflow.add_node("waiting_question_node", waiting_question_node)
    workflow.add_node("start_get_back_ground_node", get_back_ground_node)
    workflow.add_node("get_back_ground_node", get_back_ground_node)
  
    workflow.add_edge(START, "start_get_back_ground_node")
    workflow.add_conditional_edges(
        "start_get_back_ground_node",
        route_start,
        {
            "speak_node": "speak_node",
            "save_response_node": "save_response_node",
            "__end__": END
        }
    )
    workflow.add_edge("save_response_node", "get_back_ground_node")
   
    
    workflow.add_conditional_edges(
        "save_response_node",
        next_stage,
        {
            "speak_node": "speak_node",
            "finish_speak_node": "finish_speak_node",
            "waiting_question_node": "waiting_question_node"
        }
    )
    
    workflow.add_edge("speak_node", END)
    workflow.add_edge("finish_speak_node", END)
    workflow.add_edge("waiting_question_node", END)
    
    return workflow.compile(checkpointer=checkpointer)