"""Audit log / Activity log router."""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db import get_db
from app.models import AuditLog
from app.schemas import AuditLogItem

router = APIRouter(prefix="/audit-log", tags=["Audit Log"])


@router.get("", response_model=List[AuditLogItem])
def list_audit_logs(
    limit: int = Query(default=100, le=500, description="Max audit entries"),
    entity: Optional[str] = Query(None, description="Filter by entity"),
    db: Session = Depends(get_db)
):
    """List activity / audit log events in reverse chronological order."""
    query = db.query(AuditLog)
    if entity:
        query = query.filter(AuditLog.entity == entity)

    return query.order_by(desc(AuditLog.ts)).limit(limit).all()

