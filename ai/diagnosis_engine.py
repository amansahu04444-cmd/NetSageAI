"""
NetSage AI - AI Diagnosis Engine

Orchestrates network troubleshooting case analysis:
1. Loads case data (strictly withholding ground-truth expected_fault from AI).
2. Executes Phase 2 deterministic rule checker.
3. Constructs structured evidence prompt from prompts/diagnose_prompt.md.
4. Invokes Google Gemini AI API (or deterministic Offline/Mock Mode if API key is unconfigured).
5. Validates raw output using Pydantic schema validator (ai/structured_output.py).
6. Returns validated DiagnosisResult object.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Internal Imports
from data.dataset_loader import load_cases_as_dicts, DatasetLoadError
from checker.rule_checker import run_all_checks, RuleResult
from ai.structured_output import (
    DiagnosisResult,
    RuleCheckerFinding,
    validate_diagnosis_response,
    SchemaValidationError,
)

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
PROMPT_TEMPLATE_PATH = PROMPTS_DIR / "diagnose_prompt.md"

# Recognized placeholder API keys to treat as unconfigured
PLACEHOLDER_KEYS = {
    "",
    "none",
    "null",
    "your_gemini_api_key_here",
    "your_api_key_here",
    "your_key_here",
}


class DiagnosisEngineError(Exception):
    """Raised when diagnosis engine fails to generate or validate a diagnosis."""
    pass


def load_prompt_template() -> str:
    """Loads the main diagnostic prompt template from prompts/diagnose_prompt.md."""
    if not PROMPT_TEMPLATE_PATH.exists():
        raise DiagnosisEngineError(f"Prompt template missing at: {PROMPT_TEMPLATE_PATH}")
    return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def is_api_key_configured() -> bool:
    """Returns True if a valid GEMINI_API_KEY environment variable is configured."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    return bool(key) and key.lower() not in PLACEHOLDER_KEYS


def test_gemini_connection() -> Dict[str, Any]:
    """
    Tests Gemini API key & model connectivity without exposing secret credentials.
    Returns dict with status ('SUCCESS', 'MOCK_MODE', 'FAILED'), model name, and descriptive message.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    if not is_api_key_configured():
        return {
            "status": "MOCK_MODE",
            "configured": False,
            "model": model_name,
            "message": "GEMINI_API_KEY is not configured in .env. System is operating in Offline Mock Mode.",
        }

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents="Connection test. Respond with valid JSON: {\"status\": \"ok\"}",
        )
        if response and getattr(response, "text", None):
            return {
                "status": "SUCCESS",
                "configured": True,
                "model": model_name,
                "message": f"Gemini connection successful! Model: {model_name}",
            }
        else:
            return {
                "status": "FAILED",
                "configured": True,
                "model": model_name,
                "message": "Gemini API returned an empty response.",
            }
    except Exception as api_err:
        try:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=api_key)
            model = legacy_genai.GenerativeModel(model_name)
            res = model.generate_content("Connection test")
            if res and getattr(res, "text", None):
                return {
                    "status": "SUCCESS",
                    "configured": True,
                    "model": model_name,
                    "message": f"Gemini connection successful (via legacy client). Model: {model_name}",
                }
        except Exception:
            pass

        clean_err = str(api_err).replace(api_key, "***")
        return {
            "status": "FAILED",
            "configured": True,
            "model": model_name,
            "message": f"Gemini API connection failed: {clean_err}",
        }


def generate_mock_diagnosis(case: Dict[str, Any], rule_findings: List[RuleResult]) -> DiagnosisResult:
    """
    Generates a deterministic offline mock diagnosis based on case symptom & rule findings.
    Used when GEMINI_API_KEY is not configured or --mock flag is specified.
    """
    case_id = case.get("case_id", "NET-000")
    symptom = case.get("symptom", "")
    show_output = case.get("show_output") or case.get("show_outputs", "")

    # Look for rule checker errors
    error_findings = [r for r in rule_findings if r.status == "ERROR"]

    rule_items = [
        RuleCheckerFinding(rule=r.rule, status=r.status, message=r.message)
        for r in rule_findings if r.status != "NOT_CHECKED"
    ]

    if error_findings:
        err = error_findings[0]
        root_cause = f"Rule Violation ({err.rule}): {err.message}"
        status = "CONFIRMED"
        confidence = 0.95
        evidence = [err.evidence, show_output]
        next_cmd = None
        fix_steps = [
            f"Resolve rule check finding: {err.message}",
            "Verify configuration using standard Cisco IOS show commands.",
        ]
        explanation = f"[MOCK MODE] Diagnostic generated offline using deterministic rule checker finding ({err.rule})."
    else:
        root_cause = f"Potential issue related to: {symptom}"
        status = "LIKELY"
        confidence = 0.70
        evidence = [symptom, show_output] if show_output else [symptom]
        
        # Tailor next command to symptom keywords
        sym_lower = symptom.lower()
        if "vlan" in sym_lower or "trunk" in sym_lower:
            next_cmd = "show vlan brief"
        elif "ospf" in sym_lower or "route" in sym_lower:
            next_cmd = "show ip route"
        elif "acl" in sym_lower or "unreachable" in sym_lower:
            next_cmd = "show access-lists"
        elif "dhcp" in sym_lower:
            next_cmd = "show ip dhcp binding"
        else:
            next_cmd = "show ip interface brief"

        fix_steps = [
            f"Inspect case evidence for: {symptom}",
            f"Execute recommended verification command: {next_cmd}",
        ]
        explanation = "[MOCK MODE] Diagnostic generated offline in mock mode (GEMINI_API_KEY is not set)."

    # Standardize OSI layer estimate for mock
    sym_lower = symptom.lower()
    topo_lower = str(case.get("topology_note", "")).lower()
    if "gateway" in topo_lower or "sub-interface" in topo_lower or "ip" in sym_lower or "ping" in sym_lower:
        osi = "Layer 3"
    elif "dhcp" in sym_lower or "dns" in sym_lower or "wireless" in sym_lower:
        osi = "Layer 7"
    elif "acl" in sym_lower or "port" in sym_lower:
        osi = "Layer 4"
    elif "vlan" in sym_lower or "trunk" in sym_lower or "switch" in sym_lower:
        osi = "Layer 2"
    else:
        osi = "Layer 3"

    return DiagnosisResult(
        case_id=case_id,
        root_cause=root_cause,
        diagnosis_status=status,
        confidence=confidence,
        osi_layer=osi,
        evidence=[e for e in evidence if e],
        rule_checker_findings=rule_items,
        next_command=next_cmd,
        fix_steps=fix_steps,
        explanation=explanation,
        is_mock=True,
    )


def build_prompt_payload(case: Dict[str, Any], rule_findings: List[RuleResult]) -> str:
    """
    Constructs the diagnostic prompt.
    CRITICAL GROUND-TRUTH SAFETY: expected_fault, concept, and osi_layer ground truth are EXCLUDED.
    """
    template = load_prompt_template()

    # Format rule findings
    rule_strs = []
    for r in rule_findings:
        if r.status != "NOT_CHECKED":
            rule_strs.append(f"  * [{r.status}] {r.rule}: {r.message} (Evidence: {r.evidence})")

    findings_text = "\n".join(rule_strs) if rule_strs else "  * No deterministic rule violations detected."

    # Grounding check: strictly exclude expected_fault and concept!
    prompt_str = template.format(
        case_id=case.get("case_id", "NET-000"),
        symptom=case.get("symptom", "N/A"),
        topology_note=case.get("topology_note", "N/A"),
        show_output=case.get("show_output", case.get("show_outputs", "N/A")),
        severity=case.get("severity", "Medium"),
        rule_checker_findings=findings_text,
    )
    return prompt_str


def diagnose_case(
    case_id: str,
    csv_path: Optional[Union[Path, str]] = None,
    force_mock: bool = False,
) -> DiagnosisResult:
    """
    Main entry point to perform AI diagnosis on a specific case.
    """
    cases = load_cases_as_dicts(csv_path)
    target_case = next((c for c in cases if c.get("case_id") == case_id), None)
    if not target_case:
        raise DiagnosisEngineError(f"Case '{case_id}' not found in dataset.")

    # 1. Run deterministic rule checker
    rule_findings = run_all_checks(target_case)

    # 2. Check API key configuration
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

    if force_mock or not is_api_key_configured():
        # Return deterministic mock result
        return generate_mock_diagnosis(target_case, rule_findings)

    # 3. Build ground-truth protected prompt payload
    prompt_text = build_prompt_payload(target_case, rule_findings)

    # 4. Invoke Google Gemini API
    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt_text,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
            ),
        )
        raw_output = response.text
    except Exception as api_err:
        # Fallback to google.generativeai if genai module unavailable or error occurs
        try:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=api_key)
            model = legacy_genai.GenerativeModel(model_name)
            res = model.generate_content(prompt_text)
            raw_output = res.text
        except Exception as legacy_err:
            clean_err = str(api_err).replace(api_key, "***")
            # If real API call fails, fall back to Mock mode gracefully with explanation
            mock_res = generate_mock_diagnosis(target_case, rule_findings)
            mock_res.explanation = f"[FALLBACK MOCK] Gemini API call failed ({clean_err}). Operating in fallback mode."
            return mock_res

    # 5. Parse and validate response schema
    try:
        validated_diagnosis = validate_diagnosis_response(raw_output)
        return validated_diagnosis
    except SchemaValidationError as val_err:
        raise DiagnosisEngineError(f"AI response failed schema validation: {str(val_err)}") from val_err
