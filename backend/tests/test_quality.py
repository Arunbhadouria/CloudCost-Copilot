"""Unit tests for the ingestion quality gate and validation rules."""
import datetime
from app.services.quality import validate_billing_record, detect_mixed_units


def test_quality_gate_passes_clean_row():
    """Clean record should pass with no quarantine."""
    start = datetime.datetime(2024, 7, 1, 10, 0)
    end = datetime.datetime(2024, 7, 3, 10, 0)
    is_valid, kind, detail = validate_billing_record(
        consumed_quantity=100.0,
        unit_price=0.05,
        billed_cost=5.00,
        charge_period_start=start,
        charge_period_end=end,
        cpu_util=45.0,
        mem_util=55.0
    )
    assert is_valid is True
    assert kind is None
    assert detail is None


def test_quality_gate_quarantines_math_discrepancy():
    """Cost math mismatch > $0.01 tolerance must be quarantined."""
    start = datetime.datetime(2024, 7, 1, 10, 0)
    end = datetime.datetime(2024, 7, 3, 10, 0)
    # 100 * 0.05 = 5.00, but billed is 6.50
    is_valid, kind, detail = validate_billing_record(
        consumed_quantity=100.0,
        unit_price=0.05,
        billed_cost=6.50,
        charge_period_start=start,
        charge_period_end=end,
    )
    assert is_valid is False
    assert kind == "quarantined_row"
    assert "discrepancy" in detail


def test_quality_gate_quarantines_reversed_dates():
    """End date before start date must be quarantined."""
    start = datetime.datetime(2024, 7, 5, 10, 0)
    end = datetime.datetime(2024, 7, 1, 10, 0)
    is_valid, kind, detail = validate_billing_record(
        consumed_quantity=10.0,
        unit_price=1.0,
        billed_cost=10.0,
        charge_period_start=start,
        charge_period_end=end,
    )
    assert is_valid is False
    assert kind == "quarantined_row"
    assert "precedes" in detail["reason"]


def test_quality_gate_quarantines_invalid_utilization():
    """Utilization < 0 or > 100 must be quarantined."""
    start = datetime.datetime(2024, 7, 1, 10, 0)
    end = datetime.datetime(2024, 7, 2, 10, 0)

    # CPU > 100
    is_valid, kind, _ = validate_billing_record(
        consumed_quantity=10.0, unit_price=1.0, billed_cost=10.0,
        charge_period_start=start, charge_period_end=end,
        cpu_util=105.0, mem_util=50.0
    )
    assert is_valid is False
    assert kind == "quarantined_row"

    # Mem < 0
    is_valid, kind, _ = validate_billing_record(
        consumed_quantity=10.0, unit_price=1.0, billed_cost=10.0,
        charge_period_start=start, charge_period_end=end,
        cpu_util=50.0, mem_util=-5.0
    )
    assert is_valid is False
    assert kind == "quarantined_row"


def test_quality_gate_quarantines_negative_cost():
    """Negative billed cost must be quarantined."""
    start = datetime.datetime(2024, 7, 1, 10, 0)
    end = datetime.datetime(2024, 7, 2, 10, 0)
    is_valid, kind, _ = validate_billing_record(
        consumed_quantity=-10.0, unit_price=1.0, billed_cost=-10.0,
        charge_period_start=start, charge_period_end=end
    )
    assert is_valid is False
    assert kind == "quarantined_row"


def test_mixed_units_detection():
    """Detect services using multiple distinct usage units."""
    records = [
        {"service_name": "Cloud Storage", "consumed_unit": "GB"},
        {"service_name": "Cloud Storage", "consumed_unit": "Requests"},
        {"service_name": "Compute Engine", "consumed_unit": "Hours"},
    ]
    warnings = detect_mixed_units(records)
    assert len(warnings) == 1
    assert warnings[0]["kind"] == "mixed_units"
    assert warnings[0]["detail"]["service_name"] == "Cloud Storage"
    assert warnings[0]["detail"]["units"] == ["GB", "Requests"]

