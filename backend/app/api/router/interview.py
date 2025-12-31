from fastapi import APIRouter, Depends, HTTPException, Response

router = APIRouter()


@router.post("/interview/{session_id}/chat")
async def chat_text(seesion_id: str, user_input: dict, db):
    