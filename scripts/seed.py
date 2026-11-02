"""Database seeding script for CloudCost Copilot.

Loads:
1. Real-format GCP billing export sample from data/raw/gcp_final_approved_dataset.csv
2. 12-month synthetic daily dataset (Seed 1)
3. 12-month held-out synthetic evaluation dataset (Seed 100)
And runs waste detectors on all datasets.
"""
import os
import sys

# Ensure backend directory is in path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.db import init_db, SessionLocal
from app.models import Dataset, Resource, Recommendation
from app.services.loader import load_csv_dataset
from app.services.generator import generate_synthetic_dataset
from app.routers.detect import run_detectors
from app.schemas import DetectRunRequest


def seed_database():
    print("=" * 60)
    print("CloudCost Copilot Database Seeder")
    print("=" * 60)

    # 1. Initialize tables
    print("[1/4] Initializing database schema...")
    init_db()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_path = os.path.join(repo_root, "data", "raw", "gcp_final_approved_dataset.csv")

    with SessionLocal() as db:
        # 2. Load Real-format GCP CSV
        print(f"[2/4] Loading real-format GCP billing sample ({csv_path})...")
        csv_ds = db.query(Dataset).filter(Dataset.id == "gcp-sample-csv").first()
        if not csv_ds:
            if os.path.exists(csv_path):
                with open(csv_path, "rb") as f:
                    content = f.read()
                res = load_csv_dataset(
                    db=db,
                    file_content=content,
                    dataset_name="Real-format GCP billing sample",
                    dataset_id="gcp-sample-csv"
                )
                print(f"      Loaded {res['rows_loaded']} rows, quarantined {res['rows_quarantined']}.")
            else:
                print(f"      Warning: CSV file not found at {csv_path}")
        else:
            print("      Real-format CSV already exists in database.")

        # Run snapshot detectors on real CSV
        print("      Running waste finders on real CSV...")
        run_detectors(req=DetectRunRequest(dataset_id="gcp-sample-csv", path="snapshot"), db=db)
        recs_count = db.query(Recommendation).filter(Recommendation.dataset_id == "gcp-sample-csv").count()
        print(f"      Found {recs_count} savings ideas on CSV sample.")

        # 3. Generate Primary Synthetic Dataset (Seed 1)
        print("[3/4] Generating 12-month synthetic production dataset (Seed 1)...")
        syn1 = db.query(Dataset).filter(Dataset.id == "synthetic-seed-1").first()
        if not syn1:
            generate_synthetic_dataset(
                db=db,
                seed=1,
                months=12,
                num_resources=300,
                dataset_id="synthetic-seed-1"
            )
            print("      Generated 300 resources, 12 months daily series, planted ground truth.")
        else:
            print("      Synthetic Seed 1 already exists.")

        # Run series detectors on Synthetic Seed 1
        print("      Running waste finders on Synthetic Seed 1...")
        run_detectors(req=DetectRunRequest(dataset_id="synthetic-seed-1", path="series"), db=db)
        syn1_recs = db.query(Recommendation).filter(Recommendation.dataset_id == "synthetic-seed-1").count()
        print(f"      Found {syn1_recs} savings ideas on Synthetic Seed 1.")

        # 4. Generate Held-Out Synthetic Dataset (Seed 100)
        print("[4/4] Generating held-out evaluation dataset (Seed 100)...")
        syn100 = db.query(Dataset).filter(Dataset.id == "synthetic-seed-100").first()
        if not syn100:
            generate_synthetic_dataset(
                db=db,
                seed=100,
                months=12,
                num_resources=300,
                dataset_id="synthetic-seed-100"
            )
            print("      Generated held-out benchmark dataset.")
        else:
            print("      Synthetic Seed 100 already exists.")

        print("      Running waste finders on Synthetic Seed 100...")
        run_detectors(req=DetectRunRequest(dataset_id="synthetic-seed-100", path="series"), db=db)

    print("=" * 60)
    print("Database seeding completed successfully!")
    print("Ready to run CloudCost Copilot.")
    print("=" * 60)


if __name__ == "__main__":
    seed_database()
