"""Cost jump and anomaly detection router."""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db import get_db
from app.models import Anomaly, Dataset, DailySpend
from app.schemas import AnomalyItem
from app.services.anomaly import detect_anomalies_for_dataset

router = APIRouter(prefix="/anomalies", tags=["Anomalies"])


@router.get("", response_model=List[AnomalyItem])
def get_dataset_anomalies(
    dataset_id: str = Query(..., description="Target dataset ID"),
    db: Session = Depends(get_db)
):
    """Retrieve detected cost jumps for a dataset."""
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # If CSV dataset, return empty list (insufficient history)
    if ds.kind == "csv":
        return []

    # Check if anomalies exist, otherwise run detector
    existing = db.query(Anomaly).filter(Anomaly.dataset_id == dataset_id).order_by(desc(Anomaly.start_date)).all()
    if not existing:
        detect_anomalies_for_dataset(db, dataset_id)
        existing = db.query(Anomaly).filter(Anomaly.dataset_id == dataset_id).order_by(desc(Anomaly.start_date)).all()

    return [
        AnomalyItem(
            id=a.id,
            dataset_id=a.dataset_id,
            start_date=a.start_date.strftime("%Y-%m-%d"),
            end_date=a.end_date.strftime("%Y-%m-%d"),
            service_name=a.service_name,
            expected=a.expected,
            actual=a.actual,
            peak_zscore=a.peak_zscore,
            severity=a.severity,
            explained_by=a.explained_by
        ) for a in existing
    ]


@router.get("/{id}/attribution")
def get_anomaly_attribution(
    id: int,
    db: Session = Depends(get_db)
):
    """Decompose cost jump into top contributing regions and resources (Stretch)."""
    anom = db.query(Anomaly).filter(Anomaly.id == id).first()
    if not anom:
        raise HTTPException(status_code=404, detail="Cost jump event not found")

    return {
        "anomaly_id": anom.id,
        "service_name": anom.service_name,
        "actual": anom.actual,
        "expected": anom.expected,
        "delta": round(anom.actual - anom.expected, 2),
        "explained_by": anom.explained_by or []
    }

