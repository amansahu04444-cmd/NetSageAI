"""
NetSage AI - Structured Output & Schema Validation Module

Defines and validates Pydantic models for AI-generated diagnostic responses.
Ensures strict JSON structure, value bounds, and enum checks.
"""

import json
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, ValidationError

DiagnosisStatusType = Literal["CONFIRMED", "LIKELY", "UNCERTAIN"]
OSILayerType = Literal[
    "Layer 2",
    "Layer 3",
    "Layer 4",
    "Layer 7",
    "Layer 2/3",
    "Layer 3/4",
    "Unknown",
]
RuleStatusType = Literal["ERROR", "PASS", "NOT_CHECKED"]


class RuleCheckerFinding(BaseModel):
    rule: str
    status: RuleStatusType
    message: str


class DiagnosisResult(BaseModel):
    case_id: str
    root_cause: str
    diagnosis_status: DiagnosisStatusType
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0")
    osi_layer: OSILayerType
    evidence: List[str] = Field(default_factory=list)
    rule_checker_findings: List[RuleCheckerFinding] = Field(default_factory=list)
    next_command: Optional[str] = None
    fix_steps: List[str] = Field(default_factory=list)
    explanation: str
    is_mock: bool = Field(default=False, description="Flag indicating if generated via offline mock mode")


class SchemaValidationError(Exception):
    """Custom exception raised when JSON response fails validation."""
    pass


def parse_and_clean_json_str(raw_input: str) -> str:
    """Cleans potential markdown fence blocks (```json ... ```) from LLM output."""
    cleaned = raw_input.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Remove opening ``` or ```json
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove closing ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def validate_diagnosis_response(raw_response: Union[str, Dict[str, Any]]) -> DiagnosisResult:
    """
    Parses and validates raw JSON text or dictionary against the DiagnosisResult Pydantic schema.
    Raises SchemaValidationError if parsing or field validation fails.
    """
    if isinstance(raw_response, str):
        cleaned_json = parse_and_clean_json_str(raw_response)
        try:
            dict_data = json.loads(cleaned_json)
        except json.JSONDecodeError as err:
            raise SchemaValidationError(f"Invalid JSON response string: {str(err)}") from err
    elif isinstance(raw_response, dict):
        dict_data = raw_response
    else:
        raise SchemaValidationError(f"Expected str or dict response, got {type(raw_response)}")

    try:
        validated_result = DiagnosisResult.model_validate(dict_data)
        return validated_result
    except ValidationError as err:
        raise SchemaValidationError(f"Schema validation failed: {str(err)}") from err
