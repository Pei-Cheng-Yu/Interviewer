from __future__ import annotations

from app.core.schema import Problem, ReferenceAnswer


def _row_to_problem(row) -> Problem:
    """
    Convert an InterviewInteraction row -> Problem (for scoring prompts).
    Your DB doesn't store difficulty/topic/competency, so we fill defaults.
    """
    ref = None
    if row.reference_data:
        try:
            ref = ReferenceAnswer.model_validate(row.reference_data)  # Pydantic v2
        except Exception:
            ref = None

    return Problem(
        id=int(row.order_index),
        difficulty="medium",
        topic="interview",
        competency="general",
        content=row.question_content,
        reference_answer=ref,
        candidate_response=row.user_answer_text,
        grade=None,
    )
