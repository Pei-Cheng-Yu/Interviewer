import asyncio
from app.core.agents.onboarding_agent.agent import build_onboarding_graph
from app.core.agents.knowledge_agent.agent import build_knowledge_graph
from langgraph.graph import END, START, StateGraph
from app.core.state import InterviewState
async def main():
    # 1. Mock Input
    initial_state = {
        "raw_resume": "I am Pei-Cheng. I know Python and React, have wrote some backend api for my shool's lab.",
        "raw_jd": "Looking for a Full Stack Engineer.",
        "problem_set": [], # Start empty
        "current_index": 0
    }

    # 2. Build & Run
    onboarding_graph = build_onboarding_graph()
    knowledge_graph = build_knowledge_graph()
    print("--- 🏃 Running Onboarding Graph ---")
    app =  StateGraph(InterviewState) 
    app.add_node("onboarding_graph",onboarding_graph)
    app.add_node("knowledge_graph",knowledge_graph)
    
    app.add_edge(START, "onboarding_graph")
    app.add_edge("onboarding_graph", "knowledge_graph")
    app.add_edge("knowledge_graph", END)
    
    app = app.compile()
    result = await app.ainvoke(initial_state)
    # 3. Verify Results
    print(f"\n✅ Candidate: {result['candidate'].name}")
    print(f"✅ Generated {len(result['problem_set'])} Questions:")
    for q in result['problem_set']:
        print(f"   [ID {q.id}] {q.competency}: {q.content}")
        print(f"   [topic {q.topic}] {q.difficulty}")
        print(f"    reference_answer: {q.reference_answer}")
        print(f"     candidate_response: {q.candidate_response}")
        print(f"     score: {q.score}")
        print(f"     feedback: {q.feedback}")
if __name__ == "__main__":
    asyncio.run(main())