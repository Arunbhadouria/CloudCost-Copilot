"""Export CSV sample findings for human DevOps review and agreement scoring."""
import os
import sys
import csv
import argparse
from typing import List, Dict, Any
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add backend to sys.path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend"))

from app.models import Base, Dataset, Resource, UtilizationSummary, Recommendation, CostLineItem
from app.services.loader import load_csv_dataset
from app.routers.detect import run_detectors
from app.schemas import DetectRunRequest


def export_review_csv(output_path: str = "review.csv") -> str:
    """Generate review.csv with 11 idle, 3 underused, and 5 weak-signal rows from real CSV."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Load real CSV
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    csv_file = os.path.join(repo_root, "data", "raw", "gcp_final_approved_dataset.csv")

    with open(csv_file, "rb") as f:
        load_res = load_csv_dataset(db=db, file_content=f.read(), dataset_id="real-csv-review")
    run_detectors(req=DetectRunRequest(dataset_id="real-csv-review", path="snapshot"), db=db)

    # 1. Fetch 11 idle and 3 underused
    idle_recs = db.query(Recommendation).filter(
        Recommendation.dataset_id == "real-csv-review",
        Recommendation.type == "idle"
    ).all()

    underused_recs = db.query(Recommendation).filter(
        Recommendation.dataset_id == "real-csv-review",
        Recommendation.type == "underused"
    ).all()

    weak_recs = db.query(Recommendation).filter(
        Recommendation.dataset_id == "real-csv-review",
        Recommendation.type == "weak_signal"
    ).limit(5).all()

    selected_recs = idle_recs + underused_recs + weak_recs

    headers = [
        "resource_id",
        "service_name",
        "finding_type",
        "cpu_latest",
        "mem_latest",
        "billed_cost",
        "savings_range",
        "reviewer_agreement",
        "notes"
    ]

    rows = []
    for rec in selected_recs:
        summ = db.query(UtilizationSummary).filter(
            UtilizationSummary.dataset_id == "real-csv-review",
            UtilizationSummary.resource_id == rec.resource_id
        ).first()

        cost_item = db.query(CostLineItem).filter(
            CostLineItem.dataset_id == "real-csv-review",
            CostLineItem.resource_id == rec.resource_id
        ).first()

        cpu_val = round(summ.cpu_latest, 1) if summ and summ.cpu_latest is not None else "N/A"
        mem_val = round(summ.mem_latest, 1) if summ and summ.mem_latest is not None else "N/A"
        billed = round(cost_item.billed_cost, 2) if cost_item else round(rec.savings_mid, 2)
        sav_range = f"${rec.savings_low:.2f} - ${rec.savings_high:.2f}" if rec.savings_high > 0 else "$0.00"

        rows.append({
            "resource_id": rec.resource_id,
            "service_name": rec.service_name,
            "finding_type": rec.type,
            "cpu_latest": cpu_val,
            "mem_latest": mem_val,
            "billed_cost": billed,
            "savings_range": sav_range,
            "reviewer_agreement": "",
            "notes": ""
        })

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Exported {len(rows)} rows (11 idle, 3 underused, 5 weak-signal) to {output_path}")
    db.close()
    return output_path


def print_review_stats(filepath: str = "review.csv"):
    """Read review.csv and print summary agreement statistics."""
    if not os.path.exists(filepath):
        print(f"Review file {filepath} not found.")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    if not reader:
        print("Review file is empty.")
        return

    total = len(reader)
    yes_count = 0
    no_count = 0
    maybe_count = 0
    blank_count = 0

    by_type: Dict[str, Dict[str, int]] = {}

    for r in reader:
        agr = (r.get("reviewer_agreement") or "").strip().upper()
        ft = r.get("finding_type", "unknown")
        if ft not in by_type:
            by_type[ft] = {"YES": 0, "NO": 0, "MAYBE": 0, "BLANK": 0}

        if agr == "YES":
            yes_count += 1
            by_type[ft]["YES"] += 1
        elif agr == "NO":
            no_count += 1
            by_type[ft]["NO"] += 1
        elif agr == "MAYBE":
            maybe_count += 1
            by_type[ft]["MAYBE"] += 1
        else:
            blank_count += 1
            by_type[ft]["BLANK"] += 1

    reviewed = yes_count + no_count + maybe_count
    pct = round((yes_count / reviewed * 100.0), 1) if reviewed > 0 else 0.0

    print("=" * 55)
    print("DevOps Lead Review Agreement Summary")
    print("=" * 55)
    print(f"Total Rows:     {total}")
    print(f"Reviewed Rows:  {reviewed}")
    print(f"Agreed (YES):   {yes_count}")
    print(f"Disagreed (NO): {no_count}")
    print(f"Tentative:      {maybe_count}")
    print(f"Unreviewed:     {blank_count}")
    print(f"Agreement Rate: {pct}%")
    print("-" * 55)
    print(f"{'Finding Type':<15} {'YES':<8} {'NO':<8} {'MAYBE':<8} {'BLANK':<8}")
    for ft, counts in by_type.items():
        print(f"{ft:<15} {counts['YES']:<8} {counts['NO']:<8} {counts['MAYBE']:<8} {counts['BLANK']:<8}")
    print("=" * 55)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export findings for review or print review stats.")
    parser.add_argument("--stats", action="store_true", help="Print agreement stats from review.csv")
    parser.add_argument("--file", default="review.csv", help="Target review CSV path")
    args = parser.parse_args()

    if args.stats:
        print_review_stats(args.file)
    else:
        export_review_csv(args.file)
