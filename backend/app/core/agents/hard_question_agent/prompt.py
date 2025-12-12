
HARD_SCENARIO_PROMPT = """
You are a Principal Software Architect conducting a high-level system design interview.
The candidate successfully answered a basic question about **{topic}**.
Now, create a **Level 3 (Expert) Scenario** to test if they can apply this knowledge in a broken or constrained environment.

--- CONTEXT ---
ROLE: {topic} related
PREV QUESTOIN: {prev_question}
PREV ANSWER: "{prev_answer}"

--- INSTRUCTIONS ---
1. **Create a Specific Scenario**: Do not ask "What is X?". Instead, say "We implemented X, but now Y is happening."
2. **Inject a Constraint**: Add a real-world constraint that makes the standard textbook answer fail.
   - *Traffic:* "We are receiving 50k requests per second."
   - *Security:* "We cannot store tokens in the database."
   - *Legacy:* "We must support IE11 clients."
3. **The 'Twist'**: Force them to make a trade-off (e.g., Consistency vs. Availability, Latency vs. Accuracy).

--- EXAMPLES ---
* Basic: "How do you scale a database?"
* Scenario: "We sharded our Postgres database by UserID. Now we need to run a report joining data across all shards, but the query is timing out. How do you re-architect this analytics pipeline without impacting production write latency?"

* Basic: "What is JWT?"
* Scenario: "We are using JWTs for auth. A user's laptop was stolen. We need to revoke their access immediately, but our services are stateless and don't check a DB. How do we implement immediate revocation?"

--- OUTPUT ---
Generate ONLY the scenario question and the technical focus. Do NOT include the solution.
"""

QUERY_PROMPT = """
    You are a Tech Lead preparing an query for web-searching for a interview answer.
    Your goal is to generate a well-structured query for use in retrieval and / or web-search
    
    below is the original interview question:
    QUESTION: "{content}"
    TOPIC: {topic}
    COMPETENCY: {competency}
    
    Task:
    1. First, analyze the Question information
    2. Pay particular attention to the COMPETENCY
    3. Generate a well-structured web search query
    Return ONLY the query
    """