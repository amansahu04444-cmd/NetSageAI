"""
NetSage AI - Audit Logger & Responsible AI Metrics Module

Handles persistent storage of review events in review/audit_log.csv and review/reviews.json.
Provides querying utilities for Responsible AI analytics (agreement rates, corrections, decisions).
"""

import csv
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from review.review_workflow import ReviewRecord

REVIEW_DIR = Path(__file__).parent
AUDIT_LOG_CSV = REVIEW_DIR / "audit_log.csv"
REVIEWS_JSON = REVIEW_DIR / "reviews.json"

CSV_HEADERS = [
    "review_id",
    "case_id",
    "timestamp",
    "status",
    "reviewer",
    "reason",
    "ai_root_cause",
    "human_root_cause",
    "ai_confidence",
    "human_confidence",
    "ai_osi_layer",
    "human_osi_layer",
    "is_mock",
]


def _ensure_storage_files():
    """Initializes audit CSV headers and JSON storage if missing."""
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    if not AUDIT_LOG_CSV.exists():
        with open(AUDIT_LOG_CSV, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_HEADERS)
    if not REVIEWS_JSON.exists():
        with open(REVIEWS_JSON, mode="w", encoding="utf-8") as f:
            json.dump({}, f)


def save_review_record(record: ReviewRecord) -> None:
    """
    Saves or updates a ReviewRecord in reviews.json and logs audit event to audit_log.csv.
    Does NOT overwrite original AI diagnosis data.
    """
    _ensure_storage_files()

    # 1. Update JSON store
    with open(REVIEWS_JSON, mode="r", encoding="utf-8") as f:
        try:
            records_dict = json.load(f)
        except json.JSONDecodeError:
            records_dict = {}

    records_dict[record.review_id] = record.model_dump()

    with open(REVIEWS_JSON, mode="w", encoding="utf-8") as f:
        json.dump(records_dict, f, indent=2)

    # 2. Append event to audit_log.csv
    ai_diag = record.ai_diagnosis
    hum_diag = record.human_diagnosis

    row = [
        record.review_id,
        record.case_id,
        record.reviewed_at or record.created_at,
        record.status,
        record.reviewer or "N/A",
        record.reason or "",
        ai_diag.root_cause,
        hum_diag.root_cause if hum_diag else "N/A",
        ai_diag.confidence,
        hum_diag.confidence if hum_diag else "N/A",
        ai_diag.osi_layer,
        hum_diag.osi_layer if hum_diag else "N/A",
        ai_diag.is_mock,
    ]

    with open(AUDIT_LOG_CSV, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(row)


def load_all_review_records() -> List[ReviewRecord]:
    """Loads all review records from the persistent JSON store."""
    _ensure_storage_files()
    with open(REVIEWS_JSON, mode="r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return [ReviewRecord.model_validate(val) for val in data.values()]
        except json.JSONDecodeError:
            return []


def get_review_record(review_id: str) -> Optional[ReviewRecord]:
    """Retrieves a single review record by review_id."""
    records = load_all_review_records()
    return next((r for r in records if r.review_id == review_id), None)


def get_audit_metrics() -> Dict[str, Any]:
    """
    Computes Responsible AI metrics across all historical review records:
    - total reviews
    - pending count
    - accepted count
    - modified count
    - rejected count
    - agreement rate
    - corrected AI responses count (modified + rejected)
    """
    records = load_all_review_records()
    total = len(records)
    pending = sum(1 for r in records if r.status == "PENDING")
    accepted = sum(1 for r in records if r.status == "ACCEPTED")
    modified = sum(1 for r in records if r.status == "MODIFIED")
    rejected = sum(1 for r in records if r.status == "REJECTED")

    completed = accepted + modified + rejected
    agreement_rate = (accepted / completed * 100.0) if completed > 0 else 0.0
    corrected_count = modified + rejected

    return {
        "total_reviews": total,
        "pending_count": pending,
        "accepted_count": accepted,
        "modified_count": modified,
        "rejected_count": rejected,
        "completed_count": completed,
        "agreement_rate_pct": round(agreement_rate, 2),
        "corrected_ai_responses_count": corrected_count,
    }
