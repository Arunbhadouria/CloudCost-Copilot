"""Unit tests for the evaluation harness and scoring metrics."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Dataset, EvalRun
from app.services.generator import generate_synthetic_dataset
from app.services.evaluation import (
    evaluate_finders_for_dataset,
    evaluate_snapshot_path_drop,
    evaluate_savings_backtest,
    run_comprehensive_evaluation
)

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


def test_series_finder_evaluation(db_session):
    """Verify series path detection achieves target recall >= 0.90 on synthetic ground truth."""
    ds_id = generate_synthetic_dataset(
        db=db_session,
        seed=101,
        months=2,
        num_resources=60,
        dataset_id="eval-test-101"
    )

    metrics = evaluate_finders_for_dataset(db_session, ds_id, path="series")

    assert metrics["recall"] >= 0.90, f"Expected recall >= 0.90, got {metrics['recall']}"
    assert metrics["precision"] >= 0.80, f"Expected precision >= 0.80, got {metrics['precision']}"
    assert metrics["f1"] >= 0.80, f"Expected f1 >= 0.80, got {metrics['f1']}"

    # False positives on hard negatives must be low
    fp_breakdown = metrics["hard_negative_fps"]
    assert fp_breakdown["dr"] == 0, "Intentional DR should never be flagged as a positive"
    assert fp_breakdown["batch"] == 0, "Batch instances should never be flagged as a positive"


def test_snapshot_path_drop(db_session):
    """Verify snapshot evaluation on synthetic data and recall drop measurement."""
    ds_id = "eval-test-101"
    snap_metrics = evaluate_snapshot_path_drop(db_session, ds_id, seed=101)

    assert "recall" in snap_metrics
    assert "precision" in snap_metrics


def test_savings_backtest(db_session):
    """Verify savings backtest calculates MAPE."""
    ds_id = "eval-test-101"
    backtest = evaluate_savings_backtest(db_session, ds_id)

    assert "mape_pct" in backtest
    assert backtest["mape_pct"] <= 15.0  # reasonable bound on test run

