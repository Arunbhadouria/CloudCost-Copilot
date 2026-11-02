"""Future spend projection and budget forecasting using seasonal time series models."""
import datetime
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from app.models import DailySpend, CostLineItem, Dataset


def generate_cost_forecast(
    db: Session,
    dataset_id: str,
    forecast_days: int = 30,
    service_name: Optional[str] = None
) -> Dict[str, Any]:
    """Project future cloud spend for the next N days using seasonal time-series models.

    Computes expected spend along with 95% confidence intervals (optimistic and pessimistic bounds).
    """
    forecast_days = max(7, min(forecast_days, 90))

    # Query daily historical spend
    query = db.query(
        DailySpend.date,
        func.sum(DailySpend.billed_cost).label("cost")
    ).filter(DailySpend.dataset_id == dataset_id)

    if service_name:
        query = query.filter(DailySpend.service_name == service_name)

    records = query.group_by(DailySpend.date).order_by(DailySpend.date.asc()).all()

    # Fallback to CostLineItem if DailySpend is empty
    if not records:
        li_query = db.query(
            func.date(CostLineItem.charge_period_start).label("date"),
            func.sum(CostLineItem.billed_cost).label("cost")
        ).filter(CostLineItem.dataset_id == dataset_id)

        if service_name:
            li_query = li_query.filter(CostLineItem.service_name == service_name)

        records = li_query.group_by(func.date(CostLineItem.charge_period_start)).order_by("date").all()

    if not records:
        today = datetime.date.today()
        empty_daily = [
            {
                "date": (today + datetime.timedelta(days=i)).isoformat(),
                "expected": 0.0,
                "lower": 0.0,
                "upper": 0.0
            } for i in range(1, forecast_days + 1)
        ]
        return {
            "dataset_id": dataset_id,
            "forecast_days": forecast_days,
            "historical_days": 0,
            "current_run_rate_monthly": 0.0,
            "projected_next_month_spend": 0.0,
            "projected_growth_pct": 0.0,
            "lower_bound_monthly": 0.0,
            "upper_bound_monthly": 0.0,
            "daily_forecast": empty_daily
        }

    dates = [r.date if isinstance(r.date, datetime.date) else datetime.datetime.strptime(str(r.date)[:10], "%Y-%m-%d").date() for r in records]
    costs = [float(r.cost) for r in records]

    df = pd.DataFrame({"cost": costs}, index=pd.to_datetime(dates))
    df = df.resample("D").sum().fillna(0.0)

    historical_days = len(df)
    last_date = df.index[-1].date()
    recent_30_days = df["cost"].iloc[-30:].sum() if historical_days >= 30 else df["cost"].sum() * (30.0 / max(1, historical_days))

    # Time series forecasting
    predictions: List[float] = []
    lower_bounds: List[float] = []
    upper_bounds: List[float] = []

    if historical_days >= 14:
        try:
            # Holt-Winters additive trend with 7-day weekly seasonality
            model = ExponentialSmoothing(
                df["cost"].values,
                trend="add",
                seasonal="add",
                seasonal_periods=7,
                initialization_method="estimated"
            )
            fit_res = model.fit(smoothing_level=0.3, smoothing_trend=0.1, smoothing_seasonal=0.2)
            preds = fit_res.forecast(forecast_days)
            residuals = df["cost"].values - fit_res.fittedvalues
            std_err = float(np.std(residuals)) if len(residuals) > 0 else float(np.std(df["cost"]))
            if std_err < 1.0:
                std_err = float(np.mean(df["cost"])) * 0.1

            for step, pred in enumerate(preds, 1):
                val = max(0.0, float(pred))
                uncertainty = 1.96 * std_err * np.sqrt(1.0 + (step / 7.0) * 0.1)
                predictions.append(round(val, 2))
                lower_bounds.append(round(max(0.0, val - uncertainty), 2))
                upper_bounds.append(round(val + uncertainty, 2))
        except Exception:
            predictions = []

    # Fallback to linear trend with day-of-week modulation if Holt-Winters is unavailable
    if not predictions:
        x = np.arange(historical_days)
        y = df["cost"].values
        slope, intercept = np.polyfit(x, y, 1) if historical_days >= 2 else (0.0, float(np.mean(y)))
        residuals = y - (slope * x + intercept)
        std_err = float(np.std(residuals)) if len(residuals) > 0 else float(np.mean(y)) * 0.15

        dow_means = df.groupby(df.index.dayofweek)["cost"].mean().to_dict()
        overall_mean = float(np.mean(y)) if np.mean(y) > 0 else 1.0

        for step in range(1, forecast_days + 1):
            target_date = last_date + datetime.timedelta(days=step)
            base_trend = max(0.0, intercept + slope * (historical_days + step))
            dow_factor = (dow_means.get(target_date.weekday(), overall_mean) / overall_mean) if overall_mean > 0 else 1.0
            val = max(0.0, base_trend * dow_factor)
            uncertainty = 1.96 * std_err * np.sqrt(1.0 + (step / 14.0))

            predictions.append(round(val, 2))
            lower_bounds.append(round(max(0.0, val - uncertainty), 2))
            upper_bounds.append(round(val + uncertainty, 2))

    daily_forecast: List[Dict[str, Any]] = []
    for step in range(1, forecast_days + 1):
        target_date = last_date + datetime.timedelta(days=step)
        daily_forecast.append({
            "date": target_date.isoformat(),
            "expected": predictions[step - 1],
            "lower": lower_bounds[step - 1],
            "upper": upper_bounds[step - 1]
        })

    projected_next_month = sum(predictions[:30])
    lower_bound_month = sum(lower_bounds[:30])
    upper_bound_month = sum(upper_bounds[:30])

    growth_pct = 0.0
    if recent_30_days > 0:
        growth_pct = round(((projected_next_month - recent_30_days) / recent_30_days) * 100.0, 1)

    return {
        "dataset_id": dataset_id,
        "forecast_days": forecast_days,
        "historical_days": historical_days,
        "current_run_rate_monthly": round(float(recent_30_days), 2),
        "projected_next_month_spend": round(float(projected_next_month), 2),
        "projected_growth_pct": growth_pct,
        "lower_bound_monthly": round(float(lower_bound_month), 2),
        "upper_bound_monthly": round(float(upper_bound_month), 2),
        "daily_forecast": daily_forecast
    }
