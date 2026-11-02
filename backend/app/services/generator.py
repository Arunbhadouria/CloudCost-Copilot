"""Synthetic GCP billing and utilization time-series generator with planted ground truth."""
import json
import random
import datetime
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Dataset, Resource, CostLineItem, DailySpend,
    UtilizationSeries, UtilizationSummary, GroundTruth
)
from app.services.classify import get_service_class, is_provisioned

PROVISIONED_SERVICES = [
    "Compute Engine", "Kubernetes Engine", "Cloud SQL",
    "Cloud Memorystore", "Cloud Dataproc"
]

SERVERLESS_SERVICES = [
    "Cloud Run", "Cloud Functions", "Dataflow", "BigQuery", "Cloud Build"
]

STORAGE_MESSAGING_SERVICES = [
    "Cloud Storage", "Firestore", "Pub/Sub", "Container Registry", "Cloud CDN"
]

NETWORK_SERVICES = [
    "Cloud VPC", "Cloud VPN", "Cloud NAT", "Cloud Interconnect",
    "Cloud Load Balancing", "Cloud Armor", "Cloud Endpoints"
]

OTHER_MANAGED_SERVICES = [
    "Cloud Spanner", "Cloud Data Fusion", "AI Platform"
]

ALL_25_SERVICES = (
    PROVISIONED_SERVICES + SERVERLESS_SERVICES +
    STORAGE_MESSAGING_SERVICES + NETWORK_SERVICES +
    OTHER_MANAGED_SERVICES
)

REGIONS = [
    "us-central1", "us-east1", "us-west1", "europe-west1",
    "europe-north1", "asia-east1", "asia-southeast1",
    "australia-southeast1", "southamerica-east1", "northamerica-northeast1"
]


def _load_price_table() -> Dict[str, Any]:
    price_path = settings.REFERENCE_DIR / "price_table.json"
    with open(price_path, "r", encoding="utf-8") as f:
        return json.load(f)


def generate_synthetic_dataset(
    db: Session,
    seed: int = 1,
    months: int = 12,
    num_resources: int = 300,
    start_date_str: str = "2025-01-01",
    anomaly_rate: float = 0.05,
    dataset_name: Optional[str] = None,
    dataset_id: Optional[str] = None
) -> str:
    """Generate a synthetic daily dataset with planted ground truth."""
    if not dataset_id:
        dataset_id = f"synthetic-seed-{seed}"
    if not dataset_name:
        dataset_name = f"Synthetic Benchmark (Seed {seed})"

    # Clean existing dataset with same ID if present
    existing = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if existing:
        db.delete(existing)
        db.commit()

    rng = np.random.default_rng(seed)
    py_rng = random.Random(seed)

    price_table = _load_price_table()
    machine_types = list(price_table["machines"].keys())

    start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d").date()
    days_count = max(3, months * 30)
    date_list = [start_date + datetime.timedelta(days=i) for i in range(days_count)]

    # 1. Allocate resources (~40% provisioned = 120 out of 300)
    num_provisioned = max(44, int(round(num_resources * 0.40)))
    num_non_provisioned = max(1, num_resources - num_provisioned)

    resource_defs: List[Dict[str, Any]] = []

    # Provisioned resource categories:
    # 12 planted idle, 12 planted underused, 8 bursty, 6 batch, 6 DR, remaining normal
    category_counts = {
        "planted_idle": 12,
        "planted_underused": 12,
        "bursty": 8,
        "batch": 6,
        "dr": 6,
        "normal": max(0, num_provisioned - (12 + 12 + 8 + 6 + 6))
    }

    prov_svc_cycle = PROVISIONED_SERVICES * 30
    res_idx = 1

    for cat, count in category_counts.items():
        for _ in range(count):
            res_id = f"res-syn-prov-{res_idx:04d}"
            svc = prov_svc_cycle[res_idx % len(prov_svc_cycle)]
            reg = py_rng.choice(REGIONS)
            m_type = py_rng.choice(machine_types)
            env = py_rng.choice(["prod", "dev", "test"])
            is_prod = (env == "prod")

            if cat == "batch":
                role = "batch"
            elif cat == "dr":
                role = "dr"
            else:
                role = py_rng.choice(["web", "db", "app"])

            tags = {"env": env, "role": role}

            resource_defs.append({
                "resource_id": res_id,
                "service_name": svc,
                "service_class": "provisioned",
                "region_id": reg,
                "machine_type": m_type,
                "tags": tags,
                "is_prod": is_prod,
                "category": cat
            })
            res_idx += 1

    # Non-provisioned resources (60% across 20 other services)
    non_prov_services = (
        SERVERLESS_SERVICES + STORAGE_MESSAGING_SERVICES +
        NETWORK_SERVICES + OTHER_MANAGED_SERVICES
    )
    for i in range(num_non_provisioned):
        res_id = f"res-syn-nonprov-{(i+1):04d}"
        svc = non_prov_services[i % len(non_prov_services)]
        reg = py_rng.choice(REGIONS)
        env = py_rng.choice(["prod", "dev", "test"])
        resource_defs.append({
            "resource_id": res_id,
            "service_name": svc,
            "service_class": get_service_class(svc),
            "region_id": reg,
            "machine_type": None,
            "tags": {"env": env, "role": "worker"},
            "is_prod": (env == "prod"),
            "category": "non_provisioned"
        })

    # 2. Plan Anomaly Events (~20 positive events + event hard negatives)
    anomaly_events = []
    # 10 Spikes (1 to 3 days, x3 to x6)
    for i in range(10):
        duration = min(days_count, py_rng.randint(1, 3))
        max_start = max(0, days_count - duration)
        day_offset = py_rng.randint(0, max_start)
        mult = py_rng.uniform(3.0, 6.0)
        svc = py_rng.choice(ALL_25_SERVICES)
        anomaly_events.append({
            "kind": "anomaly",
            "subtype": "spike",
            "target": svc,
            "start_day": day_offset,
            "end_day": min(days_count - 1, day_offset + duration - 1),
            "multiplier": mult,
            "is_positive": True,
            "note": f"Cost spike x{mult:.1f} for {duration} day(s)"
        })

    # 3 Step changes (+40% permanent)
    for i in range(3):
        max_start = max(1, days_count - 5)
        day_offset = py_rng.randint(0, max_start)
        svc = py_rng.choice(PROVISIONED_SERVICES + SERVERLESS_SERVICES)
        anomaly_events.append({
            "kind": "anomaly",
            "subtype": "step_change",
            "target": svc,
            "start_day": day_offset,
            "end_day": days_count - 1,
            "multiplier": 1.40,
            "is_positive": True,
            "note": "Permanent +40% step increase"
        })

    # 3 Slow drift (+1%/day for up to 30 days)
    for i in range(3):
        drift_len = min(30, max(2, days_count // 3))
        max_start = max(0, days_count - drift_len)
        day_offset = py_rng.randint(0, max_start)
        svc = py_rng.choice(PROVISIONED_SERVICES + SERVERLESS_SERVICES)
        anomaly_events.append({
            "kind": "anomaly",
            "subtype": "slow_drift",
            "target": svc,
            "start_day": day_offset,
            "end_day": min(days_count - 1, day_offset + drift_len),
            "drift_rate": 0.01,
            "is_positive": True,
            "note": f"Slow drift +1%/day over {drift_len} days"
        })

    # 4 Overlapping pairs (2 pairs)
    if days_count >= 5:
        pair1_day = py_rng.randint(0, max(0, days_count - 4))
        svc1, svc2 = py_rng.sample(PROVISIONED_SERVICES, 2)
        anomaly_events.append({
            "kind": "anomaly",
            "subtype": "overlapping_pair",
            "target": svc1,
            "start_day": pair1_day,
            "end_day": min(days_count - 1, pair1_day + 2),
            "multiplier": 4.5,
            "is_positive": True,
            "note": "Overlapping spike pair 1"
        })
        anomaly_events.append({
            "kind": "anomaly",
            "subtype": "overlapping_pair",
            "target": svc2,
            "start_day": min(days_count - 1, pair1_day + 1),
            "end_day": min(days_count - 1, pair1_day + 3),
            "multiplier": 3.8,
            "is_positive": True,
            "note": "Overlapping spike pair 2"
        })

        pair2_day = py_rng.randint(0, max(0, days_count - 5))
        svc3, svc4 = py_rng.sample(SERVERLESS_SERVICES, 2)
        anomaly_events.append({
            "kind": "anomaly",
            "subtype": "overlapping_pair",
            "target": svc3,
            "start_day": pair2_day,
            "end_day": min(days_count - 1, pair2_day + 2),
            "multiplier": 5.0,
            "is_positive": True,
            "note": "Overlapping spike pair 3"
        })
        anomaly_events.append({
            "kind": "anomaly",
            "subtype": "overlapping_pair",
            "target": svc4,
            "start_day": min(days_count - 1, pair2_day + 1),
            "end_day": min(days_count - 1, pair2_day + 4),
            "multiplier": 3.5,
            "is_positive": True,
            "note": "Overlapping spike pair 4"
        })

    # Event Hard Negatives: Month-end bumps (+15% last 2 days of each month for 3 services)
    month_end_services = ["BigQuery", "Cloud Storage", "Compute Engine"]
    for m in range(months):
        end_idx = min(days_count - 1, (m + 1) * 30 - 1)
        start_idx = max(0, end_idx - 1)
        for svc in month_end_services:
            anomaly_events.append({
                "kind": "hard_negative",
                "subtype": "month_end_bump",
                "target": svc,
                "start_day": start_idx,
                "end_day": end_idx,
                "multiplier": 1.15,
                "is_positive": False,
                "note": f"Expected month-end batch processing bump (+15%) in month {m+1}"
            })

    # Event Hard Negatives: 3 Launch spikes (planned launches, labeled negative)
    for i in range(3):
        max_start = max(0, days_count - 2)
        day_offset = py_rng.randint(0, max_start)
        svc = py_rng.choice(["Compute Engine", "Cloud Run", "Cloud Load Balancing"])
        anomaly_events.append({
            "kind": "hard_negative",
            "subtype": "launch_spike",
            "target": svc,
            "start_day": day_offset,
            "end_day": min(days_count - 1, day_offset + 1),
            "multiplier": 1.5,
            "is_positive": False,
            "note": "Planned marketing launch spike"
        })

    # Save Ground Truth records
    gt_records: List[GroundTruth] = []

    # Resource ground truth (Planted positives & hard negatives)
    for r in resource_defs:
        cat = r["category"]
        res_id = r["resource_id"]
        if cat == "planted_idle":
            gt_records.append(GroundTruth(
                dataset_id=dataset_id, kind="idle", subtype="idle_planted",
                target=res_id, is_positive=True, note="Planted idle server (CPU avg < 3, p95 < 8)"
            ))
        elif cat == "planted_underused":
            gt_records.append(GroundTruth(
                dataset_id=dataset_id, kind="underused", subtype="underused_planted",
                target=res_id, is_positive=True, note="Planted underused server (CPU p95 10-18, Mem p95 10-18)"
            ))
        elif cat in ("bursty", "batch", "dr", "normal"):
            gt_records.append(GroundTruth(
                dataset_id=dataset_id, kind="hard_negative", subtype=cat,
                target=res_id, is_positive=False, note=f"Hard negative: {cat} workload"
            ))

    # Event ground truth
    for ev in anomaly_events:
        st_date = date_list[min(ev["start_day"], days_count - 1)]
        en_date = date_list[min(ev["end_day"], days_count - 1)]
        gt_records.append(GroundTruth(
            dataset_id=dataset_id,
            kind=ev["kind"],
            subtype=ev["subtype"],
            target=ev["target"],
            start_date=st_date,
            end_date=en_date,
            is_positive=ev["is_positive"],
            note=ev.get("note")
        ))

    # Create Dataset record
    ds = Dataset(
        id=dataset_id,
        name=dataset_name,
        kind="synthetic",
        seed=seed,
        notes=f"Synthetic ground-truth benchmark ({months} months daily, {num_resources} resources, seed {seed}).",
        created_at=datetime.datetime.utcnow()
    )
    db.add(ds)
    db.flush()

    for gt in gt_records:
        db.add(gt)

    # 3. Simulate Daily Utilization & Spend
    series_models: List[UtilizationSeries] = []
    summary_models: List[UtilizationSummary] = []
    line_item_models: List[CostLineItem] = []
    daily_spend_map: Dict[Tuple[datetime.date, str, str], float] = {}

    for r in resource_defs:
        res_id = r["resource_id"]
        svc = r["service_name"]
        reg = r["region_id"]
        cat = r["category"]
        env = r["tags"]["env"]
        m_type = r["machine_type"]

        # Base hourly price
        if m_type and m_type in price_table["machines"]:
            base_hourly = price_table["machines"][m_type]["hourly_price"]
        else:
            base_hourly = 0.08  # Default hourly equivalent for non-provisioned

        daily_cpu_list = []
        daily_mem_list = []

        # Generate utilization series
        for d_idx, d in enumerate(date_list):
            if cat == "planted_idle":
                cpu = float(np.clip(rng.normal(1.8, 0.4), 0.5, 4.5))
                mem = float(np.clip(rng.normal(12.0, 1.5), 5.0, 18.0))
            elif cat == "planted_underused":
                cpu = float(np.clip(rng.normal(12.0, 2.0), 8.0, 17.5))
                mem = float(np.clip(rng.normal(13.0, 2.0), 9.0, 17.5))
            elif cat == "bursty":
                if rng.random() < 0.08:
                    cpu = float(np.clip(rng.normal(75.0, 5.0), 65.0, 95.0))
                else:
                    cpu = float(np.clip(rng.normal(4.0, 1.0), 1.0, 7.0))
                mem = float(np.clip(rng.normal(40.0, 5.0), 25.0, 60.0))
            elif cat == "batch":
                if d_idx % 7 in (1, 2):
                    cpu = float(np.clip(rng.normal(65.0, 8.0), 45.0, 90.0))
                else:
                    cpu = float(np.clip(rng.normal(3.0, 0.8), 0.5, 6.0))
                mem = float(np.clip(rng.normal(30.0, 5.0), 15.0, 50.0))
            elif cat == "dr":
                cpu = float(np.clip(rng.normal(2.0, 0.5), 0.5, 4.5))
                mem = float(np.clip(rng.normal(10.0, 1.0), 5.0, 15.0))
            else:  # normal & non-provisioned
                cpu = float(np.clip(rng.normal(48.0, 8.0), 30.0, 75.0))
                mem = float(np.clip(rng.normal(52.0, 8.0), 32.0, 80.0))

            daily_cpu_list.append(cpu)
            daily_mem_list.append(mem)

            if r["service_class"] == "provisioned":
                p95_cpu = min(100.0, cpu * 1.25)
                p95_mem = min(100.0, mem * 1.15)
                series_models.append(UtilizationSeries(
                    dataset_id=dataset_id,
                    resource_id=res_id,
                    date=d,
                    cpu_avg=round(cpu, 2),
                    cpu_p95=round(p95_cpu, 2),
                    mem_avg=round(mem, 2),
                    mem_p95=round(p95_mem, 2),
                    net_in_bytes=float(rng.integers(10_000_000, 500_000_000)),
                    net_out_bytes=float(rng.integers(10_000_000, 500_000_000))
                ))

            # Daily cost simulation:
            noise = float(np.exp(rng.normal(0.0, 0.08)))
            weekend_mod = 0.8 if (d.weekday() >= 5 and env in ("dev", "test")) else 1.0

            anomaly_mod = 1.0
            for ev in anomaly_events:
                if ev["target"] == svc and ev["start_day"] <= d_idx <= ev["end_day"]:
                    if "multiplier" in ev:
                        anomaly_mod *= ev["multiplier"]
                    elif "drift_rate" in ev:
                        drift_days = d_idx - ev["start_day"]
                        anomaly_mod *= (1.0 + ev["drift_rate"] * drift_days)

            day_cost = round(24.0 * base_hourly * noise * weekend_mod * anomaly_mod, 4)

            st_dt = datetime.datetime.combine(d, datetime.time.min)
            en_dt = datetime.datetime.combine(d, datetime.time.max)
            line_item_models.append(CostLineItem(
                dataset_id=dataset_id,
                resource_id=res_id,
                service_name=svc,
                region_id=reg,
                consumed_quantity=24.0,
                consumed_unit="Hours",
                unit_price=round(base_hourly, 4),
                billed_cost=day_cost,
                charge_period_start=st_dt,
                charge_period_end=en_dt
            ))

            key = (d, svc, reg)
            daily_spend_map[key] = daily_spend_map.get(key, 0.0) + day_cost

        # Build utilization summary
        cpu_arr = np.array(daily_cpu_list)
        mem_arr = np.array(daily_mem_list)
        cpu_mean = float(np.mean(cpu_arr))
        cpu_std = float(np.std(cpu_arr))
        cpu_cv = round(cpu_std / cpu_mean, 4) if cpu_mean > 0 else 0.0

        summary_models.append(UtilizationSummary(
            dataset_id=dataset_id,
            resource_id=res_id,
            data_quality="series" if r["service_class"] == "provisioned" else "snapshot",
            cpu_latest=round(daily_cpu_list[-1], 2),
            cpu_avg=round(cpu_mean, 2),
            cpu_p95=round(float(np.percentile(cpu_arr, 95)), 2),
            mem_latest=round(daily_mem_list[-1], 2),
            mem_avg=round(float(np.mean(mem_arr)), 2),
            mem_p95=round(float(np.percentile(mem_arr, 95)), 2),
            cpu_cv=cpu_cv,
            window_days=days_count
        ))

        # Add Resource model
        db.add(Resource(
            dataset_id=dataset_id,
            resource_id=res_id,
            service_name=svc,
            service_class=r["service_class"],
            region_id=reg,
            machine_type=m_type,
            tags=r["tags"],
            is_prod=r["is_prod"]
        ))

    db.bulk_save_objects(summary_models)
    db.bulk_save_objects(series_models)
    db.bulk_save_objects(line_item_models)

    # Save real daily spend
    daily_models = [
        DailySpend(
            dataset_id=dataset_id,
            date=k[0],
            service_name=k[1],
            region_id=k[2],
            billed_cost=round(v, 4),
            is_derived=False
        ) for k, v in daily_spend_map.items()
    ]
    db.bulk_save_objects(daily_models)

    db.commit()
    return dataset_id


if __name__ == "__main__":
    import argparse
    from app.db import init_db, SessionLocal

    init_db()
    parser = argparse.ArgumentParser(description="Generate synthetic GCP billing data")
    parser.add_argument("--seed", type=int, default=1, help="Random seed")
    parser.add_argument("--months", type=int, default=12, help="Number of months")
    parser.add_argument("--resources", type=int, default=300, help="Number of resources")
    parser.add_argument("--start", type=str, default="2025-01-01", help="Start date YYYY-MM-DD")
    parser.add_argument("--anomaly-rate", type=float, default=0.05, help="Anomaly rate")
    args = parser.parse_args()

    with SessionLocal() as db_sess:
        created_id = generate_synthetic_dataset(
            db=db_sess,
            seed=args.seed,
            months=args.months,
            num_resources=args.resources,
            start_date_str=args.start,
            anomaly_rate=args.anomaly_rate
        )
        print(f"Generated synthetic dataset: {created_id}")

