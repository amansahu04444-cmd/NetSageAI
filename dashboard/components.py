"""
NetSage AI - Streamlit Dashboard UI Components Module

Modular UI renderer components for Phase 5:
- Top-level KPI cards
- Issue distribution & severity analytics
- Review outcome & Responsible AI metrics
- Corrected AI responses view
- Case Explorer (ground-truth evaluation only)
- Dataset health summary
"""

import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import streamlit as st
import pandas as pd
from typing import Any, Dict, List
from data.dataset_loader import load_cases_as_dicts, load_cases
from ai.diagnosis_engine import diagnose_case
from ai.evaluator import evaluate_diagnosis
from review.audit_logger import load_all_review_records
from dashboard.analytics import (
    get_case_dataset_summary,
    compute_responsible_ai_metrics,
    get_corrected_review_records,
    seed_demo_corrected_reviews,
)


def render_kpi_cards(metrics: Dict[str, Any], dataset_summary: Dict[str, Any]):
    """Renders top-level executive KPI cards."""
    st.subheader("📌 Key Performance Indicators (KPIs)")
    k1, k2, k3, k4, k5, k6, k7 = st.columns(7)

    k1.metric("Total Cases", dataset_summary["total_cases"])
    k2.metric("Total Reviews", metrics["total_reviews"])
    k3.metric("AI Accepted", metrics["accepted_count"])
    k4.metric("AI Modified", metrics["modified_count"])
    k5.metric("AI Rejected", metrics["rejected_count"])
    k6.metric("Agreement Rate", metrics["agreement_rate_str"])
    k7.metric("Corrected AI", metrics["corrected_ai_responses_count"])


def render_issue_analytics(dataset_summary: Dict[str, Any]):
    """Renders issue category/concept distribution analytics chart."""
    st.subheader("🏷️ Issue Category Distribution (cases.csv)")

    cat_dist = dataset_summary["category_distribution"]
    if cat_dist:
        df_cat = pd.DataFrame(
            list(cat_dist.items()), columns=["Category / Concept", "Case Count"]
        ).sort_values(by="Case Count", ascending=False)
        st.bar_chart(df_cat.set_index("Category / Concept"))
    else:
        st.info("No category data found in dataset.")


def render_severity_analytics(dataset_summary: Dict[str, Any]):
    """Renders severity distribution analytics chart."""
    st.subheader("⚠️ Case Severity Distribution")

    sev_dist = dataset_summary["severity_distribution"]
    if sev_dist:
        df_sev = pd.DataFrame(
            list(sev_dist.items()), columns=["Severity Level", "Count"]
        )
        st.bar_chart(df_sev.set_index("Severity Level"))
    else:
        st.info("No severity data found in dataset.")


def render_review_outcome_analytics(metrics: Dict[str, Any]):
    """Renders review outcome analytics chart."""
    st.subheader("📊 Human Review Outcome Breakdown")

    outcome_data = {
        "Outcome": ["ACCEPTED", "MODIFIED", "REJECTED", "PENDING"],
        "Count": [
            metrics["accepted_count"],
            metrics["modified_count"],
            metrics["rejected_count"],
            metrics["pending_count"],
        ],
    }
    df_outcome = pd.DataFrame(outcome_data)
    st.bar_chart(df_outcome.set_index("Outcome"))


def render_responsible_ai_section(metrics: Dict[str, Any]):
    """Renders dedicated Responsible AI analytics metrics & explanations."""
    st.subheader("🛡️ Responsible AI & Governance Analytics")

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("AI-Human Agreement Rate", metrics["agreement_rate_str"], help="ACCEPTED / (ACCEPTED + MODIFIED + REJECTED) * 100")
    r2.metric("Human Correction Rate", metrics["correction_rate_str"], help="MODIFIED / (ACCEPTED + MODIFIED + REJECTED) * 100")
    r3.metric("Human Rejection Rate", metrics["rejection_rate_str"], help="REJECTED / (ACCEPTED + MODIFIED + REJECTED) * 100")
    r4.metric("Total Corrected AI Responses", metrics["corrected_ai_responses_count"])

    st.markdown("##### 🏷️ Data Origin & Audit Breakdown")
    d1, d2 = st.columns(2)
    d1.metric("Real Corrected AI Responses", metrics.get("real_corrected_count", 0))
    d2.metric("Demo / Mock Corrected Responses", metrics.get("mock_corrected_count", 0), help="Generated during offline test/mock runs")

    if metrics.get("real_corrected_count", 0) == 0:
        st.info(
            f"ℹ️ **DATA ORIGIN NOTICE**: Real corrected AI responses: **0** | Demo/Mock corrected responses: **{metrics.get('mock_corrected_count', 0)}**. "
            "Existing review records were generated during offline test/mock runs and are tagged **MOCK / DEMO DATA**."
        )

    st.markdown("""
    **Responsible AI Metric Definitions**:
    * **Agreement Rate**: Percentage of completed human reviews where the operator accepted the AI recommendation verbatim.
    * **Correction Rate**: Percentage of completed reviews where the operator modified the AI diagnosis for precision.
    * **Rejection Rate**: Percentage of completed reviews where the operator rejected the AI diagnosis as inaccurate.
    * **Note**: PENDING reviews are excluded from the denominator to ensure formula precision.
    """)


def render_corrected_responses_table(records: Any):
    """Renders detailed table of corrected (MODIFIED / REJECTED) AI responses."""
    st.subheader("✏️ Corrected AI Responses (Human Modifications & Rejections)")

    corrected_records = get_corrected_review_records(records)
    if not corrected_records:
        st.info("No corrected AI responses logged yet.")
        return

    real_count = sum(1 for r in corrected_records if not getattr(r.ai_diagnosis, "is_mock", False))
    mock_count = sum(1 for r in corrected_records if getattr(r.ai_diagnosis, "is_mock", False))

    st.markdown(
        f"Displaying **{len(corrected_records)}** corrected AI response records "
        f"(Real: **{real_count}** | Demo/Mock: **{mock_count}**):"
    )

    table_rows = []
    for r in corrected_records:
        ai_rc = r.ai_diagnosis.root_cause
        hum_rc = r.human_diagnosis.root_cause if r.human_diagnosis else "N/A (Rejected)"
        is_mock_flag = getattr(r.ai_diagnosis, "is_mock", False)
        data_type = "MOCK / DEMO" if is_mock_flag else "REAL GEMINI"
        table_rows.append({
            "Review ID": r.review_id,
            "Case ID": r.case_id,
            "Status": r.status,
            "Data Origin": data_type,
            "Reviewer": r.reviewer or "N/A",
            "AI Root Cause": ai_rc,
            "Human Root Cause": hum_rc,
            "Reason / Note": r.reason,
            "Timestamp": r.reviewed_at or r.created_at,
        })

    df_corrected = pd.DataFrame(table_rows)
    st.dataframe(df_corrected, use_container_width=True)


def render_case_explorer():
    """Renders interactive Case Explorer with clearly labeled Ground Truth."""
    st.subheader("🔍 Case Explorer & Ground-Truth Inspector")

    cases = load_cases_as_dicts()
    case_labels = {f"{c['case_id']} | {c['symptom']}": c for c in cases}
    selected_label = st.selectbox("Select Case to Inspect:", list(case_labels.keys()), key="case_exp_select")
    c = case_labels[selected_label]

    exp1, exp2 = st.columns(2)
    with exp1:
        st.markdown(f"**Case ID**: `{c['case_id']}`")
        st.markdown(f"**Category / Concept**: `{c['concept']}`")
        st.markdown(f"**Severity**: `{c['severity']}`")
        st.markdown(f"**Symptom**: {c['symptom']}")
        st.markdown(f"**Topology Note**: {c['topology_note']}")

    with exp2:
        st.markdown(f"**Show Command Output**: `{c['show_output']}`")
        st.markdown(f"**OSI Layer**: `{c['osi_layer']}`")
        st.error(f"🔒 **Expected Fault**: `{c['expected_fault']}`")
        st.caption("⚠️ **GROUND TRUTH NOTICE**: Expected Fault is strictly for post-diagnosis evaluation ONLY. It is NEVER supplied to Gemini during diagnosis.")


def render_dataset_health(dataset_summary: Dict[str, Any]):
    """Renders dataset health and data quality statistics."""
    st.subheader("🩺 Dataset Health & Quality Audit")

    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Total Dataset Cases", dataset_summary["total_cases"])
    h2.metric("Categories Covered", dataset_summary["categories_count"])
    h3.metric("Cases with Rule Violations", dataset_summary["cases_with_rule_errors"])
    h4.metric("Rule Errors Detected", dataset_summary["total_rule_errors_detected"])

    st.markdown(f"- Total Rule Checks Evaluated: `{dataset_summary['total_rule_checks_evaluated']}`")
    st.markdown(f"- Cases with NO Rule Findings (`NOT_CHECKED`): `{dataset_summary['cases_all_not_checked']}`")


def render_ai_evaluation_section():
    """Renders post-diagnosis evaluation performance against ground truth."""
    st.subheader("🎯 AI Evaluation Analytics (Post-Diagnosis Ground Truth Comparison)")

    cases = load_cases_as_dicts()
    st.caption(f"Evaluates dataset accuracy across all {len(cases)} cases.")

    if st.button("▶️ Run Full Dataset Evaluation (Mock Mode)", type="secondary"):
        with st.spinner("Evaluating diagnoses against ground truth..."):
            eval_reports = []
            rc_matches = 0
            osi_matches = 0
            for c in cases:
                diag = diagnose_case(c["case_id"], force_mock=True)
                rep = evaluate_diagnosis(diag, c)
                eval_reports.append(rep)
                if rep.root_cause_match:
                    rc_matches += 1
                if rep.osi_layer_match:
                    osi_matches += 1

            total = len(eval_reports)
            e1, e2, e3 = st.columns(3)
            e1.metric("Evaluated Cases", total)
            e2.metric("Root Cause Match Rate", f"{(rc_matches/total*100):.1f}%")
            e3.metric("OSI Layer Match Rate", f"{(osi_matches/total*100):.1f}%")

            st.info("🏷️ **EXECUTION MODE**: MOCK MODE (Deterministic evaluation using Phase 2 rule checker evidence).")
