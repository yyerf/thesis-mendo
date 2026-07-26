"""
Comprehensive Algorithm Testing Suite for Mendo Symptom Detection & Recommendation System

This script tests the hybrid NLP algorithm against 100 diverse test cases including:
- Simple single symptoms
- Multiple symptoms
- Negations
- Partial negations
- Noisy input
- Misspellings
- Alternative phrasings
- English inputs
- Code-switching (mixed languages)
- Third-person descriptions
- Temporal contexts
- Age contexts
- Severity variations
- Question forms

Results are saved to benchmark/results/ with detailed metrics.
"""

import os
import sys
import csv
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add parent directory to path to import mendo_core
sys.path.insert(0, str(Path(__file__).parent.parent))

from mendo_core.evaluation import aggregate_metrics
from mendo_core.prediction_pipeline import (
    ENGINE_ID,
    TRACE_SCHEMA_VERSION,
    predict_symptoms,
)
from mendo_core.step4_recommend import load_mendo_dataset, recommend_from_dataset, DATASET_DEFAULT


class AlgorithmTester:
    """Comprehensive testing class for Mendo algorithm."""

    def __init__(self):
        self.results = []
        self.dataset_rows = None
        self.stats = {
            'total_tests': 0,
            'exact_matches': 0,
            'partial_matches': 0,
            'failed_detections': 0,
            'false_positives': 0,
            'negation_handled': 0,
            'negation_failed': 0,
            'recommendation_success': 0,
            'recommendation_failed': 0,
        }
        self.category_stats = {}

    def load_dataset(self):
        """Load Mendo dataset for recommendations."""
        try:
            self.dataset_rows = load_mendo_dataset(DATASET_DEFAULT)
            print(f"✓ Loaded {len(self.dataset_rows)} medicine entries from dataset")
        except Exception as e:
            print(f"✗ Failed to load dataset: {e}")
            sys.exit(1)

    def normalize_symptom_set(self, symptoms: List[str]) -> set:
        """Normalize symptom list to set for comparison."""
        return set(s.strip().upper() for s in symptoms if s.strip())

    def evaluate_detection(
        self,
        detected: List[str],
        expected: List[str],
        test_category: str
    ) -> Dict[str, Any]:
        """
        Evaluate symptom detection accuracy.
        
        Returns:
            dict with keys: match_type, precision, recall, f1_score, 
                           correct, missed, extra
        """
        detected_set = self.normalize_symptom_set(detected)
        expected_set = self.normalize_symptom_set(expected)

        # Handle NONE case (negations)
        if 'NONE' in expected_set:
            if len(detected_set) == 0:
                return {
                    'match_type': 'exact',
                    'precision': 1.0,
                    'recall': 1.0,
                    'f1_score': 1.0,
                    'correct': ['NONE'],
                    'missed': [],
                    'extra': []
                }
            else:
                return {
                    'match_type': 'failed',
                    'precision': 0.0,
                    'recall': 0.0,
                    'f1_score': 0.0,
                    'correct': [],
                    'missed': ['NONE'],
                    'extra': list(detected_set)
                }

        if len(expected_set) == 0:
            # No expected symptoms
            if len(detected_set) == 0:
                match_type = 'exact'
                precision = recall = f1 = 1.0
            else:
                match_type = 'false_positive'
                precision = recall = f1 = 0.0
        else:
            correct = detected_set & expected_set
            missed = expected_set - detected_set
            extra = detected_set - expected_set

            if detected_set == expected_set:
                match_type = 'exact'
            elif len(correct) > 0:
                match_type = 'partial'
            else:
                match_type = 'failed'

            # Calculate metrics
            precision = len(correct) / len(detected_set) if detected_set else 0.0
            recall = len(correct) / len(expected_set) if expected_set else 0.0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

            return {
                'match_type': match_type,
                'precision': precision,
                'recall': recall,
                'f1_score': f1,
                'correct': list(correct),
                'missed': list(missed),
                'extra': list(extra)
            }

        return {
            'match_type': match_type,
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'correct': list(correct) if 'correct' in locals() else [],
            'missed': list(missed) if 'missed' in locals() else [],
            'extra': list(extra) if 'extra' in locals() else []
        }

    def test_single_case(
        self,
        test_id: int,
        input_text: str,
        age: int,
        cough_type: Optional[str],
        expected_symptoms: List[str],
        test_category: str,
        notes: str
    ) -> Dict[str, Any]:
        """Test a single case and return detailed results."""
        
        # Run hybrid detection
        try:
            report = predict_symptoms(input_text)
            detected_symptoms = list(report.get("final", {}).get("symptoms", []) or [])
            raw_detected_symptoms = list(detected_symptoms)
            detection_source = report.get("final", {}).get("source", "unknown")
            detection_error = None
        except Exception as e:
            detected_symptoms = []
            raw_detected_symptoms = []
            detection_source = "error"
            detection_error = str(e)

        # Apply cough override if specified
        if cough_type and cough_type.strip():
            detected_symptoms = self._apply_cough_override(detected_symptoms, cough_type)

        # Evaluate detection
        eval_result = self.evaluate_detection(detected_symptoms, expected_symptoms, test_category)

        # Get recommendations
        recommendations = []
        recommendation_error = None
        try:
            rec_result = recommend_from_dataset(detected_symptoms, self.dataset_rows)
            if rec_result.get("action") == "recommend":
                recommendations = [
                    r.get("brand") for r in rec_result.get("recommendations", [])
                ]
        except Exception as e:
            recommendation_error = str(e)

        # Compile results
        result = {
            'test_id': test_id,
            'input_text': input_text,
            'age': age,
            'cough_type': cough_type or '',
            'expected_symptoms': ','.join(expected_symptoms),
            'detected_symptoms': ','.join(detected_symptoms),
            'raw_detected_symptoms': ','.join(raw_detected_symptoms),
            'detection_source': detection_source,
            'test_category': test_category,
            'notes': notes,
            'match_type': eval_result['match_type'],
            'precision': round(eval_result['precision'], 3),
            'recall': round(eval_result['recall'], 3),
            'f1_score': round(eval_result['f1_score'], 3),
            'correct_symptoms': ','.join(eval_result['correct']),
            'missed_symptoms': ','.join(eval_result['missed']),
            'extra_symptoms': ','.join(eval_result['extra']),
            'recommendations': ','.join(recommendations[:3]) if recommendations else 'None',
            'recommendation_count': len(recommendations),
            'detection_error': detection_error or '',
            'recommendation_error': recommendation_error or '',
        }

        # Update statistics
        self.stats['total_tests'] += 1
        
        if eval_result['match_type'] == 'exact':
            self.stats['exact_matches'] += 1
        elif eval_result['match_type'] == 'partial':
            self.stats['partial_matches'] += 1
        elif eval_result['match_type'] == 'failed':
            self.stats['failed_detections'] += 1
        elif eval_result['match_type'] == 'false_positive':
            self.stats['false_positives'] += 1

        # Negation tracking
        if test_category in ['negation', 'partial_negation']:
            if 'NONE' in expected_symptoms and len(detected_symptoms) == 0:
                self.stats['negation_handled'] += 1
            elif 'NONE' in expected_symptoms:
                self.stats['negation_failed'] += 1

        # Recommendation tracking
        if len(detected_symptoms) > 0 and len(recommendations) > 0:
            self.stats['recommendation_success'] += 1
        elif len(detected_symptoms) > 0 and len(recommendations) == 0:
            self.stats['recommendation_failed'] += 1

        # Category tracking
        if test_category not in self.category_stats:
            self.category_stats[test_category] = {
                'total': 0,
                'exact': 0,
                'partial': 0,
                'failed': 0,
                'avg_f1': 0.0
            }
        
        cat_stat = self.category_stats[test_category]
        cat_stat['total'] += 1
        if eval_result['match_type'] == 'exact':
            cat_stat['exact'] += 1
        elif eval_result['match_type'] == 'partial':
            cat_stat['partial'] += 1
        else:
            cat_stat['failed'] += 1
        
        # Update running average F1
        cat_stat['avg_f1'] = (
            (cat_stat['avg_f1'] * (cat_stat['total'] - 1) + eval_result['f1_score'])
            / cat_stat['total']
        )

        return result

    def _apply_cough_override(self, labels: List[str], cough_type: Optional[str]) -> List[str]:
        """Apply cough type override logic."""
        if not cough_type:
            return labels
        
        cough_type = str(cough_type).strip().lower()
        mapped = None
        
        if cough_type in {"dry", "dry_cough", "walang", "walay"}:
            mapped = "COUGH_DRY"
        elif cough_type in {"productive", "wet", "with_phlegm", "plema"}:
            mapped = "COUGH_PRODUCTIVE"
        
        if not mapped:
            return labels
        
        # A guided answer replaces every generic/competing cough label.
        out = [
            label
            for label in labels
            if label not in {"COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"}
        ]
        out.append(mapped)
        return out

    def run_all_tests(self, test_file: str):
        """Run all tests from CSV file."""
        print("\n" + "="*80)
        print("MENDO ALGORITHM COMPREHENSIVE TESTING SUITE")
        print("="*80 + "\n")

        if not os.path.exists(test_file):
            print(f"✗ Test file not found: {test_file}")
            sys.exit(1)

        print(f"Loading test cases from: {test_file}")
        
        test_cases = []
        with open(test_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                test_cases.append(row)
        
        print(f"✓ Loaded {len(test_cases)} test cases\n")

        # Run tests
        print("Running tests...")
        print("-" * 80)
        
        for i, test_case in enumerate(test_cases, 1):
            test_id = int(test_case['test_id'])
            input_text = test_case['input_text']
            age = int(test_case['age'])
            cough_type = test_case['cough_type'].strip() or None
            expected_symptoms = [
                s.strip() for s in test_case['expected_symptoms'].split(',') if s.strip()
            ]
            test_category = test_case['test_category']
            notes = test_case['notes']

            result = self.test_single_case(
                test_id, input_text, age, cough_type,
                expected_symptoms, test_category, notes
            )
            
            self.results.append(result)
            
            # Progress indicator
            status_icon = "✓" if result['match_type'] == 'exact' else "⚠" if result['match_type'] == 'partial' else "✗"
            print(f"{status_icon} Test {test_id:3d}/{len(test_cases)} | "
                  f"{test_category:20s} | F1: {result['f1_score']:.3f} | {input_text[:40]}")

        print("-" * 80)
        print("\nAll tests completed!\n")

    def save_results(self, output_dir: str):
        """Save one reproducible detail file and one canonical manifest."""
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().isoformat(timespec="seconds")
        results_file = os.path.join(output_dir, "current.csv")
        
        if not self.results:
            print("No results to save.")
            return

        # Save detailed results
        fieldnames = list(self.results[0].keys())
        with open(results_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.results)
        
        print(f"✓ Detailed results saved to: {results_file}")

        # Save summary statistics
        summary_file = os.path.join(output_dir, "current.json")
        guided_cases = []
        raw_cases = []
        for row in self.results:
            predicted = [v for v in row["detected_symptoms"].split(",") if v]
            raw_predicted = [v for v in row["raw_detected_symptoms"].split(",") if v]
            expected = [
                v for v in row["expected_symptoms"].split(",") if v and v != "NONE"
            ]
            guided_cases.append({"predicted": predicted, "expected": expected})
            raw_cases.append({"predicted": raw_predicted, "expected": expected})
        metrics = {
            "raw_input": aggregate_metrics(raw_cases),
            "guided_workflow": aggregate_metrics(guided_cases),
        }
        summary = {
            'generated_at': timestamp,
            'status': 'generated',
            'provenance': 'researcher_and_llm_created_synthetic_cases',
            'dataset': 'testing/benchmark/testing.csv',
            'dataset_sha256': hashlib.sha256(
                (Path(__file__).parent / "benchmark" / "testing.csv").read_bytes()
            ).hexdigest(),
            'engine_id': ENGINE_ID,
            'trace_version': TRACE_SCHEMA_VERSION,
            'automatic_production_training': False,
            'modes': {
                'raw_input': (
                    'Initial deployed prediction before the guided cough-type answer.'
                ),
                'guided_workflow': (
                    'Same prediction followed by the CSV cough_type answer, simulating '
                    'the deployed dry/productive clarification.'
                ),
            },
            'limitations': [
                'Synthetic researcher/LLM-created regression cases; not participant field data.',
                'The benchmark is not an independently collected clinical gold corpus.',
                'A perfect guided score must not be reported as clinical validation.',
            ],
            'metrics': metrics,
            'overall_stats': self.stats,
            'category_stats': self.category_stats,
        }
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        print(f"✓ Summary statistics saved to: {summary_file}")

        return results_file, summary_file

    def print_summary(self):
        """Print comprehensive summary to terminal."""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80 + "\n")

        # Overall statistics
        print("OVERALL STATISTICS:")
        print("-" * 80)
        print(f"  Total Tests:              {self.stats['total_tests']}")
        print(f"  Exact Matches:            {self.stats['exact_matches']} ({self.stats['exact_matches']/self.stats['total_tests']*100:.1f}%)")
        print(f"  Partial Matches:          {self.stats['partial_matches']} ({self.stats['partial_matches']/self.stats['total_tests']*100:.1f}%)")
        print(f"  Failed Detections:        {self.stats['failed_detections']} ({self.stats['failed_detections']/self.stats['total_tests']*100:.1f}%)")
        print(f"  False Positives:          {self.stats['false_positives']} ({self.stats['false_positives']/self.stats['total_tests']*100:.1f}%)")
        print()
        print(f"  Negations Handled:        {self.stats['negation_handled']}")
        print(f"  Negations Failed:         {self.stats['negation_failed']}")
        print()
        print(f"  Recommendations Given:    {self.stats['recommendation_success']}")
        print(f"  Recommendations Failed:   {self.stats['recommendation_failed']}")
        print()

        # Calculate overall metrics
        if self.results:
            avg_f1 = sum(r['f1_score'] for r in self.results) / len(self.results)
            avg_precision = sum(r['precision'] for r in self.results) / len(self.results)
            avg_recall = sum(r['recall'] for r in self.results) / len(self.results)
            
            print("OVERALL METRICS:")
            print("-" * 80)
            print(f"  Average Precision:        {avg_precision:.3f}")
            print(f"  Average Recall:           {avg_recall:.3f}")
            print(f"  Average F1 Score:         {avg_f1:.3f}")
            print(f"  Accuracy (Exact Match):   {self.stats['exact_matches']/self.stats['total_tests']:.3f}")
            print(f"  Success Rate (Exact+Partial): {(self.stats['exact_matches']+self.stats['partial_matches'])/self.stats['total_tests']:.3f}")
            print()

        # Category breakdown
        print("PERFORMANCE BY TEST CATEGORY:")
        print("-" * 80)
        print(f"{'Category':<25} {'Total':>7} {'Exact':>7} {'Partial':>9} {'Failed':>8} {'Avg F1':>8}")
        print("-" * 80)
        
        for category in sorted(self.category_stats.keys()):
            stats = self.category_stats[category]
            print(f"{category:<25} {stats['total']:>7} {stats['exact']:>7} {stats['partial']:>9} "
                  f"{stats['failed']:>8} {stats['avg_f1']:>8.3f}")
        
        print("-" * 80)
        print()

        # Problematic categories
        print("CATEGORIES NEEDING ATTENTION (F1 < 0.7):")
        print("-" * 80)
        problematic = [(cat, stats) for cat, stats in self.category_stats.items() 
                       if stats['avg_f1'] < 0.7]
        
        if problematic:
            for category, stats in sorted(problematic, key=lambda x: x[1]['avg_f1']):
                print(f"  {category:<25} F1: {stats['avg_f1']:.3f} "
                      f"(Exact: {stats['exact']}/{stats['total']}, "
                      f"Failed: {stats['failed']}/{stats['total']})")
        else:
            print("  None! All categories performing well.")
        
        print()

        # Sample failures
        print("SAMPLE FAILED/PARTIAL DETECTIONS:")
        print("-" * 80)
        failures = [r for r in self.results if r['match_type'] in ['failed', 'partial']][:10]
        
        if failures:
            for r in failures:
                print(f"\n  Test #{r['test_id']} ({r['test_category']}) - {r['match_type'].upper()}")
                print(f"    Input:    {r['input_text']}")
                print(f"    Expected: {r['expected_symptoms']}")
                print(f"    Detected: {r['detected_symptoms']}")
                print(f"    Missed:   {r['missed_symptoms']}")
                print(f"    Extra:    {r['extra_symptoms']}")
                print(f"    F1 Score: {r['f1_score']:.3f}")
        else:
            print("  None! All tests passed!")
        
        print("\n" + "="*80 + "\n")

    def _generate_html_report(self, output_file: str, timestamp: str):
        """Generate a standalone HTML report with embedded results."""
        
        # Calculate metrics
        total = self.stats['total_tests']
        exact = self.stats['exact_matches']
        partial = self.stats['partial_matches']
        failed = self.stats['failed_detections']
        avg_f1 = sum(r['f1_score'] for r in self.results) / len(self.results) if self.results else 0
        avg_precision = sum(r['precision'] for r in self.results) / len(self.results) if self.results else 0
        avg_recall = sum(r['recall'] for r in self.results) / len(self.results) if self.results else 0
        success_rate = (exact + partial) / total * 100 if total > 0 else 0
        
        # Generate table rows
        table_rows = []
        for row in self.results:
            f1 = float(row['f1_score'])
            f1_class = 'high' if f1 >= 0.8 else 'medium' if f1 >= 0.5 else 'low'
            
            expected_tags = ''.join(f'<span class="symptom-tag">{s.strip()}</span>' 
                                   for s in row['expected_symptoms'].split(',') if s.strip()) or '<em style="color:#ccc">-</em>'
            detected_tags = ''.join(f'<span class="symptom-tag">{s.strip()}</span>' 
                                   for s in row['detected_symptoms'].split(',') if s.strip()) or '<em style="color:#ccc">-</em>'
            missed_tags = ''.join(f'<span class="symptom-tag missed">{s.strip()}</span>' 
                                 for s in row['missed_symptoms'].split(',') if s.strip()) or '<em style="color:#ccc">-</em>'
            extra_tags = ''.join(f'<span class="symptom-tag extra">{s.strip()}</span>' 
                                for s in row['extra_symptoms'].split(',') if s.strip()) or '<em style="color:#ccc">-</em>'
            
            table_rows.append(f'''
                <tr>
                    <td><strong>#{row['test_id']}</strong></td>
                    <td style="max-width: 300px;">{row['input_text']}</td>
                    <td>{expected_tags}</td>
                    <td>{detected_tags}</td>
                    <td><span class="badge {row['match_type']}">{row['match_type']}</span></td>
                    <td><span class="f1-score {f1_class}">{row['f1_score']}</span></td>
                    <td><span class="category-badge">{row['test_category']}</span></td>
                    <td>{missed_tags}</td>
                    <td>{extra_tags}</td>
                    <td style="max-width: 250px; font-size: 11px;">{row['recommendations'] or 'None'}</td>
                </tr>
            ''')
        
        # Generate category options
        categories = sorted(set(r['test_category'] for r in self.results))
        category_options = '\n'.join(
            f'<option value="{cat}">{cat.replace("_", " ").title()}</option>' 
            for cat in categories
        )
        
        html_content = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mendo Test Results - {timestamp}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; min-height: 100vh; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.2); overflow: hidden; }}
        header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }}
        header h1 {{ font-size: 2.5em; margin-bottom: 10px; }}
        header p {{ font-size: 1.1em; opacity: 0.9; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; padding: 30px; background: #f8f9fa; }}
        .stat-card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); text-align: center; }}
        .stat-card h3 {{ color: #666; font-size: 0.9em; text-transform: uppercase; margin-bottom: 10px; }}
        .stat-card .value {{ font-size: 2.5em; font-weight: bold; color: #667eea; }}
        .stat-card .sub {{ color: #999; font-size: 0.9em; margin-top: 5px; }}
        .filters {{ padding: 20px 30px; background: white; border-bottom: 2px solid #eee; display: flex; gap: 15px; flex-wrap: wrap; align-items: center; }}
        .filters label {{ font-weight: 600; color: #333; }}
        .filters select, .filters input {{ padding: 8px 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 14px; }}
        .filters select:focus, .filters input:focus {{ outline: none; border-color: #667eea; }}
        .table-container {{ overflow-x: auto; padding: 30px; }}
        table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
        thead {{ background: #667eea; color: white; position: sticky; top: 0; z-index: 10; }}
        th {{ padding: 12px; text-align: left; font-weight: 600; text-transform: uppercase; font-size: 12px; letter-spacing: 0.5px; }}
        td {{ padding: 12px; border-bottom: 1px solid #eee; }}
        tbody tr:hover {{ background: #f8f9fa; }}
        .badge {{ display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; }}
        .badge.exact {{ background: #d4edda; color: #155724; }}
        .badge.partial {{ background: #fff3cd; color: #856404; }}
        .badge.failed {{ background: #f8d7da; color: #721c24; }}
        .symptom-tag {{ display: inline-block; padding: 3px 8px; margin: 2px; background: #e7e7ff; color: #5555cc; border-radius: 4px; font-size: 11px; }}
        .symptom-tag.missed {{ background: #ffebee; color: #c62828; }}
        .symptom-tag.extra {{ background: #fff3e0; color: #e65100; }}
        .f1-score {{ font-weight: bold; }}
        .f1-score.high {{ color: #155724; }}
        .f1-score.medium {{ color: #856404; }}
        .f1-score.low {{ color: #721c24; }}
        .category-badge {{ padding: 3px 8px; background: #e0e0e0; border-radius: 4px; font-size: 11px; color: #555; }}
        .hidden {{ display: none; }}
        .btn {{ background: #667eea; color: white; padding: 10px 20px; border: none; border-radius: 6px; cursor: pointer; font-weight: 600; transition: all 0.3s; }}
        .btn:hover {{ background: #5568d3; transform: translateY(-2px); box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4); }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🧪 Mendo Algorithm Test Results</h1>
            <p>Test Run: {timestamp}</p>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Total Tests</h3>
                <div class="value">{total}</div>
            </div>
            <div class="stat-card">
                <h3>Exact Matches</h3>
                <div class="value">{exact}</div>
                <div class="sub">{exact/total*100:.1f}%</div>
            </div>
            <div class="stat-card">
                <h3>Partial Matches</h3>
                <div class="value">{partial}</div>
                <div class="sub">{partial/total*100:.1f}%</div>
            </div>
            <div class="stat-card">
                <h3>Failed</h3>
                <div class="value">{failed}</div>
                <div class="sub">{failed/total*100:.1f}%</div>
            </div>
            <div class="stat-card">
                <h3>Average F1 Score</h3>
                <div class="value">{avg_f1:.3f}</div>
            </div>
            <div class="stat-card">
                <h3>Success Rate</h3>
                <div class="value">{success_rate:.1f}%</div>
            </div>
        </div>
        
        <div class="filters">
            <label>Filter by Category:</label>
            <select id="categoryFilter" onchange="applyFilters()">
                <option value="">All Categories</option>
                {category_options}
            </select>
            
            <label>Filter by Match Type:</label>
            <select id="matchFilter" onchange="applyFilters()">
                <option value="">All</option>
                <option value="exact">Exact</option>
                <option value="partial">Partial</option>
                <option value="failed">Failed</option>
            </select>
            
            <label>Search:</label>
            <input type="text" id="searchBox" placeholder="Search input text..." oninput="applyFilters()" />
            
            <button class="btn" onclick="window.print()">Print Report</button>
        </div>
        
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Input Text</th>
                        <th>Expected</th>
                        <th>Detected</th>
                        <th>Match</th>
                        <th>F1</th>
                        <th>Category</th>
                        <th>Missed</th>
                        <th>Extra</th>
                        <th>Recommendations</th>
                    </tr>
                </thead>
                <tbody id="resultsBody">
                    {''.join(table_rows)}
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        function applyFilters() {{
            const category = document.getElementById('categoryFilter').value.toLowerCase();
            const match = document.getElementById('matchFilter').value.toLowerCase();
            const search = document.getElementById('searchBox').value.toLowerCase();
            
            const rows = document.querySelectorAll('#resultsBody tr');
            
            rows.forEach(row => {{
                const categoryBadge = row.querySelector('.category-badge').textContent.toLowerCase();
                const matchBadge = row.querySelector('.badge').textContent.toLowerCase();
                const inputText = row.cells[1].textContent.toLowerCase();
                
                const categoryMatch = !category || categoryBadge.includes(category);
                const matchTypeMatch = !match || matchBadge.includes(match);
                const searchMatch = !search || inputText.includes(search);
                
                if (categoryMatch && matchTypeMatch && searchMatch) {{
                    row.style.display = '';
                }} else {{
                    row.style.display = 'none';
                }}
            }});
        }}
    </script>
</body>
</html>'''
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)


def main():
    """Main execution function."""
    # Get project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # File paths
    test_file = script_dir / "benchmark" / "testing.csv"
    results_dir = script_dir / "benchmark" / "results"
    
    # Initialize tester
    tester = AlgorithmTester()
    
    # Load dataset
    tester.load_dataset()
    
    # Run all tests
    tester.run_all_tests(str(test_file))
    
    # Save results
    tester.save_results(str(results_dir))
    
    # Print summary
    tester.print_summary()
    
    print("Testing complete! Check the results directory for detailed output.")


if __name__ == "__main__":
    main()
