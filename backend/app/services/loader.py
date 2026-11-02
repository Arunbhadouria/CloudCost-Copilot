"""CSV Billing Data Loader and Daily Spend Generator for GCP export files."""
import io
import uuid
import datetime
from typing import Dict, Any, List, Optional, Union
import pandas as pd
from sqlalchemy.orm import Session

from app.models import (
    Dataset, Resource, CostLineItem, DailySpend,
    UtilizationSummary, DataWarning
)
from app.services.classify import get_service_class
from app.services.quality import validate_billing_record, detect_mixed_units


def parse_csv_billing_data(
    file_content: Union[str, bytes],
) -> pd.DataFrame:
    """Read CSV bytes or string into a DataFrame with day-first dates and mapped columns."""
    if isinstance(file_content, bytes):
        file_obj = io.BytesIO(file_content)
    else:
        file_obj = io.StringIO(file_content)

    df = pd.read_csv(file_obj)

    # Validate essential columns
    required_cols = [
        "Resource ID", "Service Name", "Region/Zone", "Usage Quantity",
        "Usage Unit", "Cost per Quantity ($)", "Unrounded Cost ($)",
        "Usage Start Date", "Usage End Date"
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing mandatory columns: {missing}")

    # Parse day-first dates strictly: %d-%m-%Y %H:%M
    df["charge_period_start"] = pd.to_datetime(
        df["Usage Start Date"], format="%d-%m-%Y %H:%M", errors="coerce"
    )
    df["charge_period_end"] = pd.to_datetime(
        df["Usage End Date"], format="%d-%m-%Y %H:%M", errors="coerce"
    )

    # Column mapping
    rename_map = {
        "Resource ID": "resource_id",
        "Service Name": "service_name",
        "Region/Zone": "region_id",
        "Usage Quantity": "consumed_quantity",
        "Usage Unit": "consumed_unit",
        "Cost per Quantity ($)": "unit_price",
        "Unrounded Cost ($)": "billed_cost",
        "CPU Utilization (%)": "cpu_util",
        "Memory Utilization (%)": "mem_util",
        "Network Inbound Data (Bytes)": "net_in_bytes",
        "Network Outbound Data (Bytes)": "net_out_bytes",
    }
    df = df.rename(columns=rename_map)

    # Clean floats
    df["consumed_quantity"] = pd.to_numeric(df["consumed_quantity"], errors="coerce").fillna(0.0)
    df["unit_price"] = pd.to_numeric(df["unit_price"], errors="coerce").fillna(0.0)
    df["billed_cost"] = pd.to_numeric(df["billed_cost"], errors="coerce").fillna(0.0)
    if "cpu_util" in df.columns:
        df["cpu_util"] = pd.to_numeric(df["cpu_util"], errors="coerce")
    if "mem_util" in df.columns:
        df["mem_util"] = pd.to_numeric(df["mem_util"], errors="coerce")

    # Drop non-essential / redundant columns as specified in section 7.1
    for col in ["Rounded Cost ($)", "Total Cost (INR)", "Usage Start Date", "Usage End Date"]:
        if col in df.columns:
            df = df.drop(columns=[col])

    return df


def calculate_daily_spend_proportional(
    valid_rows: List[Dict[str, Any]],
    dataset_id: str
) -> List[Dict[str, Any]]:
    """Apportion line item costs proportionally across overlapping calendar days."""
    daily_aggregates: Dict[tuple, float] = {}

    for row in valid_rows:
        start: datetime.datetime = row["charge_period_start"]
        end: datetime.datetime = row["charge_period_end"]
        total_cost: float = float(row["billed_cost"])
        service_name: str = row["service_name"]
        region_id: str = row["region_id"]

        total_seconds = (end - start).total_seconds()
        if total_seconds <= 0:
            total_seconds = 3600.0  # minimal 1 hour

        current_day = start.date()
        end_day = end.date()

        while current_day <= end_day:
            day_start = max(start, datetime.datetime.combine(current_day, datetime.time.min))
            day_end = min(end, datetime.datetime.combine(current_day, datetime.time.max))

            day_seconds = max(0.0, (day_end - day_start).total_seconds())
            if day_seconds > 0:
                day_fraction = day_seconds / total_seconds
                day_cost = total_cost * day_fraction

                key = (current_day, service_name, region_id)
                daily_aggregates[key] = daily_aggregates.get(key, 0.0) + day_cost

            current_day += datetime.timedelta(days=1)

    spend_items = []
    for (d, svc, reg), cost in daily_aggregates.items():
        spend_items.append({
            "dataset_id": dataset_id,
            "date": d,
            "service_name": svc,
            "region_id": reg,
            "billed_cost": round(cost, 4),
            "is_derived": True
        })
    return spend_items


def load_csv_dataset(
    db: Session,
    file_content: Union[str, bytes],
    dataset_name: str = "Real-format GCP billing sample",
    dataset_id: Optional[str] = None
) -> Dict[str, Any]:
    """Ingest CSV, apply quality gate, store line items, resources, summaries, and daily spend."""
    if not dataset_id:
        dataset_id = f"csv-{uuid.uuid4().hex[:8]}"

    df = parse_csv_billing_data(file_content)

    valid_rows: List[Dict[str, Any]] = []
    quarantined_warnings: List[DataWarning] = []

    for _, row in df.iterrows():
        row_dict = row.to_dict()
        cpu = row_dict.get("cpu_util")
        mem = row_dict.get("mem_util")
        cpu_val = float(cpu) if pd.notnull(cpu) else None
        mem_val = float(mem) if pd.notnull(mem) else None

        start_dt = row_dict.get("charge_period_start")
        end_dt = row_dict.get("charge_period_end")

        if pd.isnull(start_dt) or pd.isnull(end_dt):
            quarantined_warnings.append(DataWarning(
                dataset_id=dataset_id,
                kind="quarantined_row",
                resource_id=str(row_dict.get("resource_id")),
                detail={"reason": "Invalid or unparseable date format"}
            ))
            continue

        is_valid, kind, detail = validate_billing_record(
            consumed_quantity=float(row_dict["consumed_quantity"]),
            unit_price=float(row_dict["unit_price"]),
            billed_cost=float(row_dict["billed_cost"]),
            charge_period_start=start_dt,
            charge_period_end=end_dt,
            cpu_util=cpu_val,
            mem_util=mem_val
        )

        if not is_valid:
            quarantined_warnings.append(DataWarning(
                dataset_id=dataset_id,
                kind=kind or "quarantined_row",
                resource_id=str(row_dict.get("resource_id")),
                detail=detail or {}
            ))
        else:
            valid_rows.append(row_dict)

    # Mixed unit detection across all valid rows
    mixed_warnings_raw = detect_mixed_units(valid_rows)
    mixed_warnings = [
        DataWarning(
            dataset_id=dataset_id,
            kind=w["kind"],
            resource_id=w["resource_id"],
            detail=w["detail"]
        ) for w in mixed_warnings_raw
    ]

    # Create Dataset record
    ds_record = Dataset(
        id=dataset_id,
        name=dataset_name,
        kind="csv",
        seed=None,
        notes="A real-format GCP billing export sample (qualitative demo only, 1000 rows).",
        created_at=datetime.datetime.utcnow()
    )
    db.add(ds_record)
    db.flush()

    # Save Data Warnings
    for w in quarantined_warnings + mixed_warnings:
        db.add(w)

    # Process valid resources & line items
    resource_map: Dict[str, Resource] = {}
    line_item_models: List[CostLineItem] = []
    summary_models: List[UtilizationSummary] = []

    min_date: Optional[datetime.datetime] = None
    max_date: Optional[datetime.datetime] = None

    for r in valid_rows:
        res_id = str(r["resource_id"])
        svc_name = str(r["service_name"])
        reg_id = str(r["region_id"])
        start = r["charge_period_start"]
        end = r["charge_period_end"]

        if min_date is None or start < min_date:
            min_date = start
        if max_date is None or end > max_date:
            max_date = end

        if res_id not in resource_map:
            res_obj = Resource(
                dataset_id=dataset_id,
                resource_id=res_id,
                service_name=svc_name,
                service_class=get_service_class(svc_name),
                region_id=reg_id,
                machine_type=None,
                tags={},
                is_prod=False
            )
            resource_map[res_id] = res_obj
            db.add(res_obj)

            cpu = float(r["cpu_util"]) if pd.notnull(r.get("cpu_util")) else 0.0
            mem = float(r.get("mem_util")) if pd.notnull(r.get("mem_util")) else 0.0
            window_days = max(1, (end.date() - start.date()).days + 1)

            summary_models.append(UtilizationSummary(
                dataset_id=dataset_id,
                resource_id=res_id,
                data_quality="snapshot",
                cpu_latest=cpu,
                cpu_avg=cpu,
                cpu_p95=None,
                mem_latest=mem,
                mem_avg=mem,
                mem_p95=None,
                cpu_cv=None,
                window_days=window_days
            ))

        line_item_models.append(CostLineItem(
            dataset_id=dataset_id,
            resource_id=res_id,
            service_name=svc_name,
            region_id=reg_id,
            consumed_quantity=float(r["consumed_quantity"]),
            consumed_unit=str(r["consumed_unit"]),
            unit_price=float(r["unit_price"]),
            billed_cost=float(r["billed_cost"]),
            charge_period_start=start,
            charge_period_end=end
        ))

    db.bulk_save_objects(line_item_models)
    db.bulk_save_objects(summary_models)

    # Compute & save daily spend
    daily_spends = calculate_daily_spend_proportional(valid_rows, dataset_id)
    daily_models = [DailySpend(**item) for item in daily_spends]
    db.bulk_save_objects(daily_models)

    db.commit()

    return {
        "dataset_id": dataset_id,
        "rows_loaded": len(valid_rows),
        "rows_quarantined": len(quarantined_warnings),
        "warnings": len(quarantined_warnings) + len(mixed_warnings),
        "date_range": {
            "start": min_date.strftime("%Y-%m-%d") if min_date else None,
            "end": max_date.strftime("%Y-%m-%d") if max_date else None
        }
    }

