"""API key authentication, used as FastAPI dependencies."""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.config import ADMIN_API_KEY, API_KEY, API_KEY_HEADER


def require_api_key(x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER)) -> None:
    """Allow any caller presenting the standard device/app key or the admin key."""
    if x_api_key not in (API_KEY, ADMIN_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key.",
            headers={"WWW-Authenticate": API_KEY_HEADER},
        )


def require_admin_key(x_api_key: str | None = Header(default=None, alias=API_KEY_HEADER)) -> None:
    """Admin-only endpoints (e.g. the anomaly queue)."""
    if x_api_key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin API key required.",
            headers={"WWW-Authenticate": API_KEY_HEADER},
        )
