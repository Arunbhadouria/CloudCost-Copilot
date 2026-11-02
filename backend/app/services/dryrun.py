"""Dry-run planner generating safe, non-destructive CLI preview commands and rollback instructions."""
import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import Recommendation, Resource, AuditLog
from app.services.savings import get_next_size_down


def generate_dry_run_plan(
    db: Session,
    recommendation_id: int,
    actor: str = "DevOps Lead"
) -> Dict[str, Any]:
    """Generate safe, idempotent preview commands and rollback instructions.

    Enforces strict safety rules:
    - Never actually executes any cloud actions.
    - Uses placeholders [PROJECT_ID] and [ZONE].
    - Refuses automated script generation for production-tagged resources.
    - Logs every generated plan to audit_log.
    """
    rec = db.query(Recommendation).filter(Recommendation.id == recommendation_id).first()
    if not rec:
        return {"error": f"Recommendation {recommendation_id} not found"}

    res = db.query(Resource).filter(
        Resource.dataset_id == rec.dataset_id,
        Resource.resource_id == rec.resource_id
    ).first()

    is_prod = False
    if res:
        is_prod = bool(res.is_prod)
        if isinstance(res.tags, dict) and res.tags.get("env") == "prod":
            is_prod = True

    # 1. Refuse automated script for production resources
    if is_prod:
        result = {
            "recommendation_id": rec.id,
            "resource_id": rec.resource_id,
            "status": "refused",
            "is_prod": True,
            "warning": "Production resource: manual review required, no automated script generated.",
            "cli_command": None,
            "rollback_command": None
        }

        audit_entry = AuditLog(
            ts=datetime.datetime.utcnow(),
            actor=actor,
            action="dry_run_refused_prod",
            entity="recommendations",
            entity_id=rec.id,
            payload={
                "resource_id": rec.resource_id,
                "reason": "Production resource requires manual review",
                "finding_type": rec.type
            }
        )
        db.add(audit_entry)
        db.commit()
        return result

    # 2. Build CLI commands based on service and finding type
    svc = rec.service_name
    r_id = rec.resource_id
    f_type = rec.type
    machine = res.machine_type if res else "e2-standard-4"
    next_machine = get_next_size_down(machine) or "e2-standard-2"
    region = res.region_id if res else "[REGION]"

    if svc == "Compute Engine":
        if f_type == "idle":
            cli_cmd = (
                f"# Step 1: Stop unused Compute Engine instance\n"
                f"gcloud compute instances stop {r_id} \\\n"
                f"    --project=[PROJECT_ID] \\\n"
                f"    --zone=[ZONE]"
            )
            rollback_cmd = (
                f"# How to undo: Start Compute Engine instance\n"
                f"gcloud compute instances start {r_id} \\\n"
                f"    --project=[PROJECT_ID] \\\n"
                f"    --zone=[ZONE]"
            )
        else:  # underused
            cli_cmd = (
                f"# Step 1: Stop instance before resizing\n"
                f"gcloud compute instances stop {r_id} \\\n"
                f"    --project=[PROJECT_ID] \\\n"
                f"    --zone=[ZONE]\n\n"
                f"# Step 2: Downsize machine type ({machine} -> {next_machine})\n"
                f"gcloud compute instances set-machine-type {r_id} \\\n"
                f"    --machine-type={next_machine} \\\n"
                f"    --project=[PROJECT_ID] \\\n"
                f"    --zone=[ZONE]\n\n"
                f"# Step 3: Restart resized instance\n"
                f"gcloud compute instances start {r_id} \\\n"
                f"    --project=[PROJECT_ID] \\\n"
                f"    --zone=[ZONE]"
            )
            rollback_cmd = (
                f"# How to undo: Restore original machine type ({next_machine} -> {machine})\n"
                f"gcloud compute instances stop {r_id} \\\n"
                f"    --project=[PROJECT_ID] \\\n"
                f"    --zone=[ZONE]\n\n"
                f"gcloud compute instances set-machine-type {r_id} \\\n"
                f"    --machine-type={machine} \\\n"
                f"    --project=[PROJECT_ID] \\\n"
                f"    --zone=[ZONE]\n\n"
                f"gcloud compute instances start {r_id} \\\n"
                f"    --project=[PROJECT_ID] \\\n"
                f"    --zone=[ZONE]"
            )
    elif svc == "Cloud SQL":
        cli_cmd = (
            f"# Downsize Cloud SQL instance tier\n"
            f"gcloud sql instances patch {r_id} \\\n"
            f"    --tier=db-custom-2-7680 \\\n"
            f"    --project=[PROJECT_ID]"
        )
        rollback_cmd = (
            f"# How to undo: Restore Cloud SQL instance tier\n"
            f"gcloud sql instances patch {r_id} \\\n"
            f"    --tier=db-custom-4-15360 \\\n"
            f"    --project=[PROJECT_ID]"
        )
    elif svc == "Cloud Dataproc":
        cli_cmd = (
            f"# Stop idle Dataproc cluster\n"
            f"gcloud dataproc clusters stop {r_id} \\\n"
            f"    --region={region} \\\n"
            f"    --project=[PROJECT_ID]"
        )
        rollback_cmd = (
            f"# How to undo: Start Dataproc cluster\n"
            f"gcloud dataproc clusters start {r_id} \\\n"
            f"    --region={region} \\\n"
            f"    --project=[PROJECT_ID]"
        )
    else:
        cli_cmd = (
            f"# Safe inspection and stop command for {svc}\n"
            f"gcloud {svc.lower().replace(' ', '-')} resources stop {r_id} \\\n"
            f"    --project=[PROJECT_ID]"
        )
        rollback_cmd = (
            f"# How to undo: Start {svc} resource\n"
            f"gcloud {svc.lower().replace(' ', '-')} resources start {r_id} \\\n"
            f"    --project=[PROJECT_ID]"
        )

    # Update recommendation status and record audit log
    rec.status = "dry_run_generated"

    audit_entry = AuditLog(
        ts=datetime.datetime.utcnow(),
        actor=actor,
        action="dry_run_generated",
        entity="recommendations",
        entity_id=rec.id,
        payload={
            "resource_id": r_id,
            "service_name": svc,
            "finding_type": f_type,
            "machine_type": machine,
            "target_machine": next_machine if f_type == "underused" else None
        }
    )
    db.add(audit_entry)
    db.commit()

    return {
        "recommendation_id": rec.id,
        "resource_id": r_id,
        "status": "ready",
        "is_prod": False,
        "cli_command": cli_cmd,
        "rollback_command": rollback_cmd,
        "explanation": "These are safe CLI preview commands with placeholders. They will not execute against your live cloud."
    }

