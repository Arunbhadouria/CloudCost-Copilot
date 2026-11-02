"""Dataset management router."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models import Dataset, Resource, CostLineItem, DailySpend, Recommendation, Anomaly, DataWarning
from app.schemas import (
    HealthResponse, DatasetItem, CsvUploadResponse,
    DatasetSummaryResponse, DataWarningItem, SyntheticGenerateRequest
)
from app.services.loader import load_csv_dataset
from app.services.generator import generate_synthetic_dataset

router = APIRouter(tags=["Datasets"])


@router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint."""
    return HealthResponse(status="ok", version="1.0.0")


@router.get("/datasets", response_model=List[DatasetItem])
def list_datasets(db: Session = Depends(get_db)):
    """List all available ingested and synthetic datasets."""
    items = db.query(Dataset).order_by(Dataset.created_at.desc()).all()
    return items


@router.post("/datasets/csv", response_model=CsvUploadResponse)
async def upload_csv_dataset(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """Upload and ingest a real-format GCP billing export sample CSV."""
    content = await file.read()
    dataset_name = name or file.filename or "Real-format GCP billing sample"
    try:
        result = load_csv_dataset(db=db, file_content=content, dataset_name=dataset_name)
        return CsvUploadResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/datasets/synthetic")
def create_synthetic_dataset(
    req: SyntheticGenerateRequest,
    db: Session = Depends(get_db)
):
    """Generate a synthetic 12-month ground truth benchmark dataset."""
    try:
        ds_id = generate_synthetic_dataset(
            db=db,
            seed=req.seed,
            months=req.months,
            num_resources=req.resources,
            start_date_str=req.start_date,
            anomaly_rate=req.anomaly_rate
        )
        return {"dataset_id": ds_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/datasets/{id}/summary", response_model=DatasetSummaryResponse)
def get_dataset_summary(id: str, db: Session = Depends(get_db)):
    """Return high-level summary KPIs and metadata for a given dataset."""
    ds = db.query(Dataset).filter(Dataset.id == id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    total_cost = db.query(func.sum(CostLineItem.billed_cost)).filter(CostLineItem.dataset_id == id).scalar() or 0.0
    res_count = db.query(func.count(Resource.id)).filter(Resource.dataset_id == id).scalar() or 0

    min_date = db.query(func.min(DailySpend.date)).filter(DailySpend.dataset_id == id).scalar()
    max_date = db.query(func.max(DailySpend.date)).filter(DailySpend.dataset_id == id).scalar()

    is_derived = db.query(DailySpend.is_derived).filter(DailySpend.dataset_id == id).first()
    is_derived_bool = bool(is_derived[0]) if is_derived else False

    # Recommendations & savings
    findings_count = db.query(func.count(Recommendation.id)).filter(
        Recommendation.dataset_id == id,
        Recommendation.status != "dismissed"
    ).scalar() or 0

    savings_low = db.query(func.sum(Recommendation.savings_low)).filter(
        Recommendation.dataset_id == id,
        Recommendation.status != "dismissed"
    ).scalar() or 0.0

    savings_high = db.query(func.sum(Recommendation.savings_high)).filter(
        Recommendation.dataset_id == id,
        Recommendation.status != "dismissed"
    ).scalar() or 0.0

    anomalies_count = db.query(func.count(Anomaly.id)).filter(Anomaly.dataset_id == id).scalar() or 0

    return DatasetSummaryResponse(
        id=ds.id,
        name=ds.name,
        kind=ds.kind,
        total_cost=round(total_cost, 2),
        resources=res_count,
        date_range={
            "start": min_date.strftime("%Y-%m-%d") if min_date else None,
            "end": max_date.strftime("%Y-%m-%d") if max_date else None,
        },
        is_derived_daily=is_derived_bool,
        findings_count=findings_count,
        savings_range={
            "low": round(savings_low, 2),
            "high": round(savings_high, 2)
        },
        anomalies_count=anomalies_count
    )


@router.get("/datasets/{id}/warnings", response_model=List[DataWarningItem])
def get_dataset_warnings(
    id: str,
    limit: int = Query(default=100, le=200),
    db: Session = Depends(get_db)
):
    """List data warnings, quarantined rows, and mixed unit notifications for a dataset."""
    warnings = db.query(DataWarning).filter(
        DataWarning.dataset_id == id
    ).limit(limit).all()

    return [
        DataWarningItem(
            id=w.id,
            kind=w.kind,
            resource_id=w.resource_id,
            detail=w.detail
        ) for w in warnings
    ]
