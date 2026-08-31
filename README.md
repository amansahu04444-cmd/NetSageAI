# NetSage AI

AI-assisted Cisco / Packet Tracer network troubleshooting helper with mandatory human review.

## Architecture & End-to-End Pipeline

```text
Dataset (30 cases.csv)
   ↓
Rule Checker (6 Deterministic Rules)
   ↓
AI Diagnosis Engine (Gemini / Mock Mode)
   ↓
Human Review Center (PENDING → ACCEPTED | MODIFIED | REJECTED)
   ↓
Persistent Audit Log (audit_log.csv & reviews.json)
   ↓
Responsible AI Dashboard & Governance Analytics
```

## Project Directory Structure

```text
NetSage-AI/
├── data/
│   ├── cases.csv            # Original troubleshooting dataset (30 cases, unmodified)
│   └── dataset_loader.py    # Loader module & schema validation utility
├── checker/
│   ├── rule_checker.py      # Deterministic 6-rule network checker
│   ├── test_rule_checker.py # Unit tests for rule checker (18 tests)
│   └── README.md            # Rule checker documentation
├── prompts/
│   ├── diagnose_prompt.md   # Main structured diagnostic prompt template
│   ├── examples.md          # Worked diagnostic examples
│   └── README.md            # Prompt library documentation
├── ai/
│   ├── structured_output.py # Pydantic schema validation module
│   ├── diagnosis_engine.py  # AI diagnosis engine (Gemini & Mock support)
│   ├── evaluator.py         # Ground-truth evaluation module
│   ├── test_diagnosis_engine.py # Unit tests for AI engine (6 tests)
│   └── README.md            # AI engine documentation
├── review/
│   ├── review_workflow.py   # Pydantic ReviewRecord model & transition rules
│   ├── review_service.py    # High-level review management service
│   ├── audit_logger.py      # Persistent audit log writer & metrics
│   ├── test_review_workflow.py # Unit tests for review module (9 tests)
│   ├── audit_log.csv        # Persistent audit log file
│   ├── reviews.json         # Persistent JSON store for review records
│   └── README.md            # Review module documentation
├── dashboard/
│   ├── analytics.py         # Data analytics & Responsible AI metrics computation
│   ├── components.py        # Streamlit UI renderer components
│   ├── test_dashboard.py    # Unit tests for dashboard module (6 tests)
│   └── README.md            # Dashboard documentation
├── streamlit_app.py         # Streamlit App (Human Review Center + Executive Dashboard)
├── app.py                   # Main CLI entry point
├── requirements.txt         # Project dependencies
├── .gitignore               # Secrets and cache exclusions
└── README.md                # Project documentation
---

## Gemini API Configuration

To enable live Google Gemini AI diagnosis generation:

1. **Obtain a Gemini API Key**: Create a key in Google AI Studio.
2. **Create `.env` Configuration File**: Copy `.env.example` to `.env` in project root:
   ```bash
   cp .env.example .env
   ```
3. **Set your API key**: Open `.env` and add your secret API key:
   ```env
   GEMINI_API_KEY=your_actual_gemini_api_key_here
   GEMINI_MODEL=gemini-3.6-flash
   ```
4. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
5. **Start Streamlit Dashboard**:
   ```bash
   streamlit run streamlit_app.py
   ```
6. **Disable Offline Mock Mode**: In the Streamlit sidebar, uncheck **Use Offline Mock Mode** and click **🧪 Test Gemini Connection** to verify API connectivity.

*Note: If no API key is configured in `.env`, the system automatically falls back to deterministic Offline Mock Mode without crashing.*

---

## Phase 1: Dataset Validation
```bash
python app.py --validate
```

---

## Phase 2: Rule-Based Network Checker
```bash
python app.py --check-rules
```

---

## Phase 3: AI Diagnosis Engine
```bash
python app.py --diagnose NET-001 --mock
python app.py --evaluate NET-001 --mock
python app.py --evaluate-all --mock
```

---

## Phase 4: Mandatory Human-in-the-Loop Review
```bash
python app.py --review NET-001
python app.py --list-reviews
```

---

## Phase 5: Dashboard & Responsible AI Analytics

The **Executive Dashboard & Responsible AI Analytics** module (`dashboard/analytics.py`, `dashboard/components.py`) provides read-only analytics, top KPI metrics, issue category distributions, severity analytics, review outcome breakdowns, Responsible AI governance rates, and an interactive Case Explorer.

### Key Metrics & Formulas
- **Top KPI Cards**: Total Cases (30), Total Reviews, AI Accepted, AI Modified, AI Rejected, AI-Human Agreement Rate, Corrected AI Responses.
- **Agreement Rate**:
  $$\text{Agreement Rate} = \frac{\text{ACCEPTED Reviews}}{\text{Completed Reviews}} \times 100\%$$
  *(Completed Reviews = ACCEPTED + MODIFIED + REJECTED; PENDING reviews excluded from denominator).*
- **Correction Rate**:
  $$\text{Correction Rate} = \frac{\text{MODIFIED Reviews}}{\text{Completed Reviews}} \times 100\%$$
- **Rejection Rate**:
  $$\text{Rejection Rate} = \frac{\text{REJECTED Reviews}}{\text{Completed Reviews}} \times 100\%$$
- **Corrected AI Responses**: Total count of MODIFIED + REJECTED human review records.
- **Mock vs Real AI Labeling**: Explicitly labels diagnoses as `"MOCK MODE"` or `"GEMINI / LIVE AI"`.

### How to Run Streamlit Dashboard UI
Launch the interactive Streamlit application containing the Executive Dashboard and Human Review Center:
```bash
streamlit run streamlit_app.py
```

### How to View Dashboard Metrics in CLI
```bash
python app.py --dashboard-metrics
```

### How to Run All Project Unit Tests
Run all 39 unit tests across all 4 modules:
```bash
python -m unittest discover -s checker
python -m unittest discover -s ai
python -m unittest discover -s review
python -m unittest discover -s dashboard
```
