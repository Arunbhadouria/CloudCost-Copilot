"""Recommendations management router."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db import get_db
from app.models import Recommendation, AuditLog
from app.schemas import RecommendationItem
from app.services.dryrun import generate_dry_run_plan

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("", response_model=List[RecommendationItem])
def list_recommendations(
    dataset_id: str = Query(..., description="Target dataset ID"),
    status: Optional[str] = Query(None, description="Filter by status (open, accepted, dismissed)"),
    type: Optional[str] = Query(None, description="Filter by finding type (idle, underused, weak_signal)"),
    service: Optional[str] = Query(None, description="Filter by service name"),
    sort: str = Query(default="priority", description="Sort field (priority, savings_mid)"),
    limit: int = Query(default=100, le=200, description="Max rows"),
    db: Session = Depends(get_db)
):
    """List recommendations for a dataset with optional filters and sorting."""
    query = db.query(Recommendation).filter(Recommendation.dataset_id == dataset_id)

    if status and isinstance(status, str):
        query = query.filter(Recommendation.status == status)
    if type and isinstance(type, str):
        query = query.filter(Recommendation.type == type)
    if service and isinstance(service, str):
        query = query.filter(Recommendation.service_name == service)

    if sort == "priority":
        query = query.order_by(desc(Recommendation.priority))
    elif sort == "savings_mid":
        query = query.order_by(desc(Recommendation.savings_mid))
    else:
        query = query.order_by(desc(Recommendation.id))

    limit_n = limit if isinstance(limit, int) else getattr(limit, "default", 100)
    return query.limit(limit_n).all()


@router.get("/{id}", response_model=RecommendationItem)
def get_recommendation(
    id: int,
    db: Session = Depends(get_db)
):
    """Get single recommendation details."""
    rec = db.query(Recommendation).filter(Recommendation.id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return rec


@router.post("/{id}/accept")
def accept_recommendation(
    id: int,
    db: Session = Depends(get_db)
):
    """Mark a recommendation as accepted."""
    rec = db.query(Recommendation).filter(Recommendation.id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.status = "accepted"
    db.add(AuditLog(
        actor="user",
        action="accept_recommendation",
        entity="recommendation",
        entity_id=str(id),
        payload={"resource_id": rec.resource_id, "type": rec.type, "savings_mid": rec.savings_mid}
    ))
    db.commit()
    return {"status": "ok", "message": "Recommendation marked as accepted"}


@router.post("/{id}/dismiss")
def dismiss_recommendation(
    id: int,
    db: Session = Depends(get_db)
):
    """Dismiss a recommendation."""
    rec = db.query(Recommendation).filter(Recommendation.id == id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Recommendation not found")

    rec.status = "dismissed"
    db.add(AuditLog(
        actor="user",
        action="dismiss_recommendation",
        entity="recommendation",
        entity_id=str(id),
        payload={"resource_id": rec.resource_id, "type": rec.type}
    ))
    db.commit()
    return {"status": "ok", "message": "Recommendation dismissed"}


@router.post("/{id}/dry-run")
def preview_dry_run(
    id: int,
    db: Session = Depends(get_db)
):
    """Generate safe CLI commands and rollback instructions for a recommendation."""
    plan = generate_dry_run_plan(db, recommendation_id=id)
    if "error" in plan:
        raise HTTPException(status_code=404, detail=plan["error"])
    return plan
