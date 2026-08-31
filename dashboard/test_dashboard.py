"""
Unit Tests for NetSage AI Phase 5 Dashboard & Responsible AI Analytics

Verifies:
1. Dataset summary and health calculations.
2. Category and severity distribution calculations.
3. Review metrics (Accepted, Modified, Rejected).
4. Agreement rate, Correction rate, and Rejection rate formulas.
5. Exclusion of PENDING reviews from completed reviews denominator.
6. Graceful handling of empty review data.
7. Mock vs real AI labeling checks.
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import unittest
from ai.structured_output import DiagnosisResult
from review.review_workflow import ReviewRecord
from dashboard.analytics import (
    get_case_dataset_summary,
    compute_responsible_ai_metrics,
    get_corrected_review_records,
)


class TestDashboardAnalytics(unittest.TestCase):

    def setUp(self):
        self.mock_diagnosis = DiagnosisResult(
            case_id="NET-001",
            root_cause="Test root cause",
            diagnosis_status="CONFIRMED",
            confidence=0.95,
            osi_layer="Layer 3",
            evidence=["Test evidence"],
            rule_checker_findings=[],
            next_command=None,
            fix_steps=["Test fix"],
            explanation="Test explanation",
            is_mock=True,
        )

    def test_case_dataset_summary_metrics(self):
        summary = get_case_dataset_summary()
        self.assertEqual(summary["total_cases"], 30)
        self.assertGreaterEqual(summary["categories_count"], 15)
        self.assertIn("High", summary["severity_distribution"])
        self.assertGreater(summary["total_rule_checks_evaluated"], 0)

    def test_responsible_ai_metrics_formulas(self):
        # 1 Accepted, 1 Modified, 1 Rejected, 2 Pending (Total 5 reviews, Completed 3)
        r_acc = ReviewRecord(case_id="NET-001", status="ACCEPTED", ai_diagnosis=self.mock_diagnosis)
        r_mod = ReviewRecord(case_id="NET-002", status="MODIFIED", ai_diagnosis=self.mock_diagnosis)
        r_rej = ReviewRecord(case_id="NET-003", status="REJECTED", ai_diagnosis=self.mock_diagnosis)
        r_pen1 = ReviewRecord(case_id="NET-004", status="PENDING", ai_diagnosis=self.mock_diagnosis)
        r_pen2 = ReviewRecord(case_id="NET-005", status="PENDING", ai_diagnosis=self.mock_diagnosis)

        records = [r_acc, r_mod, r_rej, r_pen1, r_pen2]
        metrics = compute_responsible_ai_metrics(records)

        self.assertEqual(metrics["total_reviews"], 5)
        self.assertEqual(metrics["completed_count"], 3)
        self.assertEqual(metrics["pending_count"], 2)
        self.assertEqual(metrics["accepted_count"], 1)
        self.assertEqual(metrics["modified_count"], 1)
        self.assertEqual(metrics["rejected_count"], 1)

        # Formula checks: 1/3 = 33.33%
        self.assertAlmostEqual(metrics["agreement_rate_pct"], 33.333, places=2)
        self.assertAlmostEqual(metrics["correction_rate_pct"], 33.333, places=2)
        self.assertAlmostEqual(metrics["rejection_rate_pct"], 33.333, places=2)
        self.assertEqual(metrics["corrected_ai_responses_count"], 2)

    def test_pending_reviews_excluded_from_denominator(self):
        # 2 Pending reviews, 0 completed reviews
        records = [
            ReviewRecord(case_id="NET-001", status="PENDING", ai_diagnosis=self.mock_diagnosis),
            ReviewRecord(case_id="NET-002", status="PENDING", ai_diagnosis=self.mock_diagnosis),
        ]
        metrics = compute_responsible_ai_metrics(records)
        self.assertEqual(metrics["completed_count"], 0)
        self.assertEqual(metrics["agreement_rate_str"], "N/A")
        self.assertEqual(metrics["correction_rate_str"], "N/A")
        self.assertEqual(metrics["rejection_rate_str"], "N/A")

    def test_empty_review_records(self):
        metrics = compute_responsible_ai_metrics([])
        self.assertEqual(metrics["total_reviews"], 0)
        self.assertEqual(metrics["completed_count"], 0)
        self.assertEqual(metrics["agreement_rate_str"], "N/A")

    def test_corrected_review_records_filtering(self):
        records = [
            ReviewRecord(case_id="NET-001", status="ACCEPTED", ai_diagnosis=self.mock_diagnosis),
            ReviewRecord(case_id="NET-002", status="MODIFIED", ai_diagnosis=self.mock_diagnosis),
            ReviewRecord(case_id="NET-003", status="REJECTED", ai_diagnosis=self.mock_diagnosis),
        ]
        corrected = get_corrected_review_records(records)
        self.assertEqual(len(corrected), 2)
        statuses = [r.status for r in corrected]
        self.assertIn("MODIFIED", statuses)
        self.assertIn("REJECTED", statuses)
        self.assertNotIn("ACCEPTED", statuses)

    def test_mock_vs_real_labeling(self):
        self.assertTrue(self.mock_diagnosis.is_mock)
        real_diagnosis = self.mock_diagnosis.model_copy()
        real_diagnosis.is_mock = False
        self.assertFalse(real_diagnosis.is_mock)

        # Verify tracking of real vs mock counts in compute_responsible_ai_metrics
        r_mock = ReviewRecord(case_id="NET-001", status="MODIFIED", ai_diagnosis=self.mock_diagnosis)
        r_real = ReviewRecord(case_id="NET-002", status="MODIFIED", ai_diagnosis=real_diagnosis)

        metrics = compute_responsible_ai_metrics([r_mock, r_real])
        self.assertEqual(metrics["real_reviews_count"], 1)
        self.assertEqual(metrics["mock_reviews_count"], 1)
        self.assertEqual(metrics["real_corrected_count"], 1)
        self.assertEqual(metrics["mock_corrected_count"], 1)


if __name__ == "__main__":
    unittest.main()
