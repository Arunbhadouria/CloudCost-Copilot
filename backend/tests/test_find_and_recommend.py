"""Unit and acceptance tests for detectors, savings, ranking, and CSV 11/3/52 acceptance criteria."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Dataset, Resource, Recommendation, CostLineItem
from app.services.loader import load_csv_dataset
from app.services.detectors import evaluate_resource_detector, make_snapshot
from app.services.savings import calculate_savings
from app.services.ranking import calculate_confidence, calculate_effort, calculate_priority
from app.routers.detect import run_detectors
from app.schemas import DetectRunRequest
from app.config import settings

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


def test_real_csv_acceptance_counts(db_session):
    """CRITICAL ACCEPTANCE TEST: Real CSV must produce EXACTLY 11 idle, 3 underused, 52 weak_signal.

    Fail the build if different.
    """
    csv_path = settings.RAW_DIR / "gcp_final_approved_dataset.csv"
    with open(csv_path, "rb") as f:
        content = f.read()

    load_result = load_csv_dataset(
        db=db_session,
        file_content=content,
        dataset_name="Real-format GCP billing sample",
        dataset_id="csv-acceptance-test"
    )
    assert load_result["rows_loaded"] == 1000

    detect_res = run_detectors(
        req=DetectRunRequest(dataset_id="csv-acceptance-test", path="snapshot"),
        db=db_session
    )

    counts = detect_res.counts
    assert counts["idle"] == 11, f"Expected 11 idle, got {counts['idle']}"
    assert counts["underused"] == 3, f"Expected 3 underused, got {counts['underused']}"
    assert counts["weak_signal"] == 52, f"Expected 52 weak_signal, got {counts['weak_signal']}"

    # Also verify in database
    db_idle = db_session.query(Recommendation).filter(
        Recommendation.dataset_id == "csv-acceptance-test",
        Recommendation.type == "idle"
    ).count()
    assert db_idle == 11

    db_underused = db_session.query(Recommendation).filter(
        Recommendation.dataset_id == "csv-acceptance-test",
        Recommendation.type == "underused"
    ).count()
    assert db_underused == 3

    db_weak = db_session.query(Recommendation).filter(
        Recommendation.dataset_id == "csv-acceptance-test",
        Recommendation.type == "weak_signal"
    ).count()
    assert db_weak == 52


def test_detector_rules_both_paths():
    """Verify detector rules logic across snapshot and series paths."""
    # Non-provisioned services are always ignored
    res = evaluate_resource_detector(
        summary={"cpu_latest": 2.0, "mem_latest": 10.0},
        service_class="serverless"
    )
    assert res is None

    # Tag exclusions: role=dr or role=batch are ignored
    res = evaluate_resource_detector(
        summary={"cpu_latest": 2.0, "mem_latest": 10.0},
        service_class="provisioned",
        tags={"role": "dr"}
    )
    assert res is None

    res = evaluate_resource_detector(
        summary={"cpu_latest": 2.0, "mem_latest": 10.0},
        service_class="provisioned",
        tags={"role": "batch"}
    )
    assert res is None

    # Snapshot path
    # Idle: cpu < 5
    res = evaluate_resource_detector(
        summary={"cpu_latest": 4.9, "mem_latest": 50.0},
        service_class="provisioned",
        path="snapshot"
    )
    assert res[0] == "idle"

    # Underused: cpu < 20 and mem < 20 (and not idle)
    res = evaluate_resource_detector(
        summary={"cpu_latest": 15.0, "mem_latest": 18.0},
        service_class="provisioned",
        path="snapshot"
    )
    assert res[0] == "underused"

    # Weak signal: exactly one < 20
    res = evaluate_resource_detector(
        summary={"cpu_latest": 15.0, "mem_latest": 60.0},
        service_class="provisioned",
        path="snapshot"
    )
    assert res[0] == "weak_signal"

    # Series path
    # Idle: cpu_avg < 5 and cpu_p95 < 10
    res = evaluate_resource_detector(
        summary={"cpu_avg": 3.0, "cpu_p95": 8.0, "mem_p95": 30.0},
        service_class="provisioned",
        path="series"
    )
    assert res[0] == "idle"

    # Bursty hard negative should NOT be idle (cpu_avg=4, but cpu_p95=70)
    res = evaluate_resource_detector(
        summary={"cpu_avg": 4.0, "cpu_p95": 70.0, "mem_p95": 40.0},
        service_class="provisioned",
        path="series"
    )
    assert res is None


def test_savings_calculations():
    """Verify savings formulas for synthetic (price table) and CSV (assumptions)."""
    # 1. Synthetic idle: full monthly run-rate (e2-standard-4: 0.134 * 730 = 97.82)
    syn_idle = calculate_savings("idle", "synthetic", billed_cost=100.0, machine_type="e2-standard-4")
    assert syn_idle["savings_basis"] == "price_table"
    assert syn_idle["savings_unit"] == "monthly"
    assert syn_idle["savings_mid"] == 97.82

    # 2. Synthetic underused: resize delta e2-standard-4 -> e2-standard-2 saves 48.91
    syn_under = calculate_savings("underused", "synthetic", billed_cost=100.0, machine_type="e2-standard-4")
    assert syn_under["savings_mid"] == 48.91

    # 3. CSV idle: 90% to 100% of billed_cost (e.g. $100 -> $90 to $100, mid $95)
    csv_idle = calculate_savings("idle", "csv", billed_cost=100.0)
    assert csv_idle["savings_low"] == 90.0
    assert csv_idle["savings_high"] == 100.0
    assert csv_idle["savings_mid"] == 95.0
    assert csv_idle["savings_basis"] == "assumption"
    assert csv_idle["savings_unit"] == "observed_window"

    # 4. CSV underused: 30% to 50% of billed_cost (mid $40)
    csv_under = calculate_savings("underused", "csv", billed_cost=100.0)
    assert csv_under["savings_low"] == 30.0
    assert csv_under["savings_high"] == 50.0
    assert csv_under["savings_mid"] == 40.0

    # 5. Weak signal always saves 0
    weak = calculate_savings("weak_signal", "csv", billed_cost=100.0)
    assert weak["savings_mid"] == 0.0


def test_ranking_and_priorities():
    """Verify confidence, effort, and priority calculations."""
    # Series confidence
    conf_series = calculate_confidence("series", is_prod=False, cpu_cv=0.5)
    assert conf_series == 0.9

    # Series prod penalty (-0.2)
    conf_prod = calculate_confidence("series", is_prod=True, cpu_cv=0.5)
    assert conf_prod == 0.7

    # Series high CV penalty (-0.1)
    conf_cv = calculate_confidence("series", is_prod=False, cpu_cv=1.2)
    assert conf_cv == 0.8

    # Snapshot base 0.5
    conf_snap = calculate_confidence("snapshot", is_prod=False)
    assert conf_snap == 0.5

    # Floor at 0.2
    conf_floor = calculate_confidence("snapshot", is_prod=True, cpu_cv=1.5)
    assert conf_floor == 0.2  # 0.5 - 0.2 - 0.1 = 0.2

    # Effort: idle=1, underused=3, weak_signal=5
    assert calculate_effort("idle") == 1
    assert calculate_effort("underused") == 3
    assert calculate_effort("weak_signal") == 5

    # Priority = savings_mid * confidence / effort
    # Idle ($100 mid, 0.9 conf, 1 effort) -> 90.0
    assert calculate_priority(100.0, 0.9, 1, "idle") == 90.0
    # Underused ($100 mid, 0.9 conf, 3 effort) -> 30.0
    assert calculate_priority(100.0, 0.9, 3, "underused") == 30.0
    # Weak signal is always priority 0
    assert calculate_priority(100.0, 0.9, 5, "weak_signal") == 0.0

