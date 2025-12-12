# app/core/store.py
from typing import Dict
from app.core.schema import Problem, Grade

class InterviewStore:
    _data: Dict[int, Problem] = {}
    
    @classmethod
    def save_problem(cls, problem: Problem):
        # Acts like an "UPSERT"
        if problem.id in cls._data:
            existing = cls._data[problem.id]
            # Merge logic (similar to reduce_problems)
            update_dict = problem.model_dump(exclude_unset=True, exclude_none=True)
            cls._data[problem.id] = existing.model_copy(update=update_dict)
        else:
            cls._data[problem.id] = problem
            
    @classmethod
    def get_problem(cls, p_id: int) -> Problem:
        return cls._data.get(p_id)

    @classmethod
    def get_all(cls) -> list[Problem]:
        return sorted(cls._data.values(), key=lambda p: p.id)