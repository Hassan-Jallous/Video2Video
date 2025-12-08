"""Minimal FastAPI server for frontend testing"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uuid

app = FastAPI(title="Video2Video API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for testing
sessions = {}


class SessionCreate(BaseModel):
    tiktok_url: str
    product_name: str
    num_variants: int = 1
    provider: str = "kie.ai"
    model: str = "veo-3.1-fast"
    strategy: str = "segments"


@app.get("/")
def root():
    return {"message": "Video2Video API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/api/v1/library")
def get_library():
    return {"videos": []}


@app.post("/api/v1/sessions")
def create_session(data: SessionCreate):
    session_id = str(uuid.uuid4())[:8]
    sessions[session_id] = {
        "session_id": session_id,
        "product_name": data.product_name,
        "tiktok_url": data.tiktok_url,
        "status": "pending",
        "provider": data.provider,
        "model": data.model,
        "variants": [],
        "total_cost": 0.0,
    }
    return sessions[session_id]


@app.get("/api/v1/sessions/{session_id}")
def get_session(session_id: str):
    if session_id in sessions:
        return sessions[session_id]
    # Return mock data for testing
    return {
        "session_id": session_id,
        "product_name": "Test Product",
        "tiktok_url": "https://tiktok.com/test",
        "status": "generating",
        "provider": "kie.ai",
        "model": "veo-3.1-fast",
        "variants": [],
        "total_cost": 0.0,
    }


@app.get("/api/v1/sessions/{session_id}/status")
def get_session_status(session_id: str):
    return {
        "session_id": session_id,
        "status": "generating",
        "progress": 45.0,
        "current_step": "Analyzing video scenes...",
        "variants_completed": 1,
        "variants_total": 3,
    }


@app.post("/api/v1/sessions/{session_id}/generate")
def start_generation(session_id: str):
    if session_id in sessions:
        sessions[session_id]["status"] = "generating"
    return {"message": "Generation started", "session_id": session_id}


@app.post("/api/v1/sessions/{session_id}/image")
def upload_image(session_id: str):
    return {"message": "Image uploaded"}
