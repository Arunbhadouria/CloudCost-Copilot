"""Unit tests for Live Google Cloud (GCP) integration and project synchronization."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, Dataset, Resource, CostLineItem, DailySpend, Recommendation
from app.services.gcp_live import register_live_gcp_dataset
from app.routers.gcp_sync import get_gcp_status, sync_live_gcp, GcpSyncRequest

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


def test_register_live_gcp_dataset(db_session):
    """Verify live GCP resources are registered into FOCUS schema with $0.00 spend and auto-detected."""
    resources = [
        {
            "resource_id": "demo-instance-1",
            "service_name": "Compute Engine",
            "service_class": "provisioned",
            "region_id": "us-central1",
            "resource_type": "compute_instance",
            "machine_type": "e2-micro",
            "billed_cost": 0.0,
            "cpu_latest": 0.5,  # Idle CPU
            "mem_latest": 5.0,
            "tags": {"tier": "free", "env": "live"}
        },
        {
            "resource_id": "gs://school-demo-bucket",
            "service_name": "Cloud Storage",
            "service_class": "serverless",
            "region_id": "us-central1",
            "resource_type": "storage_bucket",
            "machine_type": None,
            "billed_cost": 0.0,
            "cpu_latest": 0.0,
            "mem_latest": 0.0,
            "tags": {"tier": "free"}
        }
    ]

    ds_id = register_live_gcp_dataset(
        db=db_session,
        project_id="test-school-project",
        resources=resources
    )

    assert ds_id == "gcp-live-test-school-project"

    # Verify dataset record
    ds = db_session.query(Dataset).filter(Dataset.id == ds_id).first()
    assert ds is not None
    assert ds.kind == "live_gcp"

    # Verify resources
    res_list = db_session.query(Resource).filter(Resource.dataset_id == ds_id).all()
    assert len(res_list) == 2

    # Verify zero-dollar cost line items
    items = db_session.query(CostLineItem).filter(CostLineItem.dataset_id == ds_id).all()
    assert len(items) == 2
    assert all(i.billed_cost == 0.0 for i in items)

    # Verify daily spend
    daily = db_session.query(DailySpend).filter(DailySpend.dataset_id == ds_id).all()
    assert len(daily) == 2
    assert all(d.billed_cost == 0.0 for d in daily)

    # Verify detector ran and flagged the idle Compute Engine instance
    recs = db_session.query(Recommendation).filter(Recommendation.dataset_id == ds_id).all()
    assert len(recs) >= 1
    assert recs[0].type == "idle"
    assert recs[0].resource_id == "demo-instance-1"


def test_gcp_sync_router_endpoints(db_session):
    """Verify GCP status check and sync router endpoint."""
    status = get_gcp_status()
    assert "gcloud_detected" in status
    assert "default_project" in status

    req = GcpSyncRequest(
        project_id="test-sync-project",
        access_token="fake-test-token"
    )
    res = sync_live_gcp(req=req, db=db_session)
    assert res["dataset_id"] == "gcp-live-test-sync-project"
    assert "resources_synced" in res
    assert "api_statuses" in res
