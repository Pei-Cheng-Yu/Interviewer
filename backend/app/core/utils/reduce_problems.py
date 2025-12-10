from typing import List
from app.core.schema import Problem

def reduce_problems(existing: List[Problem], incoming: List[Problem]) -> List[Problem]:
    """
    Smartly merges incoming problems into the existing list.
    - If ID exists: Update the existing object with new fields.
    - If ID is new: Append it.
    """
    # 1. Create a dictionary map of existing problems for fast lookup
    # {1: Problem(id=1...), 2: Problem(id=2...)}
    problem_map = {p.id: p for p in existing} if existing else {}

    # 2. Process incoming updates
    for new_p in incoming:
        if new_p.id in problem_map:
            # --- MERGE LOGIC ---
            # We take the existing problem and update ONLY the fields that are not None in the new one
            existing_p = problem_map[new_p.id]
            
            # Update fields if the new object has data
            # (Pydantic's copy(update=...) is useful here, or manual assignment)
            updated_data = new_p.model_dump(exclude_unset=True) # Only get fields strictly set
            
            # We can use Pydantic's copy method to create a fresh merged object
            problem_map[new_p.id] = existing_p.copy(update=updated_data)
        else:
            # --- APPEND LOGIC ---
            problem_map[new_p.id] = new_p

    # 3. Return the list, sorted by ID to be safe
    return sorted(problem_map.values(), key=lambda p: p.id)