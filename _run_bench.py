#!/usr/bin/env python3
"""Quick benchmark runner – writes results to _bench_output.txt"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from testing.test_algorithm import AlgorithmTester

t = AlgorithmTester()
t.load_dataset()
t.run_all_tests("testing/benchmark/testing.csv")

s = t.stats
lines = []
lines.append(f"Total: {s['total_tests']}")
lines.append(f"Exact: {s['exact_matches']}")
lines.append(f"Partial: {s['partial_matches']}")
lines.append(f"Failed: {s['failed_detections']}")
lines.append(f"Precision: {s.get('precision', 0):.4f}")
lines.append(f"Recall: {s.get('recall', 0):.4f}")
lines.append(f"F1: {s.get('f1_score', 0):.4f}")

failures = [r for r in t.results if r['match_type'] != 'exact']
if failures:
    lines.append(f"\n--- {len(failures)} non-exact results ---")
    for f in failures:
        lines.append(f"  #{f['test_id']} [{f['match_type']}] exp={f['expected_symptoms']} det={f['detected_symptoms']} input={f['input_text'][:80]}")
else:
    lines.append("\nAll tests EXACT match!")

out = "\n".join(lines)
print(out)
with open(os.path.join(os.path.dirname(__file__), "_bench_output.txt"), "w") as fp:
    fp.write(out + "\n")
