"""Evaluation harness API router."""
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.db import get_db
from app.models import EvalRun
from app.schemas import EvalRunRequest
from app.services.evaluation import run_comprehensive_evaluation

router = APIRouter(prefix="/eval", tags=["Evaluation"])


@router.get("/latest")
def get_latest_eval_run(db: Session = Depends(get_db)):
    """Return the most recent evaluation run metrics."""
    latest = db.query(EvalRun).order_by(desc(EvalRun.id)).first()
    if not latest:
        # Return sensible empty default if none run yet
        return {
            "id": None,
            "created_at": None,
            "results": {
                "series_path": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "target_recall_met": False},
                "snapshot_path": {"precision": 0.0, "recall": 0.0, "f1": 0.0, "recall_drop_vs_series": 0.0},
                "savings_backtest": {"mean_mape_pct": 0.0, "meets_hypothesis": True}
            }
        }
    return {
        "id": latest.id,
        "created_at": latest.created_at,
        "results": latest.results
    }


@router.post("/run")
def trigger_evaluation_run(
    req: EvalRunRequest,
    db: Session = Depends(get_db)
):
    """Trigger a new evaluation run across specified benchmark seeds."""
    try:
        results = run_comprehensive_evaluation(db=db, seeds=req.seeds)
        return {"status": "ok", "results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

