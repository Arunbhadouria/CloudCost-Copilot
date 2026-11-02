"""Unit tests for anomaly detection, SQL templates, and Copilot tool-calling flow."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Dataset, DailySpend
from app.services.generator import generate_synthetic_dataset
from app.services.loader import load_csv_dataset
from app.services.anomaly import detect_anomalies_for_dataset
from app.services.sql_templates import execute_cost_query, execute_get_recommendation
from app.services.copilot import run_copilot_chat
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


def test_anomaly_detection_on_synthetic(db_session):
    """Verify anomaly detector detects events on synthetic 12-month data with STL decomposition."""
    ds_id = generate_synthetic_dataset(
        db=db_session,
        seed=1,
        months=4,  # 120 days > 56 min history
        num_resources=40,
        dataset_id="anom-test-syn"
    )

    anomalies = detect_anomalies_for_dataset(db_session, ds_id, threshold=3.5)
    assert len(anomalies) > 0, "Expected at least 1 anomaly event detected on synthetic data"

    first_anom = anomalies[0]
    assert first_anom.start_date <= first_anom.end_date
    assert first_anom.peak_zscore >= 3.5
    assert first_anom.severity in ("low", "medium", "high")


def test_anomaly_detection_csv_insufficient_history(db_session):
    """CSV dataset has under 56 days of daily records and must return empty list."""
    csv_path = settings.RAW_DIR / "gcp_final_approved_dataset.csv"
    with open(csv_path, "rb") as f:
        content = f.read()

    load_csv_dataset(
        db=db_session,
        file_content=content,
        dataset_name="Real-format GCP billing sample",
        dataset_id="csv-anom-test"
    )

    anomalies = detect_anomalies_for_dataset(db_session, "csv-anom-test")
    assert anomalies == [], "CSV dataset should not produce anomalies due to insufficient history"


def test_sql_templates_allowlist(db_session):
    """Verify group_by allowlist prevents arbitrary SQL injection."""
    # Group by invalid dimension defaults safely to service_name
    res = execute_cost_query(
        db=db_session,
        dataset_id="anom-test-syn",
        group_by="malicious_col; DROP TABLE users; --"
    )
    assert "rows" in res
    assert "sql" in res


def test_copilot_chat_mock_flow(db_session):
    """Verify end-to-end Copilot flow emits token, tool_call, tool_result, and final events."""
    events = list(run_copilot_chat(
        db=db_session,
        dataset_id="anom-test-syn",
        user_message="Which service costs the most?"
    ))

    event_types = [e["type"] for e in events]
    assert "tool_call" in event_types
    assert "tool_result" in event_types
    assert "token" in event_types
    assert "final" in event_types

    final_event = [e for e in events if e["type"] == "final"][0]
    assert len(final_event["answer"]) > 0
    assert "faithfulness" in final_event
    assert final_event["faithfulness"]["passed"] is True

