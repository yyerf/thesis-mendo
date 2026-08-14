"""eval_xlsx_suite.py — run the user's test.xlsx suite (520 cases, 4 languages,
normal + negation sheets) against the live hybrid pipeline and report failures.

Usage:
  python testing/eval_xlsx_suite.py            # full run (sailor default backend)
  MENDO_SEMANTIC_BACKEND=minilm python testing/eval_xlsx_suite.py

Output: prints a per-group summary + failure list, writes
  testing/benchmark/results/xlsx_suite_results.json
"""

from __future__ import annotations

import collections
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mendo_core.prediction_pipeline import predict_symptoms  # noqa: E402

SUITE = ROOT / "testing" / "benchmark" / "test_xlsx_cases.jsonl"
OUT = ROOT / "testing" / "benchmark" / "results" / "xlsx_suite_results.json"

# xlsx expected label -> canonical symptom label
EXPECTED_MAP = {
    "Fever": "FEVER",
    "Headache": "HEADACHE",
    "Bodyache": "BODY_ACHES",
    "Stomachache": "STOMACH_ACHE",
    "Diarrhea": "DIARRHEA",
    "Rashes": "RASHES",
    "Toothache": "TOOTHACHE",
    "Allergy": "ALLERGIC_RHINITIS",
    "Runny Nose": "RUNNY_NOSE",
    "Cold (Runny Nose)": "RUNNY_NOSE",
    "Nasal Congestion": "NASAL_CONGESTION",
    "Cold (Nasal Congestion)": "NASAL_CONGESTION",
    "Cough": "COUGH_GENERAL",
    "Cough (Unspecified)": "COUGH_GENERAL",
    "Dry Cough": "COUGH_DRY",
    "Cough (Dry Cough)": "COUGH_DRY",
    "Cough with Phlegm": "COUGH_PRODUCTIVE",
    "Cough (Cough with Phlegm)": "COUGH_PRODUCTIVE",
}

EMPTY_EXPECTED = {"Not Recognized", "Not recognized", "Input not recognized", "Triggered Warning", ""}


def lang_of(tc_id: str) -> str:
    if "NEG" in tc_id:
        base = tc_id.split("- NEG")[0].strip().split(" ")[0]
    else:
        base = tc_id.split("-")[0].strip()
    return base


def load_cases() -> list[dict]:
    recs = []
    for line in open(SUITE, encoding="utf-8"):
        recs.append(json.loads(line))
    return recs


def expected_canonical(exp: str) -> set:
    if exp in EMPTY_EXPECTED or not exp:
        return set()
    return {EXPECTED_MAP.get(exp, exp.upper())}


def main() -> None:
    cases = load_cases()
    results = []
    engine_id = None
    t_total = time.time()
    for i, rec in enumerate(cases, 1):
        t0 = time.time()
        try:
            trace = predict_symptoms(rec["input"])
        except Exception as e:  # noqa: BLE001
            trace = {"error": str(e)}
        latency = time.time() - t0
        if engine_id is None:
            engine_id = (trace.get("engine") or {}).get("engine_id", "unknown")
        got = set(trace.get("final", {}).get("symptoms", []) or [])
        exp = expected_canonical(rec["expected"])
        ok = got == exp
        results.append(
            {
                "tc_id": rec["tc_id"],
                "sheet": rec["sheet"],
                "lang": lang_of(rec["tc_id"]),
                "input": rec["input"],
                "expected": sorted(exp),
                "detected": sorted(got),
                "ok": ok,
                "latency_s": round(latency, 3),
                "source": trace.get("final", {}).get("source"),
                "sem_used": bool((trace.get("semantic") or {}).get("used")),
            }
        )
    elapsed = time.time() - t_total

    total = len(results)
    ok_count = sum(1 for r in results if r["ok"])
    print(f"SUITE: {ok_count}/{total} exact ({ok_count / total:.1%}) — engine {engine_id} — {elapsed:.0f}s")

    groups = collections.OrderedDict()
    for r in results:
        key = (r["sheet"].split("(")[1].rstrip(")"), r["lang"])
        groups.setdefault(key, {"total": 0, "ok": 0})
        groups[key]["total"] += 1
        groups[key]["ok"] += int(r["ok"])
    print("\nby sheet x language:")
    for (sheet, lang), g in groups.items():
        print(f"  {sheet:<10} {lang:<4} {g['ok']:>3}/{g['total']} ({g['ok'] / g['total']:.1%})")

    by_expected = collections.Counter()
    fails = [r for r in results if not r["ok"]]
    print(f"\nfailures: {len(fails)}")
    for r in fails:
        print(f"  [{r['tc_id']}] {r['lang']} exp={r['expected']} got={r['detected']} src={r['source']} :: {r['input'][:75]!r}")

    OUT.write_text(
        json.dumps(
            {
                "total": total,
                "ok": ok_count,
                "engine_id": engine_id,
                "elapsed_s": round(elapsed, 1),
                "results": results,
            },
            indent=1,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"\nsaved -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
