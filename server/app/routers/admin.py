"""Admin endpoints for the transport company (anomaly queue)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.middleware.auth import require_admin_key
from app.models.anomaly import AnomalyQueue
from app.schemas.output import AnomalyList, AnomalyOut

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_key)])


@router.get("/anomalies", response_model=AnomalyList)
def list_anomalies(
    status: str | None = Query(default=None, description="Filter: PENDING | PROCESSED"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AnomalyList:
    stmt = select(AnomalyQueue)
    count_stmt = select(func.count()).select_from(AnomalyQueue)
    if status:
        stmt = stmt.where(AnomalyQueue.status == status)
        count_stmt = count_stmt.where(AnomalyQueue.status == status)

    total = db.scalar(count_stmt) or 0
    rows = db.scalars(
        stmt.order_by(AnomalyQueue.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return AnomalyList(
        anomalies=[AnomalyOut.model_validate(r) for r in rows],
        total=total,
        page=page,
    )
