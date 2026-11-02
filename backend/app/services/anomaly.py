"""Anomaly detection for daily cloud spending using STL decomposition and robust statistics."""
import datetime
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func
from statsmodels.tsa.seasonal import STL

from app.models import DailySpend, Anomaly, Dataset


def detect_anomalies_for_dataset(
    db: Session,
    dataset_id: str,
    threshold: float = 3.5,
    min_history_days: int = 56
) -> List[Anomaly]:
    """Detect cost jumps per service using STL decomposition (period 7) and robust z-scores.

    Requires at least 56 days of daily records. Datasets with insufficient history safely return [].
    """
    ds = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not ds:
        return []

    # Per section 7.5: CSV dataset has insufficient history and must not claim anomaly results
    if ds.kind == "csv":
        return []

    # Check date span
    date_count = db.query(func.count(func.distinct(DailySpend.date))).filter(
        DailySpend.dataset_id == dataset_id
    ).scalar() or 0

    if date_count < min_history_days:
        return []

    # Clean existing anomalies for dataset
    db.query(Anomaly).filter(Anomaly.dataset_id == dataset_id).delete()
    db.flush()

    services = db.query(func.distinct(DailySpend.service_name)).filter(
        DailySpend.dataset_id == dataset_id
    ).all()
    service_names = [s[0] for s in services if s[0]]

    detected_anomalies: List[Anomaly] = []

    for svc in service_names:
        records = db.query(
            DailySpend.date,
            func.sum(DailySpend.billed_cost).label("cost")
        ).filter(
            DailySpend.dataset_id == dataset_id,
            DailySpend.service_name == svc
        ).group_by(DailySpend.date).order_by(DailySpend.date.asc()).all()

        if len(records) < min_history_days:
            continue

        dates = [r.date for r in records]
        costs = [float(r.cost) for r in records]

        df = pd.DataFrame({"cost": costs}, index=pd.to_datetime(dates))
        # Resample to ensure unbroken daily frequency
        df = df.resample("D").sum().fillna(0.0)

        if len(df) < min_history_days:
            continue

        try:
            # STL decomposition with weekly period (7 days)
            stl = STL(df["cost"], period=7, robust=True)
            res = stl.fit()
        except Exception:
            continue

        trend = res.trend
        seasonal = res.seasonal
        residuals = res.resid

        # Robust z-scores using Median and MAD
        med_resid = float(np.median(residuals))
        mad = float(np.median(np.abs(residuals - med_resid)))
        scale = 1.4826 * mad if mad > 1e-4 else float(np.std(residuals))
        if scale < 1e-4:
            scale = 1.0

        z_scores = (residuals - med_resid) / scale

        # Flag days where cost jumped abnormally high
        flagged_mask = (z_scores > threshold).values
        expected_series = (trend + seasonal).clip(lower=0.0).values
        actual_series = df["cost"].values
        index_dates = df.index.date

        # Cluster consecutive flagged days into single anomaly events
        i = 0
        while i < len(flagged_mask):
            if flagged_mask[i]:
                start_idx = i
                while i < len(flagged_mask) and flagged_mask[i]:
                    i += 1
                end_idx = i - 1

                event_actual = float(np.sum(actual_series[start_idx : end_idx + 1]))
                event_expected = float(np.sum(expected_series[start_idx : end_idx + 1]))
                peak_z = float(np.max(z_scores.values[start_idx : end_idx + 1]))

                ratio = event_actual / (event_expected + 1e-6)

                # Severity classification
                if peak_z >= 5.0 or ratio >= 3.0:
                    severity = "high"
                elif peak_z >= 4.0 or ratio >= 1.5:
                    severity = "medium"
                else:
                    severity = "low"

                anom = Anomaly(
                    dataset_id=dataset_id,
                    start_date=index_dates[start_idx],
                    end_date=index_dates[end_idx],
                    service_name=svc,
                    expected=round(event_expected, 2),
                    actual=round(event_actual, 2),
                    peak_zscore=round(peak_z, 2),
                    severity=severity,
                    explained_by=None
                )
                detected_anomalies.append(anom)
            else:
                i += 1

    db.bulk_save_objects(detected_anomalies)
    db.commit()

    return detected_anomalies
