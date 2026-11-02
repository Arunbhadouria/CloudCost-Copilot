"""Rule-based finders and detectors for idle, underused, and weak-signal resources."""
from typing import Dict, Any, Optional, Tuple, List
import random
from sqlalchemy.orm import Session

from app.models import UtilizationSummary, Resource, UtilizationSeries


def evaluate_resource_detector(
    summary: Dict[str, Any],
    service_class: str,
    tags: Optional[Dict[str, Any]] = None,
    path: str = "snapshot"
) -> Optional[Tuple[str, str]]:
    """Evaluate detector rules for a single resource.

    Args:
        summary: dict or attributes from UtilizationSummary
        service_class: service class string
        tags: resource tags dict
        path: 'snapshot' or 'series'

    Returns:
        (finding_type, reason) where finding_type is 'idle', 'underused', 'weak_signal', or None
    """
    if service_class != "provisioned":
        return None

    tags = tags or {}
    role = str(tags.get("role", "")).lower()
    if role in ("dr", "batch"):
        return None

    if path == "snapshot":
        cpu = float(summary.get("cpu_latest", 0.0))
        mem = float(summary.get("mem_latest", 0.0))

        if cpu < 5.0:
            return "idle", f"CPU utilization ({cpu:.1f}%) is below 5% idle threshold."
        if cpu < 20.0 and mem < 20.0:
            return "underused", f"Both CPU ({cpu:.1f}%) and Memory ({mem:.1f}%) are below 20% right-sizing threshold."
        if (cpu < 20.0) ^ (mem < 20.0):
            dim = "CPU" if cpu < 20.0 else "Memory"
            val = cpu if cpu < 20.0 else mem
            return "weak_signal", f"Asymmetric utilization: {dim} ({val:.1f}%) is below 20% while other metric is active."
        return None

    else:  # 'series' path
        cpu_avg = float(summary.get("cpu_avg", 0.0))
        cpu_p95 = summary.get("cpu_p95")
        mem_p95 = summary.get("mem_p95")

        if cpu_p95 is None or mem_p95 is None:
            # Fall back to latest if p95 is missing
            return evaluate_resource_detector(summary, service_class, tags, path="snapshot")

        cpu_p95 = float(cpu_p95)
        mem_p95 = float(mem_p95)

        if cpu_avg < 5.0 and cpu_p95 < 10.0:
            return "idle", f"Average CPU ({cpu_avg:.1f}%) and 95th percentile CPU ({cpu_p95:.1f}%) consistently below idle thresholds."
        if cpu_p95 < 20.0 and mem_p95 < 20.0:
            return "underused", f"Both 95th percentile CPU ({cpu_p95:.1f}%) and Memory ({mem_p95:.1f}%) below 20% right-sizing threshold."
        if (cpu_p95 < 20.0) ^ (mem_p95 < 20.0):
            dim = "CPU" if cpu_p95 < 20.0 else "Memory"
            val = cpu_p95 if cpu_p95 < 20.0 else mem_p95
            return "weak_signal", f"Asymmetric load: {dim} p95 ({val:.1f}%) below 20% while other metric is active."
        return None


def make_snapshot(db: Session, dataset_id: str, seed: int = 42) -> List[UtilizationSummary]:
    """Build a snapshot-only view of synthetic data using one seeded random day per resource."""
    py_rng = random.Random(seed)

    resources = db.query(Resource).filter(
        Resource.dataset_id == dataset_id,
        Resource.service_class == "provisioned"
    ).all()

    snapshot_summaries = []
    for res in resources:
        series_days = db.query(UtilizationSeries).filter(
            UtilizationSeries.dataset_id == dataset_id,
            UtilizationSeries.resource_id == res.resource_id
        ).all()

        if not series_days:
            continue

        chosen_day = py_rng.choice(series_days)
        summary = UtilizationSummary(
            dataset_id=dataset_id,
            resource_id=res.resource_id,
            data_quality="snapshot",
            cpu_latest=chosen_day.cpu_avg,
            cpu_avg=chosen_day.cpu_avg,
            cpu_p95=None,
            mem_latest=chosen_day.mem_avg,
            mem_avg=chosen_day.mem_avg,
            mem_p95=None,
            cpu_cv=None,
            window_days=1
        )
        snapshot_summaries.append(summary)

    return snapshot_summaries

