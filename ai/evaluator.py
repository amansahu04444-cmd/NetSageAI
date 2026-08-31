"""
NetSage AI - Diagnostic Evaluator Module

Compares AI-generated diagnostic results against dataset ground truth
(expected_fault, osi_layer, concept) AFTER diagnosis generation.
"""

from dataclasses import dataclass, asdict
import re
from typing import Any, Dict, List, Optional
from ai.structured_output import DiagnosisResult


@dataclass
class EvaluationReport:
    case_id: str
    predicted_root_cause: str
    expected_fault: str
    root_cause_match: bool
    predicted_osi_layer: str
    expected_osi_layer: str
    osi_layer_match: bool
    confidence: float
    diagnosis_status: str
    is_mock: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _check_string_similarity_or_keywords(predicted: str, expected: str) -> bool:
    """Checks if key meaningful words from expected_fault are present in predicted root_cause."""
    pred_clean = predicted.lower()
    exp_clean = expected.lower()

    # Direct substring
    if exp_clean in pred_clean or pred_clean in exp_clean:
        return True

    # Token overlap check (ignoring stopwords)
    stopwords = {"is", "the", "a", "an", "on", "in", "for", "to", "of", "and", "or", "with", "at", "by"}
    exp_words = set(re.findall(r"\w+", exp_clean)) - stopwords
    pred_words = set(re.findall(r"\w+", pred_clean)) - stopwords

    if not exp_words:
        return False

    overlap = exp_words.intersection(pred_words)
    overlap_ratio = len(overlap) / len(exp_words)
    return overlap_ratio >= 0.40


def evaluate_diagnosis(diagnosis: DiagnosisResult, ground_truth_case: Dict[str, Any]) -> EvaluationReport:
    """
    Evaluates a DiagnosisResult against ground-truth case dictionary.
    Ground-truth fields (expected_fault, osi_layer) are strictly evaluated POST-diagnosis.
    """
    expected_fault = str(ground_truth_case.get("expected_fault", "")).strip()
    expected_osi = str(ground_truth_case.get("osi_layer", "")).strip()

    # Root cause match check
    rc_match = _check_string_similarity_or_keywords(diagnosis.root_cause, expected_fault)

    # OSI layer match check (flexible handling e.g. "Layer 3" vs "Layer 3")
    pred_osi_clean = diagnosis.osi_layer.lower()
    exp_osi_clean = expected_osi.lower()
    osi_match = (pred_osi_clean == exp_osi_clean) or (exp_osi_clean in pred_osi_clean) or (pred_osi_clean in exp_osi_clean)

    return EvaluationReport(
        case_id=diagnosis.case_id,
        predicted_root_cause=diagnosis.root_cause,
        expected_fault=expected_fault,
        root_cause_match=rc_match,
        predicted_osi_layer=diagnosis.osi_layer,
        expected_osi_layer=expected_osi,
        osi_layer_match=osi_match,
        confidence=diagnosis.confidence,
        diagnosis_status=diagnosis.diagnosis_status,
        is_mock=diagnosis.is_mock,
    )
