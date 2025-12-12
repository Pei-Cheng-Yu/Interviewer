import asyncio
from app.core.agents.onboarding_agent.agent import build_onboarding_graph
from app.core.agents.knowledge_agent.agent import build_knowledge_graph
from app.core.agents.interviewer_agent.agent import build_interviewer_graph
from app.core.agents.scoring_agent.agent import build_scoring_graph

from langchain_core.messages import HumanMessage
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from app.core.state import InterviewState
from app.core.llm import get_llm
from langgraph.checkpoint.memory import MemorySaver
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
        "raw_jd": "Looking for a Backend Engineer.",
        "problem_set": [], # Start empty
        "current_index": 0
    }
    shared_memory = MemorySaver()
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
   
    interview_app = build_interviewer_graph(checkpointer=shared_memory)
    
    # 2. Inject State
    # We take the 'prepared_state' from Phase 1 and load it into Phase 2
    thread_config = {"configurable": {"thread_id": "test_session_1"}}
    sidecar_config = {"configurable": {"thread_id": "test_1_background"}}
    interview_app.update_state(thread_config, prepared_state)
    scoring_app = build_scoring_graph(shared_memory)
    # 3. Start the Interview (First Pitch)
    # We invoke with None to trigger the 'route_start' logic
    print("   ... Starting Interviewer Agent ...")
    step_result = await interview_app.ainvoke(None, config=thread_config)
    background_tasks = []
    ai_message = step_result["messages"][-1].content
    print(f"\n🤖 AI: {ai_message}")

    # 4. The Loop
    while True:
        
        # Check if interview ended based on previous AI message
        
            
        # ============================================
        # A. CANDIDATE SPEAKS
        # ============================================
        candidate_reply = await generate_candidate_response(
            ai_message, 
            persona="A Junior Developer who is nervous but knows Python basics"
        )
        print(f"\n👤 Candidate: {candidate_reply}")
        
        # ============================================
        # B. INTERVIEWER (Foreground)
        # ============================================
        step_result = await interview_app.ainvoke(
            {"messages": [HumanMessage(content=candidate_reply)]},
            config=thread_config
        )
        
        # Check the status immediately after the Interviewer runs
        final_state = await interview_app.aget_state(thread_config)
        status = final_state.values.get("interview_state", "ongoing")
        
        ai_message = step_result["messages"][-1].content
        
        # ============================================
        # C. TRIGGER BACKGROUND WORKER
        # ============================================
        # We ALWAYS trigger the scorer after the user speaks. 
        # It decides internally whether to Grade, Generate, or Research.
        print("   [Background] ⏳ Triggering Scorer...")
        scoring_app.update_state(thread_config, final_state)
        # We invoke with None. The 'index_checker' at START will find the work.
        task = asyncio.create_task(scoring_app.ainvoke({}, config=sidecar_config))
        background_tasks.append(task)
        
        # --- D. VERIFY SCORING ---
        # Let's peek into the state to ensure it actually worked
        current_state = await interview_app.aget_state(thread_config)
        status = current_state.values.get("interview_state", "ongoing")
        latest_q_idx = current_state.values["current_index"] - 1
        latest_q = current_state.values["problem_set"][latest_q_idx]
        
        if latest_q.grade:
            print(f"   [Background] ✅ Scored Q{latest_q.id}: {latest_q.grade.accuracy_score}/10")
            print(f" ===================================== ")
            print(f" =============== Score =============== ")
            print(f"   Score for Q{latest_q.id}: ")
            print(f"        accuracy_score: {latest_q.grade.accuracy_score}")
            print(f"        communication_score: {latest_q.grade.communication_score}")
            print(f"        completeness_score: {latest_q.grade.completeness_score}")
            print(f"        Final_score: {latest_q.grade.final_score}")
            print(f"   FeedBack for Q{latest_q.id}: {latest_q.grade.feedback}")
            print(f" {latest_q.grade.feedback} ")
            print(f" ===================================== ")
            
            print(f"   Response for Q{latest_q.id}: {latest_q.candidate_response})")
            print(f"   Ref for Q{latest_q.id}: {latest_q.reference_answer})")
            
            print(f" ============================================= ")
            print(f" =============== Next Question =============== ")
            print(f" ============================================= ")
        else:
            print(f"   [Background] ❌ Warning: Q{latest_q.id} Scoring didn't finish.")
            
        # ============================================
        # D. HANDLE "WAITING" STATE (The Polling Logic)
        # ============================================
        if status == "waiting":
            # 1. Show the Filler Message
            print(f"🤖 AI (Filler): {ai_message}")
            print("   [System] Buffer empty. Polling for new question...")
            
            # 2. Poll Loop
            while True:
                poll_state = await interview_app.aget_state(thread_config)
                generated_state = await scoring_app.aget_state(sidecar_config)
                curr = poll_state.values.get("current_index", 0)
                ready = len(generated_state.values["problem_set"]) - 1
                
                if ready >= curr:
                    print(f"   [System] Ready! (Index {ready} >= {curr})")
                    break
                
                # Visual feedback that we are waiting
                print(".", end="", flush=True)
                await asyncio.sleep(1)
            
            # 3. Resume the Interviewer to get the REAL question
            print("\n   [System] Resuming Conversation...")
            step_result = await interview_app.ainvoke(None, config=thread_config)
            
            # Update ai_message to the REAL question
            ai_message = step_result["messages"][-1].content
            
        # ============================================
        # E. PRINT ACTUAL AI RESPONSE
        # ============================================
        print(f"🤖 AI: {ai_message}")
        
        # ============================================
        # F. DEBUG: SHOW SCORE (Optional)
        # ============================================
        # Check the score of the question just answered (index - 1)
        current_idx = final_state.values["current_index"]
        prev_idx = current_idx - 1
        
        # Safety check: ensure we don't access negative index
        if prev_idx >= 0 and prev_idx < len(final_state.values["problem_set"]):
            latest_q = final_state.values["problem_set"][prev_idx]
            if latest_q.grade:
                 print(f"   [🔍 Debug] Q{latest_q.id} Score: {latest_q.grade.accuracy_score}/10")
                 
                 
        if status == "phase_end":
            print("\n🏁 Interview Finished.")
            break
    await asyncio.gather(*background_tasks)
    # ============================================
    # FINAL TRANSCRIPT
    # ============================================
    print("\n\n📜 FINAL TRANSCRIPT 📜")
    final_state = await interview_app.aget_state(thread_config)
    for m in final_state.values["messages"]: 
        m.pretty_print()
if __name__ == "__main__":
    asyncio.run(main())