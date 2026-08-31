"""
Unit Tests for NetSage AI Diagnosis Engine & Structured Output Validation

Verifies:
1. Pydantic schema validation for valid/invalid JSON responses.
2. Ground-truth leakage prevention (expected_fault absent from prompt).
3. Offline Mock mode diagnosis generation.
4. Evaluation module matching logic.
"""

import unittest
from ai.structured_output import (
    DiagnosisResult,
    validate_diagnosis_response,
    SchemaValidationError,
)
from ai.diagnosis_engine import (
    build_prompt_payload,
    generate_mock_diagnosis,
    diagnose_case,
)
from ai.evaluator import evaluate_diagnosis
from checker.rule_checker import run_all_checks


class TestDiagnosisEngine(unittest.TestCase):

    def setUp(self):
        self.sample_case = {
            "case_id": "NET-001",
            "symptom": "PC1 cannot reach Server1 in VLAN 30",
            "topology_note": "PC1 on Fa0/1 (VLAN 10); Gateway on Router Sub-interface Gi0/0.10",
            "show_output": "GigabitEthernet0/0.10 is administratively down line protocol is down",
            "expected_fault": "Sub-interface administratively down",
            "concept": "Inter-VLAN Routing",
            "osi_layer": "Layer 3",
            "severity": "High",
        }

    # -------------------------------------------------------------------------
    # 1. Schema Validation Tests
    # -------------------------------------------------------------------------
    def test_valid_schema_parsing(self):
        valid_json = """
        {
            "case_id": "NET-001",
            "root_cause": "Sub-interface GigabitEthernet0/0.10 is down.",
            "diagnosis_status": "CONFIRMED",
            "confidence": 0.98,
            "osi_layer": "Layer 3",
            "evidence": ["GigabitEthernet0/0.10 is administratively down"],
            "rule_checker_findings": [
                {"rule": "interface_status", "status": "ERROR", "message": "Interface down"}
            ],
            "next_command": null,
            "fix_steps": ["no shutdown"],
            "explanation": "Interface state is down in show output."
        }
        """
        result = validate_diagnosis_response(valid_json)
        self.assertIsInstance(result, DiagnosisResult)
        self.assertEqual(result.case_id, "NET-001")
        self.assertEqual(result.diagnosis_status, "CONFIRMED")
        self.assertEqual(result.confidence, 0.98)

    def test_invalid_confidence_range(self):
        invalid_json = """
        {
            "case_id": "NET-001",
            "root_cause": "Test",
            "diagnosis_status": "CONFIRMED",
            "confidence": 1.5,
            "osi_layer": "Layer 3",
            "evidence": [],
            "rule_checker_findings": [],
            "next_command": null,
            "fix_steps": [],
            "explanation": "Invalid confidence test"
        }
        """
        with self.assertRaises(SchemaValidationError):
            validate_diagnosis_response(invalid_json)

    def test_invalid_status_enum(self):
        invalid_json = """
        {
            "case_id": "NET-001",
            "root_cause": "Test",
            "diagnosis_status": "GUESSING",
            "confidence": 0.5,
            "osi_layer": "Layer 3",
            "evidence": [],
            "rule_checker_findings": [],
            "next_command": null,
            "fix_steps": [],
            "explanation": "Invalid enum test"
        }
        """
        with self.assertRaises(SchemaValidationError):
            validate_diagnosis_response(invalid_json)

    # -------------------------------------------------------------------------
    # 2. Ground-Truth Leakage Prevention Test
    # -------------------------------------------------------------------------
    def test_prompt_building_no_ground_truth_leakage(self):
        findings = run_all_checks(self.sample_case)
        prompt = build_prompt_payload(self.sample_case, findings)

        # Confirm case_id, symptom, topology_note, show_output are present
        self.assertIn("NET-001", prompt)
        self.assertIn("PC1 cannot reach Server1", prompt)

        # CONFIRM expected_fault ("Sub-interface administratively down") is NOT in prompt
        self.assertNotIn("Sub-interface administratively down", prompt)
        self.assertNotIn("Inter-VLAN Routing", prompt)

    # -------------------------------------------------------------------------
    # 3. Mock Mode Diagnosis Test
    # -------------------------------------------------------------------------
    def test_mock_diagnosis_generation(self):
        result = diagnose_case("NET-001", force_mock=True)
        self.assertIsInstance(result, DiagnosisResult)
        self.assertEqual(result.case_id, "NET-001")
        self.assertTrue(result.is_mock)
        self.assertIn("[MOCK MODE]", result.explanation)

    # -------------------------------------------------------------------------
    # 4. Evaluator Test
    # -------------------------------------------------------------------------
    def test_evaluator_matching(self):
        diagnosis = generate_mock_diagnosis(self.sample_case, run_all_checks(self.sample_case))
        eval_report = evaluate_diagnosis(diagnosis, self.sample_case)

        self.assertEqual(eval_report.case_id, "NET-001")
        self.assertTrue(eval_report.osi_layer_match)
        self.assertIsInstance(eval_report.root_cause_match, bool)


if __name__ == "__main__":
    unittest.main()
