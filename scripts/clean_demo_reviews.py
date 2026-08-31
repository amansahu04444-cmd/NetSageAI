"""
NetSage AI - Safe Review Data Cleanup Script

Cleans mock/demo test records from review/reviews.json while preserving real Gemini API diagnoses.

Usage:
  python scripts/clean_demo_reviews.py [--dry-run] [--execute]
"""

import sys
import json
import shutil
import argparse
from pathlib import Path

REVIEWS_FILE = Path(__file__).parent.parent / "review" / "reviews.json"
BACKUP_FILE = Path(__file__).parent.parent / "review" / "reviews_backup.json"


def inspect_and_clean_reviews(execute: bool = False):
    if not REVIEWS_FILE.exists():
        print(f"[ERROR] Reviews file missing at: {REVIEWS_FILE}")
        sys.exit(1)

    with open(REVIEWS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    total_before = len(data)

    mock_records = {}
    real_records = {}
    net001_mock_count = 0
    other_mock_count = 0

    for rid, record in data.items():
        if isinstance(record, str):
            rec_obj = json.loads(record)
        else:
            rec_obj = record

        ai_diag = rec_obj.get("ai_diagnosis", {}) or {}
        if isinstance(ai_diag, str):
            ai_diag = json.loads(ai_diag)

        is_mock = ai_diag.get("is_mock", True)
        case_id = rec_obj.get("case_id", "UNKNOWN")

        if is_mock:
            mock_records[rid] = rec_obj
            if case_id == "NET-001":
                net001_mock_count += 1
            else:
                other_mock_count += 1
        else:
            real_records[rid] = rec_obj

    total_mock_removed = len(mock_records)
    total_real_preserved = len(real_records)
    total_after = len(real_records)

    print("==================================================")
    print("      NETSAGE AI - REVIEW DATA CLEANUP SUMMARY    ")
    print("==================================================")
    print(f"Total Records Before Cleanup : {total_before}")
    print(f"  * Mock/Demo Records Found  : {total_mock_removed}")
    print(f"    - Repeated NET-001 Mock  : {net001_mock_count}")
    print(f"    - Other Case Mocks       : {other_mock_count}")
    print(f"  * Real Gemini Records      : {total_real_preserved}")
    print("--------------------------------------------------")

    if total_real_preserved > 0:
        print("Real Gemini Records Preserved:")
        for rid, r in real_records.items():
            cid = r.get("case_id")
            st = r.get("status")
            rev = r.get("reviewer")
            dt = r.get("created_at")
            diag = r.get("ai_diagnosis", {})
            rc = diag.get("root_cause", "") if isinstance(diag, dict) else ""
            print(f"  [KEEP] {rid} | Case: {cid} | Status: {st} | Reviewer: {rev} | Created: {dt}")
            print(f"         Root Cause: {rc[:80]}...")
    else:
        print("No real Gemini records found to preserve.")

    print("==================================================")

    if not execute:
        print("\n[DRY RUN MODE] No changes were written to disk.")
        print("To execute this cleanup, run:")
        print("  python scripts/clean_demo_reviews.py --execute")
        return

    # Create backup before modifying
    shutil.copy2(REVIEWS_FILE, BACKUP_FILE)
    print(f"✓ Backup created at: {BACKUP_FILE}")

    # Write cleaned real records back to review/reviews.json
    with open(REVIEWS_FILE, "w", encoding="utf-8") as f:
        json.dump(real_records, f, indent=2)

    print(f"✓ Updated {REVIEWS_FILE} successfully.")
    print("--------------------------------------------------")
    print(f"Total Before           : {total_before}")
    print(f"Mock/Demo Removed      : {total_mock_removed}")
    print(f"Real Preserved         : {total_real_preserved}")
    print(f"Total After            : {total_after}")
    print("==================================================")


def main():
    parser = argparse.ArgumentParser(description="NetSage AI - Safe Review Data Cleanup Utility")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute review cleanup on disk (creates backup first)",
    )
    args = parser.parse_args()
    inspect_and_clean_reviews(execute=args.execute)


if __name__ == "__main__":
    main()
