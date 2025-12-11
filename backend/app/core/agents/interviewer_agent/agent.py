from langgraph.graph import END, START, StateGraph
from app.core.state import InterviewState
from app.core.agents.interviewer_agent.node import (
    route_start,
    speak_node,
    save_response_node,
    finish_speak_node,
    next_stage
)
from app.core.agents.scoring_agent.agent import build_scoring_graph
from langgraph.checkpoint.memory import MemorySaver

def build_interviewer_graph():
    workflow = StateGraph(InterviewState)
    workflow.add_node("speak_node", speak_node)
    workflow.add_node("save_response_node", save_response_node)
    workflow.add_node("finish_speak_node", finish_speak_node)
    scoring_graph = build_scoring_graph()
    workflow.add_node("scoring_node", scoring_graph)
    workflow.add_conditional_edges(
        START,
        route_start,
        {
            "speak_node": "speak_node",
            "save_response_node": "save_response_node"
        }
    )
    
    workflow.add_conditional_edges(
        "save_response_node",
        next_stage,
        {
            "speak_node": "speak_node",
            "finish_speak_node": "finish_speak_node"
        }
    )
    
    workflow.add_edge("save_response_node","scoring_node")
    workflow.add_edge("speak_node", END)
    workflow.add_edge("finish_speak_node", END)
    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)