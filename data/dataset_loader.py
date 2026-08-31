"""
Dataset Loader & Validation Utility for NetSage AI.

This module provides dataset loading, schema normalization, and validation report
generation for network troubleshooting cases.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

# Default file paths
DATA_DIR = Path(__file__).parent
DEFAULT_CSV_PATH = DATA_DIR / "cases.csv"

# Schema mapping definitions
COLUMN_MAPPING = {
    "show_outputs": "show_output",
    "concept_tag": "concept",
}

EXPECTED_SCHEMA = [
    "case_id",
    "symptom",
    "topology_note",
    "show_output",
    "expected_fault",
    "osi_layer",
    "concept",
    "severity",
]

# Raw columns required before normalization (either original or already mapped name)
REQUIRED_RAW_FIELDS = [
    "case_id",
    "symptom",
    "topology_note",
    "expected_fault",
    "osi_layer",
    "severity",
]


@dataclass
class DatasetValidationResult:
    is_valid: bool
    total_cases: int
    raw_columns: List[str]
    normalized_columns: List[str]
    missing_expected_columns: List[str]
    missing_values_by_column: Dict[str, int]
    duplicate_case_ids: List[str]
    concept_distribution: Dict[str, int]
    severity_distribution: Dict[str, int]
    osi_layer_distribution: Dict[str, int]
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class DatasetLoadError(Exception):
    """Custom exception raised when dataset loading or validation fails critically."""
    pass


def load_raw_dataset(csv_path: Optional[Path | str] = None) -> pd.DataFrame:
    """
    Loads the raw CSV dataset from disk without altering original schema or content.
    """
    target_path = Path(csv_path) if csv_path else DEFAULT_CSV_PATH
    if not target_path.exists():
        raise DatasetLoadError(f"Dataset file not found at: {target_path.resolve()}")
    try:
        df = pd.read_csv(target_path)
        return df
    except Exception as e:
        raise DatasetLoadError(f"Failed to read CSV file '{target_path}': {str(e)}") from e


def load_cases(csv_path: Optional[Path | str] = None, normalize: bool = True) -> pd.DataFrame:
    """
    Loads cases dataset and optionally normalizes column headers according to schema mapping.
    Missing string values are safely sanitized.
    """
    df = load_raw_dataset(csv_path)
    if normalize:
        # Create mapped columns without destroying original data logic
        df = df.rename(columns=COLUMN_MAPPING)

    # Strip whitespace from string columns if present
    for col in df.select_dtypes(include=["object", "string"]).columns:
        df[col] = df[col].astype(str).str.strip()

    return df


def load_cases_as_dicts(csv_path: Optional[Path | str] = None) -> List[Dict[str, Any]]:
    """
    Loads cases as a list of dictionaries with normalized schema.
    """
    df = load_cases(csv_path, normalize=True)
    return df.to_dict(orient="records")


def validate_dataset(csv_path: Optional[Path | str] = None) -> DatasetValidationResult:
    """
    Performs full schema and data validation on the cases dataset.
    """
    target_path = Path(csv_path) if csv_path else DEFAULT_CSV_PATH
    errors: List[str] = []
    warnings: List[str] = []

    try:
        raw_df = load_raw_dataset(target_path)
    except DatasetLoadError as err:
        return DatasetValidationResult(
            is_valid=False,
            total_cases=0,
            raw_columns=[],
            normalized_columns=[],
            missing_expected_columns=EXPECTED_SCHEMA,
            missing_values_by_column={},
            duplicate_case_ids=[],
            concept_distribution={},
            severity_distribution={},
            osi_layer_distribution={},
            errors=[str(err)],
            warnings=[],
        )

    raw_columns = raw_df.columns.tolist()

    # Check normalized columns
    normalized_df = raw_df.rename(columns=COLUMN_MAPPING)
    normalized_columns = normalized_df.columns.tolist()

    # Determine missing expected columns
    missing_expected = [col for col in EXPECTED_SCHEMA if col not in normalized_columns]
    if missing_expected:
        errors.append(f"Missing required schema columns (after mapping): {missing_expected}")

    # Check for empty dataset
    total_cases = len(raw_df)
    if total_cases == 0:
        errors.append("Dataset contains 0 rows.")

    # Check missing values
    missing_values = normalized_df.isnull().sum().to_dict()
    for col, null_count in missing_values.items():
        if null_count > 0:
            warnings.append(f"Column '{col}' has {null_count} missing (NaN/null) values.")

    # Check duplicate case_id
    duplicate_ids: List[str] = []
    if "case_id" in normalized_df.columns:
        dups = normalized_df[normalized_df["case_id"].duplicated(keep=False)]["case_id"].unique().tolist()
        duplicate_ids = [str(d) for d in dups]
        if duplicate_ids:
            errors.append(f"Duplicate case_id values found: {duplicate_ids}")

    # Distributions
    concept_col = "concept" if "concept" in normalized_df.columns else "concept_tag"
    concept_dist = (
        normalized_df[concept_col].value_counts().to_dict()
        if concept_col in normalized_df.columns
        else {}
    )

    severity_dist = (
        normalized_df["severity"].value_counts().to_dict()
        if "severity" in normalized_df.columns
        else {}
    )

    osi_dist = (
        normalized_df["osi_layer"].value_counts().to_dict()
        if "osi_layer" in normalized_df.columns
        else {}
    )

    is_valid = len(errors) == 0

    return DatasetValidationResult(
        is_valid=is_valid,
        total_cases=total_cases,
        raw_columns=raw_columns,
        normalized_columns=normalized_columns,
        missing_expected_columns=missing_expected,
        missing_values_by_column=missing_values,
        duplicate_case_ids=duplicate_ids,
        concept_distribution=concept_dist,
        severity_distribution=severity_dist,
        osi_layer_distribution=osi_dist,
        errors=errors,
        warnings=warnings,
    )


def generate_report(csv_path: Optional[Path | str] = None) -> str:
    """
    Generates a formatted markdown/terminal report summarizing the dataset validation results.
    """
    res = validate_dataset(csv_path)

    lines = []
    lines.append("=" * 60)
    lines.append("           NETSAGE AI - DATASET VALIDATION REPORT           ")
    lines.append("=" * 60)
    lines.append(f"Dataset Path      : {DEFAULT_CSV_PATH if not csv_path else Path(csv_path)}")
    lines.append(f"Validation Status : {'PASSED [VALID]' if res.is_valid else 'FAILED [INVALID]'}")
    lines.append(f"Total Cases Count : {res.total_cases}")
    lines.append("")

    lines.append("--- Column Mapping & Schema ---")
    lines.append(f"Raw CSV Columns   : {', '.join(res.raw_columns)}")
    lines.append(f"Normalized Schema : {', '.join(res.normalized_columns)}")
    if COLUMN_MAPPING:
        lines.append("Internal Column Mappings Applied:")
        for orig, norm in COLUMN_MAPPING.items():
            if orig in res.raw_columns:
                lines.append(f"  * '{orig}' -> '{norm}'")
    lines.append(f"Missing Schema Columns: {res.missing_expected_columns if res.missing_expected_columns else 'None'}")
    lines.append("")

    lines.append("--- Data Integrity Check ---")
    lines.append("Missing Values per Column:")
    for col, count in res.missing_values_by_column.items():
        lines.append(f"  * {col:15s}: {count} missing")
    lines.append(f"Duplicate Case IDs: {res.duplicate_case_ids if res.duplicate_case_ids else 'None'}")
    lines.append("")

    lines.append("--- Issue / Concept Distribution ---")
    for concept, count in res.concept_distribution.items():
        pct = (count / res.total_cases * 100) if res.total_cases > 0 else 0
        lines.append(f"  * {concept:22s}: {count:2d} case(s) ({pct:5.1f}%)")
    lines.append("")

    lines.append("--- Severity Distribution ---")
    for sev, count in res.severity_distribution.items():
        pct = (count / res.total_cases * 100) if res.total_cases > 0 else 0
        lines.append(f"  * {sev:10s}: {count:2d} case(s) ({pct:5.1f}%)")
    lines.append("")

    lines.append("--- OSI Layer Distribution ---")
    for layer, count in res.osi_layer_distribution.items():
        pct = (count / res.total_cases * 100) if res.total_cases > 0 else 0
        lines.append(f"  * {layer:10s}: {count:2d} case(s) ({pct:5.1f}%)")
    lines.append("")

    if res.errors:
        lines.append("--- ERRORS ---")
        for err in res.errors:
            lines.append(f"  [ERROR] {err}")
        lines.append("")

    if res.warnings:
        lines.append("--- WARNINGS ---")
        for warn in res.warnings:
            lines.append(f"  [WARNING] {warn}")
        lines.append("")

    lines.append("=" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    report_text = generate_report()
    print(report_text)
