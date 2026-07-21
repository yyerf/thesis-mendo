"""
Tier 5 — Duration Safeguard benchmark.

Exercises the real OLDCARTS Duration Safeguard in mendo_core.step4_recommend
(check_duration_safety / parse_duration_days) against testing/benchmark/
duration_cases.csv. Each case reports a symptom + a duration in days; the
system must allow OTC when the duration is within the clinical threshold and
refer the user to a doctor when it is exceeded.

Run:  python testing/test_duration.py
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mendo_core.step4_recommend import check_duration_safety, DURATION_THRESHOLDS

CASES = Path(__file__).parent / "benchmark" / "duration_cases.csv"


def run():
    rows = list(csv.DictReader(open(CASES, encoding="utf-8")))
    total = len(rows)
    passed = 0
    failures = []

    for r in rows:
        symptom = r["symptom"].strip()
        days = int(r["reported_days"])
        expected_safe = r["expected_safe"].strip().lower() == "true"

        result = check_duration_safety(symptom, days)
        actual_safe = bool(result.get("safe"))
        ok = actual_safe == expected_safe
        passed += ok
        status = "PASS" if ok else "FAIL"
        action = "proceed_otc" if actual_safe else "refer_doctor"
        print(f"  [{status}] {symptom:<18} {days:>3}d "
              f"(threshold {DURATION_THRESHOLDS[symptom]['days']}d) -> {action}")
        if not ok:
            failures.append((symptom, days, expected_safe, actual_safe))

    print("\n" + "=" * 60)
    print(f"Tier 5 Duration Safeguard: {passed}/{total} "
          f"({passed/total*100:.1f}%) exact match")
    if failures:
        print("\nFAILURES:")
        for s, d, exp, act in failures:
            print(f"  {s} {d}d: expected safe={exp}, got safe={act}")
    print("=" * 60)
    return passed == total


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
