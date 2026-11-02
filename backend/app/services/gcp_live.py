"""Live Google Cloud (GCP) resource discovery and synchronization service."""
import subprocess
import datetime
import shutil
from typing import Dict, Any, List, Optional
import httpx
from sqlalchemy.orm import Session

from app.models import (
    Dataset, Resource, CostLineItem, DailySpend,
    UtilizationSummary, Recommendation
)
from app.services.classify import get_service_class
from app.routers.detect import run_detectors
from app.schemas import DetectRunRequest


def get_local_gcloud_token() -> Optional[str]:
    """Attempt to obtain a live OAuth access token using host gcloud CLI."""
    gcloud_bin = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    if not gcloud_bin:
        return None
    try:
        proc = subprocess.run(
            [gcloud_bin, "auth", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        if proc.returncode == 0:
            token = proc.stdout.strip()
            if token and len(token) > 20:
                return token
    except Exception:
        pass
    return None


def fetch_live_gcp_resources(
    project_id: str,
    access_token: Optional[str] = None
) -> Dict[str, Any]:
    """Query live Google Cloud REST APIs for Storage, Compute, Cloud Run, and Pub/Sub.

    Returns:
        Dict with "resources": list of normalized items, and "api_statuses": dict of status messages.
    """
    token = access_token or get_local_gcloud_token()
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    resources: List[Dict[str, Any]] = []
    statuses: Dict[str, str] = {}

    if not token:
        statuses["auth"] = "No access token provided or detected via gcloud auth."
        return {"resources": [], "api_statuses": statuses}

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    with httpx.Client(timeout=10.0) as client:
        # 1. Cloud Storage Buckets (Always Free Tier eligible, default enabled)
        try:
            url = f"https://storage.googleapis.com/storage/v1/b?project={project_id}"
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                statuses["Cloud Storage"] = f"OK ({len(items)} buckets found)"
                for b in items:
                    b_name = b.get("name", "unnamed-bucket")
                    loc = b.get("location", "us-central1").lower()
                    resources.append({
                        "resource_id": f"gs://{b_name}",
                        "service_name": "Cloud Storage",
                        "service_class": "serverless",
                        "region_id": loc,
                        "resource_type": "storage_bucket",
                        "machine_type": None,
                        "billed_cost": 0.0,
                        "cpu_latest": 0.0,
                        "mem_latest": 0.0,
                        "tags": {"environment": "live-gcp", "storage_class": b.get("storageClass", "STANDARD")},
                        "created_at": b.get("timeCreated", now_iso)
                    })
            elif resp.status_code == 403:
                statuses["Cloud Storage"] = "Access forbidden (check project ID / permissions)"
            else:
                statuses["Cloud Storage"] = f"HTTP {resp.status_code}"
        except Exception as e:
            statuses["Cloud Storage"] = f"Error: {str(e)}"

        # 2. Compute Engine Instances
        try:
            url = f"https://compute.googleapis.com/compute/v1/projects/{project_id}/aggregated/instances"
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                items_dict = data.get("items", {})
                count = 0
                for zone_path, zone_data in items_dict.items():
                    inst_list = zone_data.get("instances", [])
                    for inst in inst_list:
                        count += 1
                        i_name = inst.get("name", "unnamed-instance")
                        zone = zone_path.split("/")[-1]
                        region = "-".join(zone.split("-")[:-1]) if "-" in zone else "us-central1"
                        m_type = inst.get("machineType", "").split("/")[-1] or "e2-micro"
                        status = inst.get("status", "RUNNING")
                        resources.append({
                            "resource_id": i_name,
                            "service_name": "Compute Engine",
                            "service_class": "provisioned",
                            "region_id": region,
                            "resource_type": "compute_instance",
                            "machine_type": m_type,
                            "billed_cost": 0.0,
                            "cpu_latest": 0.8 if status == "RUNNING" else 0.0,
                            "mem_latest": 6.5 if status == "RUNNING" else 0.0,
                            "tags": {"environment": "live-gcp", "status": status, "zone": zone},
                            "created_at": inst.get("creationTimestamp", now_iso)
                        })
                statuses["Compute Engine"] = f"OK ({count} instances found)"
            elif resp.status_code in (403, 404):
                statuses["Compute Engine"] = "API not enabled or project billing not linked"
            else:
                statuses["Compute Engine"] = f"HTTP {resp.status_code}"
        except Exception as e:
            statuses["Compute Engine"] = f"Error: {str(e)}"

        # 3. Cloud Run Services
        try:
            url = f"https://run.googleapis.com/v2/projects/{project_id}/locations/-/services"
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                services = data.get("services", [])
                statuses["Cloud Run"] = f"OK ({len(services)} services found)"
                for s in services:
                    s_name = s.get("name", "").split("/")[-1]
                    resources.append({
                        "resource_id": s_name,
                        "service_name": "Cloud Run",
                        "service_class": "serverless",
                        "region_id": "us-central1",
                        "resource_type": "cloud_run_service",
                        "machine_type": None,
                        "billed_cost": 0.0,
                        "cpu_latest": 0.0,
                        "mem_latest": 0.0,
                        "tags": {"environment": "live-gcp"},
                        "created_at": now_iso
                    })
            elif resp.status_code in (403, 404):
                statuses["Cloud Run"] = "API not enabled or project billing not linked"
            else:
                statuses["Cloud Run"] = f"HTTP {resp.status_code}"
        except Exception as e:
            statuses["Cloud Run"] = f"Error: {str(e)}"

        # 4. Cloud Pub/Sub Topics
        try:
            url = f"https://pubsub.googleapis.com/v1/projects/{project_id}/topics"
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                topics = data.get("topics", [])
                statuses["Cloud Pub/Sub"] = f"OK ({len(topics)} topics found)"
                for t in topics:
                    t_name = t.get("name", "").split("/")[-1]
                    resources.append({
                        "resource_id": t_name,
                        "service_name": "Cloud Pub/Sub",
                        "service_class": "serverless",
                        "region_id": "global",
                        "resource_type": "pubsub_topic",
                        "machine_type": None,
                        "billed_cost": 0.0,
                        "cpu_latest": 0.0,
                        "mem_latest": 0.0,
                        "tags": {"environment": "live-gcp"},
                        "created_at": now_iso
                    })
            else:
                statuses["Cloud Pub/Sub"] = f"HTTP {resp.status_code}"
        except Exception as e:
            statuses["Cloud Pub/Sub"] = f"Error: {str(e)}"

    return {"resources": resources, "api_statuses": statuses}


def register_live_gcp_dataset(
    db: Session,
    project_id: str,
    resources: List[Dict[str, Any]]
) -> str:
    """Register or update a live GCP dataset with discovered resources and run detectors."""
    dataset_id = f"gcp-live-{project_id}"
    dataset_name = f"Live GCP: {project_id}"

    # Upsert dataset
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        ds = Dataset(
            id=dataset_id,
            name=dataset_name,
            kind="live_gcp",
            notes=f"Live Google Cloud resources synchronized from GCP Project {project_id}.",
            created_at=datetime.datetime.now(datetime.timezone.utc)
        )
        db.add(ds)
        db.flush()

    # Clear existing resources in this live dataset for a clean refresh
    db.query(CostLineItem).filter(CostLineItem.dataset_id == dataset_id).delete()
    db.query(DailySpend).filter(DailySpend.dataset_id == dataset_id).delete()
    db.query(UtilizationSummary).filter(UtilizationSummary.dataset_id == dataset_id).delete()
    db.query(Recommendation).filter(Recommendation.dataset_id == dataset_id).delete()
    db.query(Resource).filter(Resource.dataset_id == dataset_id).delete()
    db.flush()

    today = datetime.date.today()
    start_dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
    end_dt = datetime.datetime.now(datetime.timezone.utc)

    for item in resources:
        res_id = item["resource_id"]
        svc_name = item["service_name"]
        svc_class = item.get("service_class") or get_service_class(svc_name)
        region = item.get("region_id") or "us-central1"
        billed_cost = float(item.get("billed_cost", 0.0))

        # 1. Resource
        r = Resource(
            dataset_id=dataset_id,
            resource_id=res_id,
            service_name=svc_name,
            service_class=svc_class,
            region_id=region,
            machine_type=item.get("machine_type"),
            tags=item.get("tags", {}),
            is_prod=False
        )
        db.add(r)

        # 2. CostLineItem (FOCUS schema)
        cli = CostLineItem(
            dataset_id=dataset_id,
            resource_id=res_id,
            service_name=svc_name,
            region_id=region,
            consumed_quantity=1.0,
            consumed_unit="count",
            unit_price=0.0,
            billed_cost=billed_cost,
            charge_period_start=start_dt,
            charge_period_end=end_dt
        )
        db.add(cli)

        # 3. DailySpend
        ds_spend = DailySpend(
            dataset_id=dataset_id,
            date=today,
            service_name=svc_name,
            region_id=region,
            billed_cost=billed_cost,
            is_derived=False
        )
        db.add(ds_spend)

        # 4. UtilizationSummary (for provisioned resources like Compute Engine)
        if svc_class == "provisioned":
            cpu = float(item.get("cpu_latest", 0.5))
            mem = float(item.get("mem_latest", 5.0))
            us = UtilizationSummary(
                dataset_id=dataset_id,
                resource_id=res_id,
                data_quality="snapshot",
                cpu_latest=cpu,
                cpu_avg=cpu,
                cpu_p95=cpu,
                mem_latest=mem,
                mem_avg=mem,
                mem_p95=mem,
                cpu_cv=0.1,
                window_days=1
            )
            db.add(us)

    db.commit()

    # Automatically run detectors on the new dataset
    run_detectors(req=DetectRunRequest(dataset_id=dataset_id, path="snapshot"), db=db)

    return dataset_id


