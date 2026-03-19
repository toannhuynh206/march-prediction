"""FastAPI application for March Madness Bracket Simulation Engine.

Entry point: uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from db.connection import check_connection
from api.routes import brackets, stats, results, events, portfolio


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Verify database connectivity on startup."""
    if not check_connection():
        print("WARNING: PostgreSQL connection failed. API may not work.")
    else:
        print("PostgreSQL connection verified.")
    yield


app = FastAPI(
    title="March Madness Bracket Engine",
    description="206M Bracket Simulation API",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:5176",
        "http://localhost:3000",
        "https://marchmadnesschallenge.store",
        "https://www.marchmadnesschallenge.store",
        "http://marchmadnesschallenge.store",
        "http://www.marchmadnesschallenge.store",
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
app.include_router(portfolio.router)


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "march-madness-bracket-engine"}
