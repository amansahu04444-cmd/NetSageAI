# NetSage AI - Deterministic Rule Checker Module

This module implements deterministic Python logic for network validation. It operates without AI models to guarantee fast, reproducible findings.

## Implemented Functions
- `check_duplicate_ips(evidence)`
- `check_subnet_masks(evidence)`
- `check_gateway_mismatch(evidence)`
- `check_interface_status(evidence)`
- `check_missing_vlans(evidence)`
- `check_missing_routes(evidence)`
- `run_all_checks(evidence)`
- `run_checker_on_dataset(csv_path)`

## Execution
```bash
python checker/rule_checker.py
python -m unittest checker/test_rule_checker.py
```
