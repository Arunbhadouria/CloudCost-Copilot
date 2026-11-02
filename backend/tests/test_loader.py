"""Unit and integration tests for CSV loader and cost aggregation endpoints."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.models import Base, Dataset, Resource, CostLineItem, DailySpend, DataWarning
from app.services.loader import load_csv_dataset
from app.routers.datasets import health_check, list_datasets, get_dataset_summary
from app.routers.costs import get_costs, get_top_costs
from app.config import settings

# Test in-memory database setup with StaticPool for cross-thread memory sharing in FastAPI
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


def test_load_real_csv_dataset(db_session):
    """Test loading the real-format GCP billing sample CSV."""
    csv_path = settings.RAW_DIR / "gcp_final_approved_dataset.csv"
    assert csv_path.is_file(), f"Approved CSV missing at {csv_path}"

    with open(csv_path, "rb") as f:
        content = f.read()

    result = load_csv_dataset(
        db=db_session,
        file_content=content,
        dataset_name="Real-format GCP billing export sample",
        dataset_id="csv-test-01"
    )

    assert result["dataset_id"] == "csv-test-01"
    assert result["rows_loaded"] == 1000
    assert result["rows_quarantined"] == 0
    assert result["warnings"] > 0  # mixed_units warnings expected

    # Check DB tables
    line_items_count = db_session.query(CostLineItem).filter(CostLineItem.dataset_id == "csv-test-01").count()
    assert line_items_count == 1000

    res_count = db_session.query(Resource).filter(Resource.dataset_id == "csv-test-01").count()
    assert res_count == 1000

    daily_spend_count = db_session.query(DailySpend).filter(DailySpend.dataset_id == "csv-test-01").count()
    assert daily_spend_count > 0

    # Ensure all daily spend entries are marked derived
    non_derived = db_session.query(DailySpend).filter(
        DailySpend.dataset_id == "csv-test-01",
        DailySpend.is_derived == False
    ).count()
    assert non_derived == 0


def test_api_endpoints(db_session):
    """Test dataset and cost API endpoints directly."""
    # 1. Health
    h = health_check()
    assert h.status == "ok"

    # 2. Datasets list
    datasets = list_datasets(db=db_session)
    assert len(datasets) >= 1
    assert datasets[0].id == "csv-test-01"

    # 3. Dataset summary
    summary = get_dataset_summary(id="csv-test-01", db=db_session)
    assert summary.resources == 1000
    assert summary.total_cost > 0
    assert summary.is_derived_daily is True

    # 4. Costs grouped by service
    costs_svc = get_costs(dataset_id="csv-test-01", group_by="service", limit=10, db=db_session)
    assert len(costs_svc) <= 10
    assert costs_svc[0].billed_cost > 0
    assert costs_svc[0].share_pct > 0

    # 5. Top costs
    top = get_top_costs(dataset_id="csv-test-01", n=5, db=db_session)
    assert len(top) == 5
    assert sum(item.share_pct for item in top) <= 100.0
