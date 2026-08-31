"""
NetSage AI - Review Service Module

High-level service interface for managing Human-in-the-Loop review workflows.
Enforces validation rules, state transitions, and audit trail generation.
"""

from typing import List, Optional, Dict, Any
from ai.structured_output import DiagnosisResult
from review.review_workflow import (
    ReviewRecord,
    InvalidStateTransitionError,
    ReviewValidationError,
)
from review.audit_logger import (
    save_review_record,
    load_all_review_records,
    get_review_record,
    get_audit_metrics,
)


class ReviewNotFoundError(Exception):
    """Raised when a specified review_id is not found."""
    pass


def create_review(diagnosis: DiagnosisResult, reviewer: Optional[str] = None) -> ReviewRecord:
    """
    Creates a new PENDING review record from a validated DiagnosisResult object.
    Preserves original AI diagnosis without modification.
    """
    record = ReviewRecord(
        case_id=diagnosis.case_id,
        status="PENDING",
        ai_diagnosis=diagnosis,
        human_diagnosis=None,
        reviewer=reviewer,
        reason=None,
    )
    save_review_record(record)
    return record


def accept_review(review_id: str, reviewer: str, reason: Optional[str] = None) -> ReviewRecord:
    """Approves an existing PENDING review without modifying AI recommendations."""
    record = get_review_record(review_id)
    if not record:
        raise ReviewNotFoundError(f"Review '{review_id}' not found.")

    record.accept(reviewer=reviewer, reason=reason)
    save_review_record(record)
    return record


def modify_review(
    review_id: str,
    edited_diagnosis: DiagnosisResult,
    reviewer: str,
    reason: str,
) -> ReviewRecord:
    """Modifies an existing PENDING review, saving edited diagnosis and reason."""
    record = get_review_record(review_id)
    if not record:
        raise ReviewNotFoundError(f"Review '{review_id}' not found.")

    record.modify(edited_diagnosis=edited_diagnosis, reviewer=reviewer, reason=reason)
    save_review_record(record)
    return record


def reject_review(review_id: str, reviewer: str, reason: str) -> ReviewRecord:
    """Rejects an existing PENDING review with mandatory rejection reason."""
    record = get_review_record(review_id)
    if not record:
        raise ReviewNotFoundError(f"Review '{review_id}' not found.")

    record.reject(reviewer=reviewer, reason=reason)
    save_review_record(record)
    return record


def get_review(review_id: str) -> ReviewRecord:
    """Retrieves a specific review record by ID."""
    record = get_review_record(review_id)
    if not record:
        raise ReviewNotFoundError(f"Review '{review_id}' not found.")
    return record


def list_reviews(status: Optional[str] = None) -> List[ReviewRecord]:
    """Lists review records, optionally filtered by status."""
    all_records = load_all_review_records()
    if status:
        stat_upper = status.upper()
        return [r for r in all_records if r.status == stat_upper]
    return all_records


def list_pending_reviews() -> List[ReviewRecord]:
    """Lists all reviews currently in PENDING state."""
    return list_reviews(status="PENDING")


def get_metrics() -> Dict[str, Any]:
    """Retrieves Responsible AI audit analytics metrics."""
    return get_audit_metrics()
