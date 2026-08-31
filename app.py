"""
NetSage AI - Cisco/Packet Tracer Network Troubleshooting Helper
Main CLI Entry Point (Phase 1, Phase 2, Phase 3, Phase 4 & Phase 5)
"""

import json
import sys
import argparse
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from data.dataset_loader import generate_report, validate_dataset, load_cases_as_dicts
from checker.rule_checker import print_cli_report
from ai.diagnosis_engine import diagnose_case, DiagnosisEngineError
from ai.evaluator import evaluate_diagnosis
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
)


def main():
    parser = argparse.ArgumentParser(
        description="NetSage AI - Cisco Network Troubleshooting Helper CLI"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run dataset validation on cases.csv and print report",
    )
    parser.add_argument(
        "--check-rules",
        action="store_true",
        help="Run deterministic rule checker on troubleshooting cases dataset",
    )
    parser.add_argument(
        "--diagnose",
        type=str,
        default=None,
        help="Run AI diagnosis on a specific case_id (e.g. --diagnose NET-001)",
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force offline deterministic mock mode for diagnosis (no API key needed)",
    )
    parser.add_argument(
        "--evaluate",
        type=str,
        default=None,
        help="Diagnose case and evaluate result against ground-truth (e.g. --evaluate NET-001)",
    )
    parser.add_argument(
        "--evaluate-all",
        action="store_true",
        help="Run diagnosis and ground-truth evaluation across all 30 dataset cases",
    )
    parser.add_argument(
        "--review",
        type=str,
        default=None,
        help="Create a pending human review record for a specific case (e.g. --review NET-001)",
    )
    parser.add_argument(
        "--list-reviews",
        action="store_true",
        help="List all saved human review audit records and metrics",
    )
    parser.add_argument(
        "--dashboard-metrics",
        action="store_true",
        help="Print Phase 5 executive dashboard summary & Responsible AI analytics metrics",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Custom path to cases CSV file (optional)",
    )

    args = parser.parse_args()

    # Dashboard Metrics via CLI
    if args.dashboard_metrics:
        print("=== NetSage AI - Executive Dashboard & Responsible AI Analytics ===")
        summary = get_case_dataset_summary()
        records = load_all_review_records()
        metrics = compute_responsible_ai_metrics(records)

        print("\n--- KPI METRICS ---")
        print(f"Total Dataset Cases      : {summary['total_cases']}")
        print(f"Categories Covered       : {summary['categories_count']}")
        print(f"Total Review Records     : {metrics['total_reviews']}")
        print(f"Completed Human Reviews  : {metrics['completed_count']}")
        print(f"Pending Reviews          : {metrics['pending_count']}")
        print(f"AI Accepted Count        : {metrics['accepted_count']}")
        print(f"AI Modified Count        : {metrics['modified_count']}")
        print(f"AI Rejected Count        : {metrics['rejected_count']}")
        print(f"AI-Human Agreement Rate  : {metrics['agreement_rate_str']}")
        print(f"Human Correction Rate    : {metrics['correction_rate_str']}")
        print(f"Human Rejection Rate     : {metrics['rejection_rate_str']}")
        print(f"Corrected AI Responses   : {metrics['corrected_ai_responses_count']}")
        print("=" * 60)
        return

    # Create pending review via CLI
    if args.review:
        print(f"=== NetSage AI - Creating Human Review Record for {args.review} ===")
        try:
            diag = diagnose_case(args.review, csv_path=args.path, force_mock=args.mock)
            rev_rec = create_review(diag, reviewer="CLI User")
            print(f"Created PENDING Review Record: {rev_rec.review_id}")
            print(json.dumps(rev_rec.model_dump(), indent=2))
        except Exception as err:
            print(f"[ERROR] {err}")
            sys.exit(1)
        return

    # List reviews via CLI
    if args.list_reviews:
        print("=== NetSage AI - Human Review Audit Records & Metrics ===")
        reviews = list_reviews()
        records = load_all_review_records()
        metrics = compute_responsible_ai_metrics(records)
        print(f"Total Historical Reviews: {metrics['total_reviews']}")
        print(f"  * Accepted            : {metrics['accepted_count']}")
        print(f"  * Modified            : {metrics['modified_count']}")
        print(f"  * Rejected            : {metrics['rejected_count']}")
        print(f"  * Pending             : {metrics['pending_count']}")
        print(f"  * Agreement Rate      : {metrics['agreement_rate_str']}")
        print(f"  * AI Corrections      : {metrics['corrected_ai_responses_count']}")
        print("-" * 60)
        for r in reviews:
            print(f"Review {r.review_id} | Case: {r.case_id} | Status: {r.status} | Reviewer: {r.reviewer} | Reason: {r.reason}")
        return

    # Diagnosis for a specific case
    if args.diagnose:
        print(f"=== NetSage AI Diagnosis for {args.diagnose} ===")
        try:
            res = diagnose_case(args.diagnose, csv_path=args.path, force_mock=args.mock)
            print(json.dumps(res.model_dump(), indent=2))
        except DiagnosisEngineError as err:
            print(f"[ERROR] {err}")
            sys.exit(1)
        return

    # Evaluation for a specific case
    if args.evaluate:
        print(f"=== NetSage AI Ground-Truth Evaluation for {args.evaluate} ===")
        try:
            res = diagnose_case(args.evaluate, csv_path=args.path, force_mock=args.mock)
            cases = load_cases_as_dicts(args.path)
            target = next((c for c in cases if c.get("case_id") == args.evaluate), None)
            if not target:
                print(f"[ERROR] Case {args.evaluate} not found.")
                sys.exit(1)
            eval_report = evaluate_diagnosis(res, target)
            print(json.dumps(eval_report.to_dict(), indent=2))
        except DiagnosisEngineError as err:
            print(f"[ERROR] {err}")
            sys.exit(1)
        return

    # Evaluate all cases in dataset
    if args.evaluate_all:
        print("=== NetSage AI - Full Dataset Evaluation Run ===")
        cases = load_cases_as_dicts(args.path)
        eval_reports = []
        rc_matches = 0
        osi_matches = 0

        for c in cases:
            cid = c.get("case_id", "NET-000")
            try:
                diag = diagnose_case(cid, csv_path=args.path, force_mock=args.mock)
                rep = evaluate_diagnosis(diag, c)
                eval_reports.append(rep)
                if rep.root_cause_match:
                    rc_matches += 1
                if rep.osi_layer_match:
                    osi_matches += 1
            except Exception as e:
                print(f"[WARN] Failed evaluating {cid}: {e}")

        total = len(eval_reports)
        print(f"Total Cases Evaluated  : {total}")
        print(f"Root Cause Matches     : {rc_matches} / {total} ({(rc_matches/total*100):.1f}%)")
        print(f"OSI Layer Matches      : {osi_matches} / {total} ({(osi_matches/total*100):.1f}%)")
        print("================================================")
        return

    # Default run: validate dataset & check rules if no specific command given
    run_val = args.validate or (not args.validate and not args.check_rules)
    run_rules = args.check_rules or (not args.validate and not args.check_rules)

    if run_val:
        report = generate_report(args.path)
        print(report)
        val_res = validate_dataset(args.path)
        if not val_res.is_valid:
            sys.exit(1)

    if run_rules:
        print("\n")
        print_cli_report(args.path)


if __name__ == "__main__":
    main()
