"""Router for live Google Cloud (GCP) project synchronization."""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.gcp_live import (
    fetch_live_gcp_resources,
    register_live_gcp_dataset,
    get_local_gcloud_token
)

router = APIRouter(prefix="/gcp", tags=["Google Cloud Live"])


class GcpSyncRequest(BaseModel):
    project_id: str = Field(..., description="Google Cloud Project ID (e.g. big-formula-489906-e6)")
    access_token: Optional[str] = Field(None, description="Optional OAuth access token from gcloud auth print-access-token")


@router.get("/status")
def get_gcp_status():
    """Check whether local gcloud credentials and token are detected."""
    token = get_local_gcloud_token()
    return {
        "gcloud_detected": token is not None,
        "token_available": token is not None,
        "default_project": "big-formula-489906-e6"
    }


@router.post("/sync")
def sync_live_gcp(req: GcpSyncRequest, db: Session = Depends(get_db)):
    """Fetch live resources directly from Google Cloud REST APIs and register as a live dataset."""
    project_id = req.project_id.strip()
    if not project_id:
        raise HTTPException(status_code=400, detail="Project ID cannot be empty.")

    result = fetch_live_gcp_resources(project_id=project_id, access_token=req.access_token)
    resources = result["resources"]
    statuses = result["api_statuses"]

    dataset_id = register_live_gcp_dataset(db=db, project_id=project_id, resources=resources)

    return {
        "dataset_id": dataset_id,
        "project_id": project_id,
        "resources_synced": len(resources),
        "api_statuses": statuses,
        "resources": resources
    }
