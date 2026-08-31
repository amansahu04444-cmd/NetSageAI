"""
NetSage AI - Streamlit Application Entry Point

Combines:
- Phase 4: Human Review Center (Accept / Edit / Reject)
- Phase 5: Executive Dashboard & Responsible AI Analytics
"""

import os
import json
import streamlit as st
import pandas as pd
from pathlib import Path

# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# NetSage AI Module Imports
from data.dataset_loader import load_cases_as_dicts
from ai.diagnosis_engine import (
    diagnose_case,
    is_api_key_configured,
    test_gemini_connection,
)
from ai.structured_output import DiagnosisResult
from review.review_service import (
    create_review,
    accept_review,
    modify_review,
    reject_review,
    list_reviews,
)
from review.audit_logger import load_all_review_records
from dashboard.analytics import (
    get_case_dataset_summary,
    compute_responsible_ai_metrics,
    get_corrected_review_records,
    seed_demo_corrected_reviews,
)
from dashboard.components import (
    render_kpi_cards,
    render_issue_analytics,
    render_severity_analytics,
    render_review_outcome_analytics,
    render_responsible_ai_section,
    render_corrected_responses_table,
    render_case_explorer,
    render_dataset_health,
    render_ai_evaluation_section,
)

# Page configuration
st.set_page_config(
    page_title="NetSage AI - Network Troubleshooting Intelligence",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state():
    if "current_review" not in st.session_state:
        st.session_state["current_review"] = None


init_session_state()

# Header & Safety Banner
st.title("🌐 NetSage AI — Network Troubleshooting Intelligence")
st.caption("AI-assisted Cisco / Packet Tracer network troubleshooting helper with mandatory human review.")

st.warning(
    "⚠️ **SAFETY RESTRICTION NOTICE**: NetSage AI operates strictly as a passive decision-support tool. "
    "All AI recommendations require explicit human approval and will **NEVER automatically execute Cisco IOS commands** "
    "or alter network device configurations."
)

# Load current datasets & review metrics
dataset_summary = get_case_dataset_summary()
all_reviews = load_all_review_records()
metrics = compute_responsible_ai_metrics(all_reviews)

# Sidebar Navigation & Settings
st.sidebar.header("Navigation")
nav_choice = st.sidebar.radio(
    "Go to",
    [
        "📊 Executive Dashboard",
        "🛠️ Human Review Center",
        "📋 Review History & Audit Log",
        "🛡️ Responsible AI & Human Corrections",
        "🔍 Case Explorer & Dataset Health",
        "🎯 AI Evaluation Analytics",
    ],
)

st.sidebar.divider()
st.sidebar.subheader("⚙️ AI Diagnosis Configuration")

has_gemini_key = is_api_key_configured()
gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

if has_gemini_key:
    st.sidebar.success(f"🟢 Gemini API: Configured ({gemini_model_name})")
    default_mock_mode = False
else:
    st.sidebar.info("🟡 Gemini API: Not configured — using Mock Mode")
    default_mock_mode = True

use_mock_mode = st.sidebar.checkbox(
    "Use Offline Mock Mode",
    value=default_mock_mode,
    help="Force offline mock diagnosis without making live Gemini API calls."
)

reviewer_default_name = st.sidebar.text_input("Reviewer Identity", value="Network Engineer")

if st.sidebar.button("🧪 Test Gemini Connection"):
    with st.sidebar.spinner("Testing Gemini API connection..."):
        conn_res = test_gemini_connection()
        if conn_res["status"] == "SUCCESS":
            st.sidebar.success(conn_res["message"])
        elif conn_res["status"] == "MOCK_MODE":
            st.sidebar.info(conn_res["message"])
        else:
            st.sidebar.error(conn_res["message"])

with st.sidebar.expander("ℹ️ How to enable Gemini API"):
    st.markdown("""
    **To enable real Gemini API**:
    1. Create a `.env` file in project root.
    2. Add:
       `GEMINI_API_KEY=your_key`
       `GEMINI_MODEL=gemini-3.6-flash`
    3. Restart Streamlit.
    4. Uncheck **Use Offline Mock Mode**.
    """)


# =============================================================================
# TAB 1: EXECUTIVE DASHBOARD
# =============================================================================
if nav_choice == "📊 Executive Dashboard":
    st.header("📊 Executive Analytics Dashboard")

    # Render Top KPI Cards
    render_kpi_cards(metrics, dataset_summary)

    st.divider()

    # Visual Analytics Grid
    col_a, col_b = st.columns(2)
    with col_a:
        render_issue_analytics(dataset_summary)
    with col_b:
        render_severity_analytics(dataset_summary)

    st.divider()

    col_c, col_d = st.columns(2)
    with col_c:
        render_review_outcome_analytics(metrics)
    with col_d:
        render_responsible_ai_section(metrics)


# =============================================================================
# TAB 2: HUMAN REVIEW CENTER
# =============================================================================
elif nav_choice == "🛠️ Human Review Center":
    st.header("🛠️ Human Review Center")
    st.caption("Review AI diagnostic recommendations before authorizing human configuration steps.")

    cases = load_cases_as_dicts()
    case_options = {f"{c['case_id']} | {c['concept']} | {c['symptom']}": c for c in cases}
    selected_label = st.selectbox("Select Case from Dataset:", list(case_options.keys()))
    selected_case = case_options[selected_label]
    case_id = selected_case["case_id"]

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Case ID**: `{case_id}`")
        st.markdown(f"**Symptom**: {selected_case['symptom']}")
        st.markdown(f"**Topology Note**: {selected_case['topology_note']}")
    with col2:
        st.markdown(f"**Show Output**: `{selected_case['show_output']}`")
        st.markdown(f"**Severity**: `{selected_case['severity']}`")

    st.divider()

    if st.button("🚀 Generate AI Diagnosis for Review", type="primary"):
        with st.spinner("Executing Phase 2 Rule Checker & Phase 3 AI Diagnosis Engine..."):
            try:
                diag = diagnose_case(case_id, force_mock=use_mock_mode)
                review_rec = create_review(diag, reviewer=reviewer_default_name)
                st.session_state["current_review"] = review_rec
                st.success(f"New review record created: `{review_rec.review_id}` (Status: PENDING)")
            except Exception as err:
                st.error(f"Failed generating diagnosis: {str(err)}")

    rec = st.session_state.get("current_review")
    if rec and rec.case_id == case_id:
        st.subheader(f"Review Case `{rec.case_id}` (Review ID: `{rec.review_id}`)")

        status_color = "orange" if rec.status == "PENDING" else "green" if rec.status == "ACCEPTED" else "blue" if rec.status == "MODIFIED" else "red"
        st.markdown(f"**Review Status**: :{status_color}[**{rec.status}**]")

        ai_diag = rec.ai_diagnosis

        with st.expander("🔍 Deterministic Rule-Checker Findings (Phase 2)", expanded=True):
            if ai_diag.rule_checker_findings:
                for f in ai_diag.rule_checker_findings:
                    badge = "🔴 ERROR" if f.status == "ERROR" else "🟢 PASS"
                    st.write(f"- **{f.rule}**: {badge} — {f.message}")
            else:
                st.info("No rule checker syntax errors detected for this case.")

        st.markdown("### 🤖 Original AI Diagnosis Recommendation")
        res_col1, res_col2, res_col3 = st.columns(3)
        res_col1.metric("Diagnosis Status", ai_diag.diagnosis_status)
        res_col2.metric("Confidence Score", f"{ai_diag.confidence:.2f}")
        res_col3.metric("Affected OSI Layer", ai_diag.osi_layer)

        st.markdown(f"**Root Cause**: `{ai_diag.root_cause}`")
        st.markdown(f"**Explanation**: {ai_diag.explanation}")

        if ai_diag.evidence:
            st.markdown("**Evidence Cited**:")
            for ev in ai_diag.evidence:
                st.markdown(f"  * `{ev}`")

        if ai_diag.next_command:
            st.markdown(f"**Recommended Next Command**: `{ai_diag.next_command}`")

        if ai_diag.fix_steps:
            st.markdown("**Recommended Fix Steps (Requires Human Action)**:")
            for idx, step in enumerate(ai_diag.fix_steps, 1):
                st.markdown(f"  {idx}. `{step}`")

        st.divider()

        if rec.status == "PENDING":
            st.subheader("Human Reviewer Action")
            action = st.radio("Select Review Decision:", ["ACCEPT", "EDIT / MODIFY", "REJECT"], horizontal=True)
            reviewer_input = st.text_input("Reviewer Name:", value=reviewer_default_name, key="rev_input")

            if action == "ACCEPT":
                st.success("Approve the AI recommendation exactly as presented.")
                accept_reason = st.text_input("Acceptance Comment (Optional):", value="Approved as accurate.")
                if st.button("✅ Confirm ACCEPT"):
                    try:
                        updated_rec = accept_review(rec.review_id, reviewer=reviewer_input, reason=accept_reason)
                        st.session_state["current_review"] = updated_rec
                        st.success(f"Review `{rec.review_id}` successfully ACCEPTED!")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

            elif action == "EDIT / MODIFY":
                st.warning("Modify the AI recommendation. Both original AI and human-edited versions will be saved.")
                mod_reason = st.text_area("Mandatory Modification Reason (Required):", placeholder="Explain why the AI diagnosis is being edited...")

                st.markdown("#### Edit Diagnosis Fields")
                edit_root_cause = st.text_input("Root Cause", value=ai_diag.root_cause)
                edit_status = st.selectbox("Diagnosis Status", ["CONFIRMED", "LIKELY", "UNCERTAIN"], index=["CONFIRMED", "LIKELY", "UNCERTAIN"].index(ai_diag.diagnosis_status))
                edit_confidence = st.slider("Confidence Score", 0.0, 1.0, float(ai_diag.confidence), 0.05)
                edit_osi = st.selectbox("OSI Layer", ["Layer 2", "Layer 3", "Layer 4", "Layer 7", "Layer 2/3", "Layer 3/4", "Unknown"], index=["Layer 2", "Layer 3", "Layer 4", "Layer 7", "Layer 2/3", "Layer 3/4", "Unknown"].index(ai_diag.osi_layer))
                edit_next_cmd = st.text_input("Next Command (or blank)", value=ai_diag.next_command or "")
                edit_fix_steps_raw = st.text_area("Fix Steps (one per line)", value="\n".join(ai_diag.fix_steps))
                edit_explanation = st.text_area("Explanation", value=ai_diag.explanation)

                st.markdown("#### ⚖️ Side-by-Side Comparison Preview")
                cmp1, cmp2 = st.columns(2)
                with cmp1:
                    st.markdown("**Original AI Recommendation**")
                    st.write(f"- Root Cause: {ai_diag.root_cause}")
                    st.write(f"- Status: {ai_diag.diagnosis_status}")
                    st.write(f"- Confidence: {ai_diag.confidence}")
                    st.write(f"- OSI Layer: {ai_diag.osi_layer}")
                with cmp2:
                    st.markdown("**Human-Edited Recommendation**")
                    st.write(f"- Root Cause: {edit_root_cause}")
                    st.write(f"- Status: {edit_status}")
                    st.write(f"- Confidence: {edit_confidence}")
                    st.write(f"- OSI Layer: {edit_osi}")

                if st.button("✏️ Confirm MODIFICATION"):
                    fix_list = [s.strip() for s in edit_fix_steps_raw.splitlines() if s.strip()]
                    edited_diag_obj = DiagnosisResult(
                        case_id=ai_diag.case_id,
                        root_cause=edit_root_cause,
                        diagnosis_status=edit_status,
                        confidence=edit_confidence,
                        osi_layer=edit_osi,
                        evidence=ai_diag.evidence,
                        rule_checker_findings=ai_diag.rule_checker_findings,
                        next_command=edit_next_cmd if edit_next_cmd.strip() else None,
                        fix_steps=fix_list,
                        explanation=edit_explanation,
                        is_mock=ai_diag.is_mock,
                    )
                    try:
                        updated_rec = modify_review(
                            rec.review_id,
                            edited_diagnosis=edited_diag_obj,
                            reviewer=reviewer_input,
                            reason=mod_reason,
                        )
                        st.session_state["current_review"] = updated_rec
                        st.success(f"Review `{rec.review_id}` successfully MODIFIED!")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

            elif action == "REJECT":
                st.error("Reject the AI recommendation. Original AI diagnosis will remain saved for audit.")
                rej_reason = st.text_area("Mandatory Rejection Reason (Required):", placeholder="Explain why the AI diagnosis is rejected...")

                if st.button("❌ Confirm REJECTION"):
                    try:
                        updated_rec = reject_review(rec.review_id, reviewer=reviewer_input, reason=rej_reason)
                        st.session_state["current_review"] = updated_rec
                        st.success(f"Review `{rec.review_id}` REJECTED!")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))


# =============================================================================
# TAB 3: REVIEW HISTORY & AUDIT LOG
# =============================================================================
elif nav_choice == "📋 Review History & Audit Log":
    st.header("📋 Review History & Audit Log")
    st.caption("Read-only historical view of all human review decisions.")

    if not all_reviews:
        st.info("No historical review records found.")
    else:
        status_filter = st.selectbox("Filter by Status:", ["ALL", "PENDING", "ACCEPTED", "MODIFIED", "REJECTED"])
        filtered_reviews = all_reviews if status_filter == "ALL" else [r for r in all_reviews if r.status == status_filter]

        st.markdown(f"**Total Records Found**: `{len(filtered_reviews)}`")

        table_data = []
        for r in filtered_reviews:
            table_data.append({
                "Review ID": r.review_id,
                "Case ID": r.case_id,
                "Status": r.status,
                "Reviewer": r.reviewer or "N/A",
                "Reason / Comment": r.reason or "",
                "Created At": r.created_at,
            })
        st.dataframe(pd.DataFrame(table_data), use_container_width=True)

        st.divider()
        st.subheader("Inspect Specific Review Record")
        rev_id_list = [r.review_id for r in filtered_reviews]
        sel_rev_id = st.selectbox("Select Review ID:", rev_id_list)
        sel_rec = next((r for r in filtered_reviews if r.review_id == sel_rev_id), None)

        if sel_rec:
            st.markdown(f"### Review Record `{sel_rec.review_id}`")
            st.markdown(f"- **Case ID**: `{sel_rec.case_id}`")
            st.markdown(f"- **Status**: `{sel_rec.status}`")
            st.markdown(f"- **Reviewer**: `{sel_rec.reviewer}`")
            st.markdown(f"- **Reason / Comment**: {sel_rec.reason}")
            st.markdown(f"- **Reviewed At**: `{sel_rec.reviewed_at or sel_rec.created_at}`")

            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("#### Original AI Diagnosis")
                st.json(sel_rec.ai_diagnosis.model_dump())

            with col_b:
                st.markdown("#### Human-Edited Diagnosis")
                if sel_rec.human_diagnosis:
                    st.json(sel_rec.human_diagnosis.model_dump())
                else:
                    st.info("No human diagnosis modification (Status: " + sel_rec.status + ")")


# =============================================================================
# TAB 4: RESPONSIBLE AI & HUMAN CORRECTIONS
# =============================================================================
elif nav_choice == "🛡️ Responsible AI & Human Corrections":
    st.header("🛡️ Responsible AI & Human Corrections Engine")

    render_responsible_ai_section(metrics)

    st.divider()

    # Seed demo reviews helper if needed
    corrected = get_corrected_review_records(all_reviews)
    if len(corrected) < 5:
        st.warning(f"Currently {len(corrected)} corrected AI responses exist in audit log. (Requirement: at least 5 corrected AI responses).")
        if st.button("➕ Seed Demo Corrected Reviews (Tagged [DEMO])"):
            seed_demo_corrected_reviews(5)
            st.success("Seeded demo corrected reviews. Refreshing page...")
            st.rerun()

    render_corrected_responses_table(all_reviews)


# =============================================================================
# TAB 5: CASE EXPLORER & DATASET HEALTH
# =============================================================================
elif nav_choice == "🔍 Case Explorer & Dataset Health":
    st.header("🔍 Case Explorer & Dataset Health Audit")

    render_case_explorer()

    st.divider()

    render_dataset_health(dataset_summary)


# =============================================================================
# TAB 6: AI EVALUATION ANALYTICS
# =============================================================================
elif nav_choice == "🎯 AI Evaluation Analytics":
    st.header("🎯 AI Evaluation Analytics")

    render_ai_evaluation_section()
