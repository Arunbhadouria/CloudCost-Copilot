"""CLI script to scan and synchronize live Google Cloud resources into CloudCost Copilot."""
import sys
import os
import argparse

# Ensure backend directory is in path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.db import init_db, SessionLocal
from app.services.gcp_live import fetch_live_gcp_resources, register_live_gcp_dataset


def main():
    parser = argparse.ArgumentParser(description="Synchronize live GCP resources from a real Google Cloud project.")
    parser.add_argument("--project", default="big-formula-489906-e6", help="Google Cloud Project ID")
    parser.add_argument("--token", default=None, help="Optional OAuth access token")
    args = parser.parse_args()

    init_db()

    with SessionLocal() as db:
        print(f"Connecting to Google Cloud APIs for project: {args.project}...")
        result = fetch_live_gcp_resources(project_id=args.project, access_token=args.token)
        resources = result["resources"]
        statuses = result["api_statuses"]

        print("API Statuses:")
        for k, v in statuses.items():
            print(f"  - {k}: {v}")

        ds_id = register_live_gcp_dataset(db=db, project_id=args.project, resources=resources)
        print(f"[OK] Synchronized {len(resources)} live resource(s) into dataset: {ds_id}")


if __name__ == "__main__":
    main()
