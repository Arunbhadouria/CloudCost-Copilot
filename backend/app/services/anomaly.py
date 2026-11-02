"""Anomaly detection for cloud spending using STL decomposition and Isolation Forest."""
import datetime
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func
from statsmodels.tsa.seasonal import STL
from sklearn.ensemble import IsolationForest

from app.models import DailySpend, Anomaly, Dataset, Resource, UtilizationSummary, CostLineItem


def detect_isolation_forest_anomalies(
    db: Session,
    dataset_id: str,
    contamination: float = 0.05
) -> List[Anomaly]:
    """Detect multivariate resource anomalies (e.g. high spend with near-zero utilization) via Isolation Forest."""
    # Query resource telemetry joined with billed cost
    cost_subq = db.query(
        CostLineItem.resource_id,
        func.sum(CostLineItem.billed_cost).label("total_cost"),
        func.min(CostLineItem.charge_period_start).label("min_start"),
        func.max(CostLineItem.charge_period_end).label("max_end")
    ).filter(CostLineItem.dataset_id == dataset_id).group_by(CostLineItem.resource_id).subquery()

    rows = db.query(
        Resource.resource_id,
        Resource.service_name,
        cost_subq.c.total_cost,
        cost_subq.c.min_start,
        cost_subq.c.max_end,
        UtilizationSummary.cpu_avg,
        UtilizationSummary.cpu_p95,
        UtilizationSummary.mem_avg,
        UtilizationSummary.cpu_cv
    ).join(
        cost_subq, Resource.resource_id == cost_subq.c.resource_id
    ).outerjoin(
        UtilizationSummary,
        (Resource.resource_id == UtilizationSummary.resource_id) & (Resource.dataset_id == UtilizationSummary.dataset_id)
    ).filter(Resource.dataset_id == dataset_id).all()

    if len(rows) < 8:
        return []

    data = []
    metadata = []
    for r in rows:
        cost = float(r.total_cost or 0.0)
        cpu_avg = float(r.cpu_avg or 50.0)
        cpu_p95 = float(r.cpu_p95 or 50.0)
        mem_avg = float(r.mem_avg or 50.0)
        cpu_cv = float(r.cpu_cv or 0.0)
        data.append([np.log1p(cost), cpu_avg, cpu_p95, mem_avg, cpu_cv])
        metadata.append(r)

    X = np.array(data, dtype=float)
    if X.shape[0] < 8:
        return []

    try:
        clf = IsolationForest(contamination=contamination, random_state=42)
        preds = clf.fit_predict(X)
        scores = -clf.decision_function(X)  # higher = more anomalous
    except Exception:
        return []

    if_anomalies: List[Anomaly] = []
    for idx, (pred, score) in enumerate(zip(preds, scores)):
        if pred == -1:  # Outlier detected
            r = metadata[idx]
            cost = float(r.total_cost or 0.0)
            cpu_avg = float(r.cpu_avg or 50.0)

            # Focus on meaningful dollar anomalies
            if cost < 50.0:
                continue

            if cpu_avg < 10.0:
                reason = f"High spend (${cost:,.2f}) with dormant CPU utilization ({cpu_avg:.1f}%)"
            elif float(r.cpu_cv or 0.0) > 1.2:
                reason = f"Extreme utilization volatility with anomalous cost footprint (${cost:,.2f})"
            else:
                reason = f"Multivariate outlier: atypical cost-to-utilization distribution"

            st_date = r.min_start.date() if hasattr(r.min_start, 'date') else datetime.date.today()
            en_date = r.max_end.date() if hasattr(r.max_end, 'date') else datetime.date.today()

            norm_score = round(float(np.clip(score * 10.0, 3.0, 6.0)), 2)
            severity = "high" if cost > 400.0 or norm_score >= 4.5 else "medium"

            if_anomalies.append(Anomaly(
                dataset_id=dataset_id,
                start_date=st_date,
                end_date=en_date,
                service_name=r.service_name,
                expected=round(max(0.0, cost * 0.25), 2),
                actual=round(cost, 2),
                peak_zscore=norm_score,
                severity=severity,
                explained_by=[{
                    "method": "isolation_forest",
                    "resource_id": r.resource_id,
                    "reason": reason,
                    "score": round(float(score), 3)
                }]
            ))

    return if_anomalies


def detect_anomalies_for_dataset(
    db: Session,
    dataset_id: str,
    threshold: float = 3.5,
    min_history_days: int = 56
) -> List[Anomaly]:
    """Detect cost jumps per service using STL decomposition (period 7) and Isolation Forest.

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

    # 1. STL Decomposition for 1D spend jumps
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
        df = df.resample("D").sum().fillna(0.0)

        if len(df) < min_history_days:
            continue

        try:
            stl = STL(df["cost"], period=7, robust=True)
            res = stl.fit()
        except Exception:
            continue

        trend = res.trend
        seasonal = res.seasonal
        residuals = res.resid

        med_resid = float(np.median(residuals))
        mad = float(np.median(np.abs(residuals - med_resid)))
        scale = 1.4826 * mad if mad > 1e-4 else float(np.std(residuals))
        if scale < 1e-4:
            scale = 1.0

        z_scores = (residuals - med_resid) / scale
        flagged_mask = (z_scores > threshold).values
        expected_series = (trend + seasonal).clip(lower=0.0).values
        actual_series = df["cost"].values
        index_dates = df.index.date

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
                    explained_by=[{
                        "method": "stl_decomposition",
                        "type": "cost_spike",
                        "peak_zscore": round(peak_z, 2)
                    }]
                )
                detected_anomalies.append(anom)
            else:
                i += 1

    # 2. Isolation Forest for multi-dimensional resource anomalies
    if_anomalies = detect_isolation_forest_anomalies(db, dataset_id)
    detected_anomalies.extend(if_anomalies)

    db.bulk_save_objects(detected_anomalies)
    db.commit()

    return detected_anomalies
