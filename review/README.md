# NetSage AI - Human-in-the-Loop Review Module

Implements mandatory human review and approval workflows for AI-generated Cisco network troubleshooting diagnoses.

## Core Principles
1. **Zero Automated Execution**: AI recommendations are passive suggestions ONLY and will NEVER automatically alter Cisco device configurations.
2. **Immutable AI Output**: Original AI diagnoses are preserved persistently and never mutated or deleted.
3. **Immutable Terminal States**: Reviews transition from `PENDING` to `ACCEPTED`, `MODIFIED`, or `REJECTED`. Once in a terminal state, records cannot be altered.
4. **Mandatory Audit Trail**: Every decision is logged to `review/audit_log.csv` and `review/reviews.json` with timestamp, reviewer identity, and reason.

## Audit Log File
Located at: `review/audit_log.csv`

## Execution
Run Streamlit Review Interface:
```bash
streamlit run streamlit_app.py
```

Run CLI commands:
```bash
python app.py --review NET-001
python app.py --list-reviews
```

Run Unit Tests:
```bash
python -m unittest discover -s review
```
