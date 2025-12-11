from typing import List
from app.core.schema import Problem

def reduce_problems(existing: List[Problem], incoming: List[Problem]) -> List[Problem]:
    """
    Smartly merges incoming problems into the existing list.
    """
    problem_map = {p.id: p for p in existing} if existing else {}

    for new_p in incoming:
        if new_p.id in problem_map:
            existing_p = problem_map[new_p.id]
            
            # 1. Convert to dict (This unfortunately turns nested objects into dicts)
            updated_data = new_p.model_dump(exclude_unset=True)
            
            # --- 2. THE FIX: RE-INJECT OBJECTS ---
            # We explicitly overwrite the dicts with the original Pydantic Objects.
            
            if new_p.grade is not None:
                updated_data["grade"] = new_p.grade  # Keep as Grade object
                
            if new_p.reference_answer is not None:
                updated_data["reference_answer"] = new_p.reference_answer # Keep as Ref object

            # 3. Apply updates (Now safely containing Objects)
            # Use model_copy() for Pydantic V2 compatibility (copy() is deprecated)
            problem_map[new_p.id] = existing_p.model_copy(update=updated_data)
        else:
            problem_map[new_p.id] = new_p

    return sorted(problem_map.values(), key=lambda p: p.id)