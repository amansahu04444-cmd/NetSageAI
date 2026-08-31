"""
Unit Tests for NetSage AI Phase 4 Human Review & Approval Workflow

Verifies:
1. PENDING initial review state.
2. Accept, Modify, and Reject workflows.
3. Rejection and Modification validation (mandatory reason & reviewer).
4. Illegal state transition enforcement (immutable terminal states).
5. Preservation of original AI diagnosis after modification.
6. Audit logger persistence (CSV & JSON) and Responsible AI metrics calculation.
"""

import unittest
from pathlib import Path
from ai.structured_output import DiagnosisResult, RuleCheckerFinding
from review.review_workflow import (
    ReviewRecord,
    InvalidStateTransitionError,
    ReviewValidationError,
)
from review.review_service import (
    create_review,
    accept_review,
    modify_review,
    reject_review,
    get_review,
    list_reviews,
    list_pending_reviews,
    get_metrics,
)
from review.audit_logger import AUDIT_LOG_CSV, REVIEWS_JSON


class TestReviewWorkflow(unittest.TestCase):

    def setUp(self):
        self.sample_diagnosis = DiagnosisResult(
            case_id="NET-001",
            root_cause="Router sub-interface GigabitEthernet0/0.10 is down.",
            diagnosis_status="CONFIRMED",
            confidence=0.95,
            osi_layer="Layer 3",
            evidence=["GigabitEthernet0/0.10 is administratively down"],
            rule_checker_findings=[
                RuleCheckerFinding(rule="interface_status", status="ERROR", message="Interface down")
            ],
            next_command=None,
            fix_steps=["no shutdown"],
            explanation="Sub-interface is down in show output.",
            is_mock=True,
        )

    def test_new_review_starts_as_pending(self):
        record = create_review(self.sample_diagnosis)
        self.assertEqual(record.status, "PENDING")
        self.assertIsNotNone(record.review_id)
        self.assertEqual(record.case_id, "NET-001")
        self.assertEqual(record.ai_diagnosis.root_cause, self.sample_diagnosis.root_cause)
        self.assertIsNone(record.human_diagnosis)

    def test_accept_workflow_success(self):
        record = create_review(self.sample_diagnosis)
        accepted_rec = accept_review(record.review_id, reviewer="Aman", reason="Looks accurate.")
        self.assertEqual(accepted_rec.status, "ACCEPTED")
        self.assertEqual(accepted_rec.reviewer, "Aman")
        self.assertEqual(accepted_rec.reason, "Looks accurate.")
        self.assertIsNotNone(accepted_rec.human_diagnosis)
        self.assertEqual(accepted_rec.human_diagnosis.root_cause, self.sample_diagnosis.root_cause)

    def test_modify_workflow_success(self):
        record = create_review(self.sample_diagnosis)

        edited_diag = self.sample_diagnosis.model_copy(deep=True)
        edited_diag.root_cause = "Human corrected root cause: VLAN 10 interface shutdown."
        edited_diag.confidence = 1.0

        modified_rec = modify_review(
            record.review_id,
            edited_diagnosis=edited_diag,
            reviewer="Aman",
            reason="Refined root cause explanation for clarity.",
        )

        self.assertEqual(modified_rec.status, "MODIFIED")
        self.assertEqual(modified_rec.reviewer, "Aman")
        self.assertEqual(modified_rec.reason, "Refined root cause explanation for clarity.")
        self.assertIsNotNone(modified_rec.human_diagnosis)
        self.assertEqual(
            modified_rec.human_diagnosis.root_cause,
            "Human corrected root cause: VLAN 10 interface shutdown.",
        )
        # CRITICAL TEST: Original AI diagnosis must remain unchanged!
        self.assertEqual(
            modified_rec.ai_diagnosis.root_cause,
            "Router sub-interface GigabitEthernet0/0.10 is down.",
        )

    def test_reject_workflow_success(self):
        record = create_review(self.sample_diagnosis)
        rejected_rec = reject_review(
            record.review_id,
            reviewer="Aman",
            reason="Incorrect root cause identified by AI.",
        )
        self.assertEqual(rejected_rec.status, "REJECTED")
        self.assertEqual(rejected_rec.reviewer, "Aman")
        self.assertEqual(rejected_rec.reason, "Incorrect root cause identified by AI.")

    def test_reject_without_reason_fails(self):
        record = create_review(self.sample_diagnosis)
        with self.assertRaises(ReviewValidationError):
            reject_review(record.review_id, reviewer="Aman", reason="  ")

    def test_modify_without_reason_fails(self):
        record = create_review(self.sample_diagnosis)
        with self.assertRaises(ReviewValidationError):
            modify_review(
                record.review_id,
                edited_diagnosis=self.sample_diagnosis,
                reviewer="Aman",
                reason="",
            )

    def test_invalid_state_transition_fails(self):
        record = create_review(self.sample_diagnosis)
        accept_review(record.review_id, reviewer="Aman")
        # Second transition on already terminal ACCEPTED state must fail
        rec = get_review(record.review_id)
        with self.assertRaises(InvalidStateTransitionError):
            rec.reject(reviewer="Aman", reason="Trying to reject accepted review")

    def test_audit_log_created_and_persisted(self):
        record = create_review(self.sample_diagnosis)
        accept_review(record.review_id, reviewer="AuditTester", reason="Audit log validation.")

        self.assertTrue(AUDIT_LOG_CSV.exists())
        self.assertTrue(REVIEWS_JSON.exists())

        audit_text = AUDIT_LOG_CSV.read_text(encoding="utf-8")
        self.assertIn("AuditTester", audit_text)
        self.assertIn("Audit log validation.", audit_text)

    def test_metrics_calculation(self):
        # Create 3 separate reviews
        r1 = create_review(self.sample_diagnosis)
        accept_review(r1.review_id, reviewer="Rev1")

        r2 = create_review(self.sample_diagnosis)
        edited = self.sample_diagnosis.model_copy(deep=True)
        edited.root_cause = "Correction test"
        modify_review(r2.review_id, edited_diagnosis=edited, reviewer="Rev2", reason="Correction")

        r3 = create_review(self.sample_diagnosis)
        reject_review(r3.review_id, reviewer="Rev3", reason="Rejection test")

        metrics = get_metrics()
        self.assertGreaterEqual(metrics["total_reviews"], 3)
        self.assertGreaterEqual(metrics["accepted_count"], 1)
        self.assertGreaterEqual(metrics["modified_count"], 1)
        self.assertGreaterEqual(metrics["rejected_count"], 1)
        self.assertGreaterEqual(metrics["corrected_ai_responses_count"], 2)


if __name__ == "__main__":
    unittest.main()
