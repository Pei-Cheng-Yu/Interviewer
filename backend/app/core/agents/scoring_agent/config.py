# backend/app/core/agents/scoring/config.py

SCORING_CRITERIA = {
    "accuracy": {
        "name": "Technical Accuracy",
        "definition": "Are the technical facts correct? Does the logic work? Compare strictly against the Reference Answer. Penalize hallucinations or wrong terminology."
    },
    "communication": {
        "name": "Communication Clarity",
        "definition": "Is the answer structured, concise, and easy to follow? Penalize rambling, confusion, or lack of directness. Do NOT judge technical facts."
    },
    "completeness": {
        "name": "Depth & Completeness",
        "definition": "Did they mention the 'Key Keywords'? Did they explain the 'Why' and 'How'? Did they cover edge cases? Compare against the required keywords list."
    }
}