import asyncio
from app.core.agents.onboarding_agent.agent import build_onboarding_graph
from app.core.agents.knowledge_agent.agent import build_knowledge_graph
from app.core.agents.interviewer_agent.agent import build_interviewer_graph


from langchain_core.messages import HumanMessage
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.core.state import InterviewState
from app.core.llm import get_llm

async def generate_candidate_response(question_text: str, persona: str):
    """Generates a fake candidate answer using LLM."""
    llm = get_llm()
    prompt = f"""
    You are a job candidate in an interview.
    PERSONA: {persona}
    QUESTION: "{question_text}"
    
    Give a concise, spoken-style answer (1-2 sentences).
    """
    res = await llm.ainvoke(prompt)
    return res.content


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
    
    prep_app = app.compile()
    prepared_state = await prep_app.ainvoke(initial_state)
    
    # 3. Verify Results
    print(f"\n✅ Candidate: {prepared_state['candidate'].name}")
    print(f"✅ Generated {len(prepared_state['problem_set'])} Questions:")
    for q in prepared_state['problem_set']:
        print(f"   [ID {q.id}] {q.competency}: {q.content}")
        print(f"   [topic {q.topic}] {q.difficulty}")
        print(f"    reference_answer: {q.reference_answer}")
        print(f"     candidate_response: {q.candidate_response}")
        print(f"     score: {q.grade}")
 
        
    print(f"✅ Setup Complete. Generated {len(prepared_state['problem_set'])} questions.")
    
    
    # ==========================================
    # 🔵 PHASE 2: INTERVIEW SIMULATION (The Loop)
    # ==========================================
    print("\n--- 🔵 PHASE 2: INTERVIEW LOOP (Simulated) ---")
    
    # 1. Build Interview Graph with Memory
    # We need memory because this graph stops and resumes!
    
    interview_app = build_interviewer_graph()
    
    # 2. Inject State
    # We take the 'prepared_state' from Phase 1 and load it into Phase 2
    thread_config = {"configurable": {"thread_id": "test_session_1"}}
    interview_app.update_state(thread_config, prepared_state)
    
    # 3. Start the Interview (First Pitch)
    # We invoke with None to trigger the 'route_start' logic
    print("   ... Starting Interviewer Agent ...")
    step_result = await interview_app.ainvoke(None, config=thread_config)
    
    ai_message = step_result["messages"][-1].content
    print(f"\n🤖 AI: {ai_message}")

    # 4. The Loop
    while True:
        # Check if interview ended
        if "thank you" in ai_message.lower() or "finished" in ai_message.lower():
            print("\n🏁 Interview Finished.")
            break
            
        # A. Simulate Candidate Thinking
        candidate_reply = await generate_candidate_response(
            ai_message, 
            persona="A confident Junior Developer"
        )
        print(f"👤 Candidate: {candidate_reply}")
        
        # B. Send Answer to Graph
        # This triggers: Save -> Score -> Next -> Speak
        step_result = await interview_app.ainvoke(
            {"messages": [HumanMessage(content=candidate_reply)]},
            config=thread_config
        )
        
        
        
        # (Optional Debug: Show Score)
        # Access the state to see the score of the question just answered
        current_idx = step_result["current_index"] 
        # previous question is at index - 1 (because speak node looks at current, but logic incremented it)
        # Note: Depending on your exact logic implementation, you might need to adjust this index lookup
        scored_q = step_result["problem_set"][current_idx - 1]
        print(f"   (DEBUG: Score for Q{scored_q.id}: {scored_q.grade})")
        print(f"   (DEBUG: Response for Q{scored_q.id}: {scored_q.candidate_response})")
        print(f"   (DEBUG: Ref for Q{scored_q.id}: {scored_q.reference_answer})")
        
        
        # C. Get AI Response
        ai_message = step_result["messages"][-1].content
        print(f"🤖 AI: {ai_message}")
        
    for m in prepared_state["messages"]: 
        m.pretty_print()
if __name__ == "__main__":
    asyncio.run(main())