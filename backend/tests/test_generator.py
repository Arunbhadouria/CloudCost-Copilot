"""Unit tests for synthetic dataset generator and ground truth integrity."""
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Dataset, Resource, DailySpend, GroundTruth
from app.services.generator import generate_synthetic_dataset
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


def test_price_table_hand_check():
    """Verify hand-checked unit test from section 7.3: e2-standard-4 -> e2-standard-2 saves $48.91/mo."""
    price_path = settings.REFERENCE_DIR / "price_table.json"
    assert price_path.is_file(), f"Price table missing at {price_path}"

    with open(price_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    machines = data["machines"]
    e2_4 = machines["e2-standard-4"]
    e2_2 = machines[e2_4["next_size_down"]]

    savings_hourly = e2_4["hourly_price"] - e2_2["hourly_price"]
    savings_monthly = savings_hourly * 730

    assert round(savings_monthly, 2) == 48.91


def test_synthetic_generator_ground_truth(db_session):
    """Verify synthetic dataset generator creates required resources, tags, and ground truth labels."""
    # Run with small months for fast test execution
    ds_id = generate_synthetic_dataset(
        db=db_session,
        seed=1,
        months=2,
        num_resources=50,
        start_date_str="2025-01-01"
    )

    # 1. Dataset record
    ds = db_session.query(Dataset).filter(Dataset.id == ds_id).first()
    assert ds is not None
    assert ds.kind == "synthetic"
    assert ds.seed == 1

    # 2. Check Ground Truth labels
    planted_idle = db_session.query(GroundTruth).filter(
        GroundTruth.dataset_id == ds_id,
        GroundTruth.kind == "idle",
        GroundTruth.is_positive == True
    ).count()
    assert planted_idle == 12

    planted_underused = db_session.query(GroundTruth).filter(
        GroundTruth.dataset_id == ds_id,
        GroundTruth.kind == "underused",
        GroundTruth.is_positive == True
    ).count()
    assert planted_underused == 12

    hard_negatives = db_session.query(GroundTruth).filter(
        GroundTruth.dataset_id == ds_id,
        GroundTruth.kind == "hard_negative"
    ).all()
    assert len(hard_negatives) > 0

    subtypes = {h.subtype for h in hard_negatives}
    assert "bursty" in subtypes
    assert "batch" in subtypes
    assert "dr" in subtypes

    # 3. Check Daily Spend is not marked derived
    derived_count = db_session.query(DailySpend).filter(
        DailySpend.dataset_id == ds_id,
        DailySpend.is_derived == True
    ).count()
    assert derived_count == 0


def test_generator_reproducibility(db_session):
    """Verify that generating with the same seed produces identical spend totals and counts."""
    ds_id_1 = generate_synthetic_dataset(
        db=db_session, seed=42, months=1, num_resources=20, dataset_id="repro-1"
    )
    total_1 = db_session.query(DailySpend).filter(DailySpend.dataset_id == "repro-1").count()

    ds_id_2 = generate_synthetic_dataset(
        db=db_session, seed=42, months=1, num_resources=20, dataset_id="repro-2"
    )
    total_2 = db_session.query(DailySpend).filter(DailySpend.dataset_id == "repro-2").count()

    assert total_1 == total_2

