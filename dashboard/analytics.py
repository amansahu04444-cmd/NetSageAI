"""
NetSage AI - Dashboard Analytics & Metrics Engine

Provides reusable data analysis, KPI calculations, dataset health metrics,
and Responsible AI audit metrics for the dashboard.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from typing import Any, Dict, List, Optional, Tuple
import pandas as pd
from data.dataset_loader import load_cases_as_dicts, load_cases
from checker.rule_checker import run_all_checks
from review.audit_logger import load_all_review_records
from review.review_workflow import ReviewRecord
from review.review_service import create_review, accept_review, modify_review, reject_review
from ai.diagnosis_engine import diagnose_case


def get_case_dataset_summary() -> Dict[str, Any]:
    """Computes summary statistics for the cases.csv dataset."""
    cases = load_cases_as_dicts()
    df = load_cases()

    total_cases = len(cases)

    # Category / Concept distribution
    concept_col = "concept" if "concept" in df.columns else "concept_tag"
    category_counts = df[concept_col].value_counts().to_dict() if concept_col in df.columns else {}

    # Severity distribution
    severity_counts = df["severity"].value_counts().to_dict() if "severity" in df.columns else {}

    # Rule checker findings across all cases
    cases_with_errors = 0
    cases_all_not_checked = 0
    total_rule_checks = 0
    total_errors_detected = 0

    for c in cases:
        findings = run_all_checks(c)
        total_rule_checks += len(findings)
        err_count = sum(1 for f in findings if f.status == "ERROR")
        total_errors_detected += err_count

        if err_count > 0:
            cases_with_errors += 1
        elif all(f.status == "NOT_CHECKED" for f in findings):
            cases_all_not_checked += 1

    return {
        "total_cases": total_cases,
        "categories_count": len(category_counts),
        "category_distribution": category_counts,
        "severity_distribution": severity_counts,
        "cases_with_rule_errors": cases_with_errors,
        "cases_all_not_checked": cases_all_not_checked,
        "total_rule_checks_evaluated": total_rule_checks,
        "total_rule_errors_detected": total_errors_detected,
    }


def compute_responsible_ai_metrics(records: List[ReviewRecord]) -> Dict[str, Any]:
    """
    Computes Responsible AI metrics across review records.
    Excludes PENDING reviews from completed-review metrics.

    Formulas:
    - Agreement Rate = ACCEPTED / (ACCEPTED + MODIFIED + REJECTED) * 100
    - Correction Rate = MODIFIED / (ACCEPTED + MODIFIED + REJECTED) * 100
    - Rejection Rate = REJECTED / (ACCEPTED + MODIFIED + REJECTED) * 100
    """
    total_reviews = len(records)
    pending_count = sum(1 for r in records if r.status == "PENDING")
    accepted_count = sum(1 for r in records if r.status == "ACCEPTED")
    modified_count = sum(1 for r in records if r.status == "MODIFIED")
    rejected_count = sum(1 for r in records if r.status == "REJECTED")

    completed_count = accepted_count + modified_count + rejected_count

    if completed_count > 0:
        agreement_rate = (accepted_count / completed_count) * 100.0
        correction_rate = (modified_count / completed_count) * 100.0
        rejection_rate = (rejected_count / completed_count) * 100.0
        agreement_rate_str = f"{agreement_rate:.1f}%"
        correction_rate_str = f"{correction_rate:.1f}%"
        rejection_rate_str = f"{rejection_rate:.1f}%"
    else:
        agreement_rate = None
        correction_rate = None
        rejection_rate = None
        agreement_rate_str = "N/A"
        correction_rate_str = "N/A"
        rejection_rate_str = "N/A"

    corrected_ai_responses = modified_count + rejected_count

    real_records = [r for r in records if not getattr(r.ai_diagnosis, "is_mock", False)]
    mock_records = [r for r in records if getattr(r.ai_diagnosis, "is_mock", False)]

    real_corrected_count = sum(1 for r in real_records if r.status in ("MODIFIED", "REJECTED"))
    mock_corrected_count = sum(1 for r in mock_records if r.status in ("MODIFIED", "REJECTED"))

    return {
        "total_reviews": total_reviews,
        "pending_count": pending_count,
        "accepted_count": accepted_count,
        "modified_count": modified_count,
        "rejected_count": rejected_count,
        "completed_count": completed_count,
        "agreement_rate_pct": agreement_rate,
        "agreement_rate_str": agreement_rate_str,
        "correction_rate_pct": correction_rate,
        "correction_rate_str": correction_rate_str,
        "rejection_rate_pct": rejection_rate,
        "rejection_rate_str": rejection_rate_str,
        "corrected_ai_responses_count": corrected_ai_responses,
        "real_reviews_count": len(real_records),
        "mock_reviews_count": len(mock_records),
        "real_corrected_count": real_corrected_count,
        "mock_corrected_count": mock_corrected_count,
    }


def get_corrected_review_records(records: List[ReviewRecord]) -> List[ReviewRecord]:
    """Returns all review records where the AI recommendation was MODIFIED or REJECTED."""
    return [r for r in records if r.status in ("MODIFIED", "REJECTED")]


def seed_demo_corrected_reviews(min_required: int = 5) -> List[ReviewRecord]:
    """
    Ensures at least min_required corrected review records exist for Phase 5 requirements.
    Seeds additional review records clearly tagged as '[DEMO]' if needed.
    """
    all_records = load_all_review_records()
    corrected = get_corrected_review_records(all_records)

    if len(corrected) >= min_required:
        return load_all_review_records()

    needed = min_required - len(corrected)
    demo_cases = [("NET-002", "DHCP Scope Exhaustion"), ("NET-004", "OSPF Hello Mismatch"),
                  ("NET-006", "NAT Overload Keyword Missing"), ("NET-010", "SVI Shutdown"),
                  ("NET-012", "OSPF Passive Interface")]

    for idx in range(needed):
        cid, fault_desc = demo_cases[idx % len(demo_cases)]
        try:
            diag = diagnose_case(cid, force_mock=True)
            rec = create_review(diag, reviewer="[DEMO] Quality Reviewer")

            if idx % 2 == 0:
                edited_diag = diag.model_copy(deep=True)
                edited_diag.root_cause = f"[DEMO] Human refined root cause: {fault_desc}"
                edited_diag.confidence = 0.99
                modify_review(
                    rec.review_id,
                    edited_diagnosis=edited_diag,
                    reviewer="[DEMO] Quality Reviewer",
                    reason=f"[DEMO] Clarified technical diagnosis for {fault_desc}.",
                )
            else:
                reject_review(
                    rec.review_id,
                    reviewer="[DEMO] Quality Reviewer",
                    reason=f"[DEMO] Rejected initial diagnosis to request detailed packet capture for {fault_desc}.",
                )
        except Exception:
            pass

    return load_all_review_records()
