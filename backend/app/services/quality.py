"""Quality gate and validation rules for cloud billing ingestion."""
from typing import Dict, Any, Tuple, Optional, List
import pandas as pd


def validate_billing_record(
    consumed_quantity: float,
    unit_price: float,
    billed_cost: float,
    charge_period_start: Any,
    charge_period_end: Any,
    cpu_util: Optional[float] = None,
    mem_util: Optional[float] = None,
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """Validate a single billing record against quality gate thresholds.

    Returns:
        (is_valid, failure_kind, detail_dict)
    """
    # 1. Negative cost check
    if billed_cost < 0:
        return False, "quarantined_row", {
            "reason": "Negative billed cost",
            "billed_cost": billed_cost
        }

    # 2. Math reconciliation tolerance: abs(quantity * unit_price - billed_cost) > 0.01
    expected_cost = consumed_quantity * unit_price
    cost_diff = abs(expected_cost - billed_cost)
    if cost_diff > 0.01:
        return False, "quarantined_row", {
            "reason": "Math reconciliation discrepancy exceeded $0.01 tolerance",
            "consumed_quantity": consumed_quantity,
            "unit_price": unit_price,
            "billed_cost": billed_cost,
            "expected_cost": round(expected_cost, 4),
            "discrepancy": round(cost_diff, 4)
        }

    # 3. Timeline check: end must be >= start
    if charge_period_end < charge_period_start:
        return False, "quarantined_row", {
            "reason": "Charge period end precedes start date",
            "start": str(charge_period_start),
            "end": str(charge_period_end)
        }

    # 4. Utilization range check: 0 to 100%
    if cpu_util is not None and (cpu_util < 0.0 or cpu_util > 100.0):
        return False, "quarantined_row", {
            "reason": "CPU utilization outside valid 0-100% range",
            "cpu_util": cpu_util
        }

    if mem_util is not None and (mem_util < 0.0 or mem_util > 100.0):
        return False, "quarantined_row", {
            "reason": "Memory utilization outside valid 0-100% range",
            "mem_util": mem_util
        }

    return True, None, None


def detect_mixed_units(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Detect services that report usage under multiple distinct units."""
    units_by_service: Dict[str, set] = {}
    for r in records:
        svc = r.get("service_name")
        unit = r.get("consumed_unit")
        if svc and unit:
            if svc not in units_by_service:
                units_by_service[svc] = set()
            units_by_service[svc].add(unit)

    warnings = []
    for svc, units in units_by_service.items():
        if len(units) > 1:
            warnings.append({
                "kind": "mixed_units",
                "resource_id": None,
                "detail": {
                    "service_name": svc,
                    "units": sorted(list(units)),
                    "message": f"Service '{svc}' uses multiple units: {', '.join(sorted(units))}"
                }
            })
    return warnings

