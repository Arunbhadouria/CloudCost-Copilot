"""Whitelisted parameterized SQL templates for the Copilot tools."""
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.models import DailySpend, Recommendation


GROUP_BY_ALLOWLIST = {
    "service": "service_name",
    "region": "region_id",
    "day": "date"
}


def execute_cost_query(
    db: Session,
    dataset_id: str,
    group_by: str = "service",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    service: Optional[str] = None,
    region: Optional[str] = None,
    limit: int = 20
) -> Dict[str, Any]:
    """Execute whitelisted cost aggregation query with precomputed shares and row limits."""
    col_name = GROUP_BY_ALLOWLIST.get(group_by.lower(), "service_name")
    limit = min(50, max(1, limit))

    where_clauses = ["dataset_id = :dataset_id"]
    params: Dict[str, Any] = {"dataset_id": dataset_id, "limit": limit}

    if date_from:
        where_clauses.append("date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        where_clauses.append("date <= :date_to")
        params["date_to"] = date_to
    if service:
        where_clauses.append("service_name = :service")
        params["service"] = service
    if region:
        where_clauses.append("region_id = :region")
        params["region"] = region

    where_sql = " AND ".join(where_clauses)

    # Calculate total spend for precomputing share_pct
    total_sql = f"SELECT SUM(billed_cost) as total FROM daily_spend WHERE {where_sql}"
    total_res = db.execute(text(total_sql), params).scalar() or 0.0

    # Grouped query
    sql = f"""
    SELECT {col_name} AS dimension_key,
           ROUND(CAST(SUM(billed_cost) AS NUMERIC), 2) AS billed_cost
    FROM daily_spend
    WHERE {where_sql}
    GROUP BY {col_name}
    ORDER BY billed_cost DESC
    LIMIT :limit
    """

    cursor = db.execute(text(sql), params)
    rows = []
    for r in cursor.fetchall():
        cost = float(r.billed_cost or 0.0)
        share = round((cost / total_res * 100.0), 2) if total_res > 0 else 0.0
        key_str = r.dimension_key.strftime("%Y-%m-%d") if isinstance(r.dimension_key, (datetime.date, datetime.datetime)) else str(r.dimension_key)
        rows.append({
            group_by: key_str,
            "billed_cost": cost,
            "share_pct": share
        })

    # Return readable SQL representation for the "How was this worked out?" drawer
    display_sql = f"SELECT {col_name}, SUM(billed_cost) FROM daily_spend WHERE dataset_id = '{dataset_id}' GROUP BY {col_name} ORDER BY SUM(billed_cost) DESC LIMIT {limit};"

    return {"rows": rows, "sql": display_sql}


def execute_get_recommendation(
    db: Session,
    dataset_id: str,
    id: Optional[int] = None,
    top_n: Optional[int] = 5
) -> Dict[str, Any]:
    """Execute parameterized query to look up recommendations."""
    limit = min(50, max(1, top_n or 5))

    if id is not None:
        sql = """
        SELECT id, resource_id, service_name, type, savings_mid,
               savings_low, savings_high, savings_basis, savings_unit,
               confidence, effort, priority, reason, status
        FROM recommendations
        WHERE dataset_id = :dataset_id AND id = :id
        """
        cursor = db.execute(text(sql), {"dataset_id": dataset_id, "id": id})
        display_sql = f"SELECT * FROM recommendations WHERE dataset_id = '{dataset_id}' AND id = {id};"
    else:
        sql = """
        SELECT id, resource_id, service_name, type, savings_mid,
               savings_low, savings_high, savings_basis, savings_unit,
               confidence, effort, priority, reason, status
        FROM recommendations
        WHERE dataset_id = :dataset_id AND status != 'dismissed'
        ORDER BY priority DESC
        LIMIT :limit
        """
        cursor = db.execute(text(sql), {"dataset_id": dataset_id, "limit": limit})
        display_sql = f"SELECT * FROM recommendations WHERE dataset_id = '{dataset_id}' AND status != 'dismissed' ORDER BY priority DESC LIMIT {limit};"

    rows = []
    for r in cursor.fetchall():
        rows.append({
            "id": r.id,
            "resource_id": r.resource_id,
            "service_name": r.service_name,
            "finding_type": r.type,
            "possible_savings": float(r.savings_mid),
            "savings_range": f"${r.savings_low:.0f} - ${r.savings_high:.0f}",
            "basis": r.savings_basis,
            "unit": r.savings_unit,
            "reason": r.reason[:80]
        })

    return {"rows": rows, "sql": display_sql}


def execute_compare_periods(
    db: Session,
    dataset_id: str,
    period_a_start: str,
    period_a_end: str,
    period_b_start: str,
    period_b_end: str,
    group_by: str = "service"
) -> Dict[str, Any]:
    """Compare total and grouped costs between two time windows."""
    col_name = GROUP_BY_ALLOWLIST.get(group_by.lower(), "service_name")

    sql_a = f"""
    SELECT {col_name} AS dim_key, SUM(billed_cost) AS cost
    FROM daily_spend
    WHERE dataset_id = :dataset_id AND date >= :st_a AND date <= :en_a
    GROUP BY {col_name}
    """
    sql_b = f"""
    SELECT {col_name} AS dim_key, SUM(billed_cost) AS cost
    FROM daily_spend
    WHERE dataset_id = :dataset_id AND date >= :st_b AND date <= :en_b
    GROUP BY {col_name}
    """

    res_a = dict(db.execute(text(sql_a), {"dataset_id": dataset_id, "st_a": period_a_start, "en_a": period_a_end}).fetchall())
    res_b = dict(db.execute(text(sql_b), {"dataset_id": dataset_id, "st_b": period_b_start, "en_b": period_b_end}).fetchall())

    all_keys = set(res_a.keys()) | set(res_b.keys())
    rows = []
    for k in sorted(all_keys):
        c_a = round(float(res_a.get(k, 0.0)), 2)
        c_b = round(float(res_b.get(k, 0.0)), 2)
        delta_usd = round(c_b - c_a, 2)
        delta_pct = round((delta_usd / (c_a + 1e-6)) * 100.0, 1) if c_a > 0 else 0.0
        rows.append({
            group_by: str(k),
            "period_a_usd": c_a,
            "period_b_usd": c_b,
            "delta_usd": delta_usd,
            "delta_pct": delta_pct
        })

    display_sql = f"SELECT {col_name}, SUM(billed_cost) FROM daily_spend WHERE dataset_id = '{dataset_id}' AND date BETWEEN '{period_a_start}' AND '{period_b_end}' GROUP BY {col_name};"
    return {"rows": rows[:50], "sql": display_sql}

