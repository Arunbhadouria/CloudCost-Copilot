"""Cost breakdown and aggregation router."""
import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models import DailySpend, CostLineItem
from app.schemas import CostBreakdownItem, CostTopItem
from app.services.forecast import generate_cost_forecast

router = APIRouter(prefix="/costs", tags=["Costs"])


@router.get("/forecast")
def get_cost_forecast(
    dataset_id: str = Query(..., description="Target dataset ID"),
    days: int = Query(default=30, ge=7, le=90, description="Forecast horizon in days"),
    service: Optional[str] = Query(default=None, description="Optional service name filter"),
    db: Session = Depends(get_db)
):
    """Generate future spend projection with confidence intervals."""
    return generate_cost_forecast(db=db, dataset_id=dataset_id, forecast_days=days, service_name=service)


@router.get("", response_model=List[CostBreakdownItem])
def get_costs(
    dataset_id: str = Query(..., description="Target dataset ID"),
    group_by: str = Query(default="service", description="Grouping dimension: service, region, or day"),
    from_date: Optional[str] = Query(None, alias="from", description="Start date YYYY-MM-DD"),
    to_date: Optional[str] = Query(None, alias="to", description="End date YYYY-MM-DD"),
    service: Optional[str] = Query(None, description="Optional service name filter"),
    limit: int = Query(default=50, le=200, description="Max rows returned"),
    db: Session = Depends(get_db)
):
    """Query aggregated costs grouped by service, region, or day with precomputed share percentages."""
    allowed_groups = {"service", "region", "day"}
    if group_by not in allowed_groups:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid group_by '{group_by}'. Allowed dimensions: {', '.join(sorted(allowed_groups))}"
        )

    # Base query on daily_spend
    query = db.query(DailySpend).filter(DailySpend.dataset_id == dataset_id)

    if from_date and isinstance(from_date, str):
        try:
            d_from = datetime.datetime.strptime(from_date, "%Y-%m-%d").date()
            query = query.filter(DailySpend.date >= d_from)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid from_date format, expected YYYY-MM-DD")

    if to_date and isinstance(to_date, str):
        try:
            d_to = datetime.datetime.strptime(to_date, "%Y-%m-%d").date()
            query = query.filter(DailySpend.date <= d_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid to_date format, expected YYYY-MM-DD")

    if service and isinstance(service, str):
        query = query.filter(DailySpend.service_name == service)

    # Calculate total sum for precomputing percentages
    subq = query.subquery()
    total_spend = db.query(func.sum(subq.c.billed_cost)).scalar() or 0.0

    if group_by == "service":
        results = db.query(
            subq.c.service_name.label("key"),
            func.sum(subq.c.billed_cost).label("cost")
        ).group_by(subq.c.service_name).order_by(func.sum(subq.c.billed_cost).desc()).limit(limit).all()

    elif group_by == "region":
        results = db.query(
            subq.c.region_id.label("key"),
            func.sum(subq.c.billed_cost).label("cost")
        ).group_by(subq.c.region_id).order_by(func.sum(subq.c.billed_cost).desc()).limit(limit).all()

    else:  # day
        results = db.query(
            subq.c.date.label("key"),
            func.sum(subq.c.billed_cost).label("cost")
        ).group_by(subq.c.date).order_by(subq.c.date.asc()).limit(limit).all()

    output = []
    for r in results:
        cost = float(r.cost or 0.0)
        key_str = r.key.strftime("%Y-%m-%d") if isinstance(r.key, (datetime.date, datetime.datetime)) else str(r.key)
        share = round((cost / total_spend * 100.0), 2) if total_spend > 0 else 0.0
        output.append(CostBreakdownItem(
            key=key_str,
            billed_cost=round(cost, 2),
            share_pct=share
        ))

    return output


@router.get("/top", response_model=List[CostTopItem])
def get_top_costs(
    dataset_id: str = Query(..., description="Target dataset ID"),
    n: int = Query(default=5, ge=1, le=25, description="Number of top services"),
    db: Session = Depends(get_db)
):
    """Return top N services by billed cost with precomputed share percentages."""
    total_spend = db.query(func.sum(DailySpend.billed_cost)).filter(
        DailySpend.dataset_id == dataset_id
    ).scalar() or 0.0

    limit_n = n if isinstance(n, int) else (getattr(n, "default", 5))

    results = db.query(
        DailySpend.service_name,
        func.sum(DailySpend.billed_cost).label("cost")
    ).filter(
        DailySpend.dataset_id == dataset_id
    ).group_by(DailySpend.service_name).order_by(
        func.sum(DailySpend.billed_cost).desc()
    ).limit(limit_n).all()

    output = []
    for r in results:
        cost = float(r.cost or 0.0)
        share = round((cost / total_spend * 100.0), 2) if total_spend > 0 else 0.0
        output.append(CostTopItem(
            service_name=str(r.service_name),
            billed_cost=round(cost, 2),
            share_pct=share
        ))

    return output

