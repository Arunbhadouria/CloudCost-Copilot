"""Unit tests verifying service classes cover all 25 GCP services."""
import pandas as pd
from app.services.classify import get_service_class, is_provisioned, get_all_classes
from app.config import settings


def test_service_classes_covers_csv():
    """Verify that all unique services in the CSV are covered by service_classes.json."""
    csv_path = settings.RAW_DIR / "gcp_final_approved_dataset.csv"
    df = pd.read_csv(csv_path)
    csv_services = set(df["Service Name"].unique())

    all_registered = get_all_classes()
    assert len(csv_services) == 25, f"Expected 25 services, got {len(csv_services)}"

    missing = [svc for svc in csv_services if svc not in all_registered]
    assert not missing, f"Services missing from service_classes.json: {missing}"


def test_provisioned_services():
    """Verify provisioned services classification."""
    expected_provisioned = {
        "Compute Engine", "Kubernetes Engine", "Cloud SQL",
        "Cloud Memorystore", "Cloud Dataproc"
    }
    for svc in expected_provisioned:
        assert is_provisioned(svc) is True
        assert get_service_class(svc) == "provisioned"

    assert is_provisioned("Cloud Storage") is False
    assert get_service_class("Cloud Storage") == "storage_messaging"
    assert is_provisioned("Cloud Run") is False
    assert get_service_class("Cloud Run") == "serverless"

