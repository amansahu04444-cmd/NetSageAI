# NetSage AI - AI Engine & Evaluator Module

Handles AI diagnosis generation, Pydantic schema validation, Google Gemini integration, offline mock fallback, and ground-truth evaluation.

## Files
- `structured_output.py`: Pydantic schema definition and JSON validator.
- `diagnosis_engine.py`: Diagnosis orchestrator (Gemini API & Offline Mock).
- `evaluator.py`: Post-diagnosis evaluation against ground truth.
- `test_diagnosis_engine.py`: Unit test suite (6 tests).
