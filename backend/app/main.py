import os

import uvicorn
from app.auth import routes as auth
from app.routes import interviews_api
from app.routes.interviews_api import MEDIA_ROOT
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# --- CORS Configuration ---
# Allow requests from the frontend (React/Vite)
allowed_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Register Routers ---

app.include_router(auth.router, prefix="/api/auth")
app.include_router(interviews_api.router)
app.mount("/media", StaticFiles(directory=str(MEDIA_ROOT)), name="media")


@app.get("/")
def health_check():
    return {"status": "ok", "message": "Interviewer is running"}


if __name__ == "__main__":
    # Run with: python main.py
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
