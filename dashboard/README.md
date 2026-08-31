# NetSage AI - Executive Dashboard & Responsible AI Analytics Module

Implements Phase 5 data analytics, executive KPI cards, issue category distribution, severity analytics, review outcome breakdown, Responsible AI metrics, and Case Explorer with ground-truth inspection.

## Architecture
- `analytics.py`: Data aggregation, dataset health audit, and Responsible AI metrics calculation.
- `components.py`: Modular Streamlit UI renderer functions for charts, metrics cards, and tables.
- `test_dashboard.py`: Unit test suite (6 tests).

## Execution
Run Streamlit Dashboard UI:
```bash
streamlit run streamlit_app.py
```

Run CLI Metrics Overview:
```bash
python app.py --dashboard-metrics
```

Run Unit Tests:
```bash
python -m unittest discover -s dashboard
```
