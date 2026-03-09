"""FastAPI application for March Madness Survivor 10M Bracket Challenge.

Entry point: uvicorn api.main:app --reload --port 8000
"""

import sys
import os

# Add project root and src to path
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, "src"))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from api.routes import brackets, stats, results, events


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()
    yield


app = FastAPI(
    title="March Madness Survivor",
    description="10 Million Bracket Challenge API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register route modules
app.include_router(brackets.router)
app.include_router(stats.router)
app.include_router(results.router)
app.include_router(events.router)


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "march-madness-survivor"}
