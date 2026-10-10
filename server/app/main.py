"""SmartBus Central Server - FastAPI application entrypoint.

Run with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.database import Base, engine
import app.models  # noqa: F401  (registers tables on Base.metadata)
from app.routers import admin, ingest, public


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Make the server self-sufficient: create tables if they don't exist yet.
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="SmartBus Central Server",
    description="AI-powered real-time public transport intelligence for Smart Cities.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Liveness probe. No authentication required."""
    return {"status": "ok"}


app.include_router(ingest.router)
app.include_router(public.router)
app.include_router(admin.router)
