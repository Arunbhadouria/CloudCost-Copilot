"""Savings calculations for idle, underused, and weak-signal resources."""
import json
from pathlib import Path
from typing import Dict, Any, Optional
from app.config import settings

_PRICE_TABLE_CACHE: Optional[Dict[str, Any]] = None


def _get_price_table() -> Dict[str, Any]:
    global _PRICE_TABLE_CACHE
    if _PRICE_TABLE_CACHE is not None:
        return _PRICE_TABLE_CACHE
    price_path = settings.REFERENCE_DIR / "price_table.json"
    with open(price_path, "r", encoding="utf-8") as f:
        _PRICE_TABLE_CACHE = json.load(f)
    return _PRICE_TABLE_CACHE


def get_next_size_down(machine_type: Optional[str]) -> Optional[str]:
    """Look up the next size down machine type from price_table.json."""
    if not machine_type:
        return None
    price_table = _get_price_table()
    machines = price_table.get("machines", {})
    m_info = machines.get(machine_type)
    if m_info and "next_size_down" in m_info:
        return m_info["next_size_down"]
    return None


def calculate_savings(
    finding_type: str,
    dataset_kind: str,
    billed_cost: float,
    machine_type: Optional[str] = None
) -> Dict[str, Any]:
    """Calculate low, high, and mid savings estimates based on dataset kind and pricing rules.

    Returns:
        {
            "savings_low": float,
            "savings_high": float,
            "savings_mid": float,
            "savings_basis": "price_table" | "assumption",
            "savings_unit": "monthly" | "observed_window"
        }
    """
    if finding_type == "weak_signal":
        return {
            "savings_low": 0.0,
            "savings_high": 0.0,
            "savings_mid": 0.0,
            "savings_basis": "price_table" if dataset_kind == "synthetic" else "assumption",
            "savings_unit": "monthly" if dataset_kind == "synthetic" else "observed_window"
        }

    # Synthetic dataset path (Price table based, monthly run-rate x 730)
    if dataset_kind == "synthetic":
        price_table = _get_price_table()
        machines = price_table["machines"]

        m_info = machines.get(machine_type) if machine_type else None
        current_hourly = m_info["hourly_price"] if m_info else 0.10

        if finding_type == "idle":
            # Idle: full run-rate savings
            monthly = round(current_hourly * 730.0, 2)
            return {
                "savings_low": monthly,
                "savings_high": monthly,
                "savings_mid": monthly,
                "savings_basis": "price_table",
                "savings_unit": "monthly"
            }

        elif finding_type == "underused":
            # Underused: resize down using next_size_down
            next_name = m_info.get("next_size_down") if m_info else None
            if next_name and next_name in machines:
                next_hourly = machines[next_name]["hourly_price"]
                delta = current_hourly - next_hourly
                monthly = round(delta * 730.0, 2)
            else:
                # Fallback downsizing 50%
                monthly = round((current_hourly * 0.5) * 730.0, 2)

            return {
                "savings_low": monthly,
                "savings_high": monthly,
                "savings_mid": monthly,
                "savings_basis": "price_table",
                "savings_unit": "monthly"
            }

    # CSV dataset path (Ranges on observed window, assumption basis)
    else:
        if finding_type == "idle":
            low = round(0.90 * billed_cost, 2)
            high = round(1.00 * billed_cost, 2)
            mid = round(0.95 * billed_cost, 2)
            return {
                "savings_low": low,
                "savings_high": high,
                "savings_mid": mid,
                "savings_basis": "assumption",
                "savings_unit": "observed_window"
            }

        elif finding_type == "underused":
            low = round(0.30 * billed_cost, 2)
            high = round(0.50 * billed_cost, 2)
            mid = round(0.40 * billed_cost, 2)
            return {
                "savings_low": low,
                "savings_high": high,
                "savings_mid": mid,
                "savings_basis": "assumption",
                "savings_unit": "observed_window"
            }

    return {
        "savings_low": 0.0,
        "savings_high": 0.0,
        "savings_mid": 0.0,
        "savings_basis": "assumption",
        "savings_unit": "observed_window"
    }
