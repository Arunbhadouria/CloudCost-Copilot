"""Detector execution router for generating cost recommendations."""
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models import Dataset, Resource, UtilizationSummary, Recommendation, CostLineItem
from app.schemas import DetectRunRequest, DetectRunResponse
from app.services.detectors import evaluate_resource_detector
from app.services.savings import calculate_savings
from app.services.ranking import calculate_confidence, calculate_effort, calculate_priority

router = APIRouter(prefix="/detect", tags=["Detection"])


@router.post("/run", response_model=DetectRunResponse)
def run_detectors(
    req: DetectRunRequest,
    db: Session = Depends(get_db)
):
    """Run rule-based detection on provisioned resources in a dataset and save recommendations."""
    ds = db.query(Dataset).filter(Dataset.id == req.dataset_id).first()
    if not ds:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # Determine execution path
    if req.path == "auto":
        path_used = "series" if ds.kind == "synthetic" else "snapshot"
    else:
        path_used = req.path

    # Clean existing recommendations for dataset
    db.query(Recommendation).filter(Recommendation.dataset_id == req.dataset_id).delete()
    db.flush()

    # Query provisioned resources
    prov_resources = db.query(Resource).filter(
        Resource.dataset_id == req.dataset_id,
        Resource.service_class == "provisioned"
    ).all()

    counts = {"idle": 0, "underused": 0, "weak_signal": 0}
    total_savings_mid = 0.0
    rec_models = []

    for res in prov_resources:
        summary = db.query(UtilizationSummary).filter(
            UtilizationSummary.dataset_id == req.dataset_id,
            UtilizationSummary.resource_id == res.resource_id
        ).first()

        if not summary:
            continue

        summary_dict = {
            "cpu_latest": summary.cpu_latest,
            "cpu_avg": summary.cpu_avg,
            "cpu_p95": summary.cpu_p95,
            "mem_latest": summary.mem_latest,
            "mem_avg": summary.mem_avg,
            "mem_p95": summary.mem_p95,
        }

        eval_result = evaluate_resource_detector(
            summary=summary_dict,
            service_class=res.service_class,
            tags=res.tags,
            path=path_used
        )

        if not eval_result:
            continue

        finding_type, reason = eval_result
        counts[finding_type] = counts.get(finding_type, 0) + 1

        # Calculate billed cost for savings basis
        billed_cost = db.query(func.sum(CostLineItem.billed_cost)).filter(
            CostLineItem.dataset_id == req.dataset_id,
            CostLineItem.resource_id == res.resource_id
        ).scalar() or 0.0

        savings = calculate_savings(
            finding_type=finding_type,
            dataset_kind=ds.kind,
            billed_cost=billed_cost,
            machine_type=res.machine_type
        )

        confidence = calculate_confidence(
            data_quality=path_used,
            is_prod=res.is_prod,
            cpu_cv=summary.cpu_cv
        )

        effort = calculate_effort(finding_type)

        priority = calculate_priority(
            savings_mid=savings["savings_mid"],
            confidence=confidence,
            effort=effort,
            finding_type=finding_type
        )

        total_savings_mid += savings["savings_mid"]

        rec_models.append(Recommendation(
            dataset_id=req.dataset_id,
            resource_id=res.resource_id,
            service_name=res.service_name,
            type=finding_type,
            savings_low=savings["savings_low"],
            savings_high=savings["savings_high"],
            savings_mid=savings["savings_mid"],
            savings_basis=savings["savings_basis"],
            savings_unit=savings["savings_unit"],
            confidence=confidence,
            effort=effort,
            priority=priority,
            reason=reason,
            status="open"
        ))

    db.bulk_save_objects(rec_models)
    db.commit()

    return DetectRunResponse(
        dataset_id=req.dataset_id,
        path_used=path_used,
        counts=counts,
        total_savings_mid=round(total_savings_mid, 2)
    )

