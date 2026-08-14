"""compare_backends.py — honest head-to-head: MiniLM (cosine-anchor) vs Sailor2 (local LLM).

Runs the full 288-case detection benchmark through both semantic backends
in one process (resetting the extractor singleton between them) and reports:

  - exact/partial/failed per backend (guided, with cough override)
  - semantic generalization (16 paraphrases) + fresh negatives (20 chit-chat)
    where the semantic stage genuinely decides
  - semantic-stage behavior: when it fired (dictionary-miss only, for
    fallback_only backends) and what it selected
  - latency: mean / p95 per query per backend

Output: prints a table and writes testing/benchmark/results/backend_comparison.json

Usage:
  python testing/compare_backends.py
  MENDO_SEMANTIC_BACKEND is overridden per backend inside the harness.
"""

from __future__ import annotations

import csv
import json
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mendo_core import step3_hybrid  # noqa: E402
from mendo_core.prediction_pipeline import predict_symptoms  # noqa: E402
from testing.test_algorithm import AlgorithmTester  # noqa: E402

BENCH_CSV = ROOT / "testing" / "benchmark" / "testing.csv"
GEN_JSONL = ROOT / "testing" / "benchmark" / "semantic_generalization.jsonl"
NEG_JSONL = ROOT / "testing" / "benchmark" / "semantic_fresh_negatives.jsonl"
OUT_JSON = ROOT / "testing" / "benchmark" / "results" / "backend_comparison.json"

BACKENDS = ["minilm", "sailor"]


def load_cases() -> list[dict]:
    cases = []
    with open(BENCH_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cases.append(
                {
                    "test_id": int(row["test_id"]),
                    "input_text": row["input_text"],
                    "age": int(row["age"]),
                    "cough_type": row["cough_type"].strip() or None,
                    "expected_symptoms": [
                        s.strip() for s in row["expected_symptoms"].split(",") if s.strip()
                    ],
                    "test_category": row["test_category"],
                    "tier": row.get("tier", "").strip(),
                }
            )
    return cases


def run_backend(backend: str, cases: list[dict], tester: AlgorithmTester) -> list[dict]:
    os.environ["MENDO_SEMANTIC_BACKEND"] = backend
    step3_hybrid._SEMANTIC_EXTRACTOR = None  # force the factory to rebuild

    results = []
    for case in cases:
        t0 = time.time()
        trace = predict_symptoms(case["input_text"])
        latency = time.time() - t0

        detected = list(trace["final"].get("symptoms", []) or [])
        detected = tester._apply_cough_override(detected, case["cough_type"])
        eval_result = tester.evaluate_detection(
            detected, case["expected_symptoms"], case["test_category"]
        )

        semantic_stage = next(
            (s for s in trace.get("stages", []) if s.get("stage") == "semantic"), {}
        )
        sem_summary = trace.get("semantic") or {}
        results.append(
            {
                "test_id": case["test_id"],
                "input_text": case["input_text"],
                "tier": case["tier"],
                "expected": case["expected_symptoms"],
                "detected": detected,
                "match_type": eval_result["match_type"],
                "f1": round(eval_result["f1_score"], 4),
                "source": trace["final"].get("source", "unknown"),
                "latency_s": round(latency, 3),
                "sem_used": bool(sem_summary.get("used")),
                "sem_reason": sem_summary.get("reason"),
                "sem_selected": [s["symptom"] for s in sem_summary.get("selected", []) or []],
                "sem_score_type": sem_summary.get("score_type"),
                "engine_id": trace.get("engine", {}).get("engine_id"),
            }
        )
    return results


def load_generalization() -> list[dict]:
    cases = []
    with open(GEN_JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                obj = json.loads(line)
                cases.append(
                    {
                        "text": obj["text"],
                        "expected_symptoms": list(obj["expected"]),
                        "note": obj.get("note", ""),
                    }
                )
    return cases


def run_generalization(backend: str, cases: list[dict]) -> list[dict]:
    """Run the out-of-dictionary paraphrase set (semantic stage decides here)."""
    os.environ["MENDO_SEMANTIC_BACKEND"] = backend
    step3_hybrid._SEMANTIC_EXTRACTOR = None

    results = []
    for case in cases:
        t0 = time.time()
        trace = predict_symptoms(case["text"])
        latency = time.time() - t0

        detected = list(trace["final"].get("symptoms", []) or [])
        expected = case["expected_symptoms"]
        match_type = "exact" if set(detected) == set(expected) else (
            "partial" if detected and set(detected) & set(expected) else "miss"
        )
        sem = trace.get("semantic") or {}
        results.append(
            {
                "text": case["text"],
                "note": case["note"],
                "expected": expected,
                "detected": detected,
                "match_type": match_type,
                "source": trace["final"].get("source", "unknown"),
                "latency_s": round(latency, 3),
                "sem_used": bool(sem.get("used")),
                "sem_selected": [s["symptom"] for s in (sem.get("selected") or [])],
                "sem_vetoed": [
                    s["symptom"]
                    for s in (sem.get("lexical_guard_vetoed") or [])
                    if s.get("score", 0) > 0
                ],
            }
        )
    return results


def summarize(backend: str, results: list[dict]) -> dict:
    exact = sum(1 for r in results if r["match_type"] == "exact")
    partial = sum(1 for r in results if r["match_type"] == "partial")
    failed = sum(1 for r in results if r["match_type"] in ("failed", "false_positive"))
    latencies = [r["latency_s"] for r in results]
    sem_fired = [r for r in results if r["sem_used"]]
    latencies_sorted = sorted(latencies)
    p95 = latencies_sorted[min(len(latencies_sorted) - 1, int(len(latencies_sorted) * 0.95))]
    return {
        "backend": backend,
        "engine_id": results[0]["engine_id"] if results else None,
        "exact": exact,
        "partial": partial,
        "failed": failed,
        "exact_rate": round(exact / len(results), 4) if results else None,
        "latency_mean_s": round(statistics.mean(latencies), 3) if latencies else None,
        "latency_p95_s": round(p95, 3) if latencies else None,
        "semantic_fired_cases": len(sem_fired),
        "semantic_selected_total": sum(len(r["sem_selected"]) for r in sem_fired),
    }


def main() -> None:
    cases = load_cases()
    tester = AlgorithmTester()
    tester.load_dataset()

    runs = {}
    gen_runs = {}
    neg_runs = {}
    fresh_neg_cases = [
        {"text": json.loads(line)["text"], "expected_symptoms": [], "note": json.loads(line).get("note", "")}
        for line in open(NEG_JSONL, encoding="utf-8") if line.strip()
    ]
    for backend in BACKENDS:
        print(f"\n── running backend: {backend} ({len(cases)} cases) ──")
        runs[backend] = run_backend(backend, cases, tester)
        gen_cases = load_generalization()
        print(f"── running backend: {backend} (generalization set, {len(gen_cases)} cases) ──")
        gen_runs[backend] = run_generalization(backend, gen_cases)
        print(f"── running backend: {backend} (fresh negatives, {len(fresh_neg_cases)} cases) ──")
        neg_runs[backend] = run_generalization(backend, fresh_neg_cases)

    summaries = {b: summarize(b, runs[b]) for b in BACKENDS}
    gen_summaries = {}
    neg_summaries = {}
    for b in BACKENDS:
        exact = sum(1 for r in gen_runs[b] if r["match_type"] == "exact")
        gen_summaries[b] = {
            "backend": b,
            "cases": len(gen_runs[b]),
            "exact": exact,
            "exact_rate": round(exact / len(gen_runs[b]), 4),
            "semantic_decided": sum(1 for r in gen_runs[b] if r["sem_used"]),
        }
        clean = sum(1 for r in neg_runs[b] if r["match_type"] == "exact")
        neg_summaries[b] = {
            "backend": b,
            "cases": len(neg_runs[b]),
            "clean": clean,
            "clean_rate": round(clean / len(neg_runs[b]), 4),
        }
    del os.environ["MENDO_SEMANTIC_BACKEND"]

    # ── disagreement analysis ──
    by_id = {b: {r["test_id"]: r for r in runs[b]} for b in BACKENDS}
    disagreements = []
    for case in cases:
        tid = case["test_id"]
        a, b = by_id["minilm"][tid], by_id["sailor"][tid]
        if a["match_type"] != b["match_type"] or set(a["detected"]) != set(b["detected"]):
            disagreements.append(
                {
                    "test_id": tid,
                    "input_text": case["input_text"],
                    "tier": case["tier"],
                    "expected": case["expected_symptoms"],
                    "minilm": {"match": a["match_type"], "detected": a["detected"], "sem": a["sem_selected"], "src": a["source"]},
                    "sailor": {"match": b["match_type"], "detected": b["detected"], "sem": b["sem_selected"], "src": b["source"]},
                }
            )

    payload = {
        "dataset": "testing/benchmark/testing.csv",
        "case_count": len(cases),
        "method": "same 288 cases, all backends, guided cough override, in-process singleton reset",
        "summaries": summaries,
        "generalization": {
            "dataset": "testing/benchmark/semantic_generalization.jsonl",
            "note": "hand-curated out-of-dictionary paraphrases; semantic stage genuinely decides",
            "summaries": gen_summaries,
            "rows": {b: gen_runs[b] for b in BACKENDS},
        },
        "fresh_negatives": {
            "dataset": "testing/benchmark/semantic_fresh_negatives.jsonl",
            "note": "kiosk chit-chat/gibberish; semantic stage must emit nothing",
            "summaries": neg_summaries,
            "rows": {b: neg_runs[b] for b in BACKENDS},
        },
        "disagreement_count": len(disagreements),
        "disagreements": disagreements,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # ── print ──
    print("\n" + "=" * 78)
    print("BACKEND COMPARISON — 288 detection cases (guided)")
    print("=" * 78)
    print(f"{'backend':<10}{'engine':<32}{'exact':>7}{'partial':>9}{'failed':>8}{'rate':>8}{'mean s':>8}{'p95 s':>8}")
    for s in summaries.values():
        print(
            f"{s['backend']:<10}{s['engine_id']:<32}{s['exact']:>7}{s['partial']:>9}"
            f"{s['failed']:>8}{s['exact_rate']:>8.3f}"
            f"{s['latency_mean_s']:>8.3f}{s['latency_p95_s']:>8.3f}"
        )
    print("\nsemantic stage fired (dictionary-miss cases):")
    for s in summaries.values():
        print(
            f"  {s['backend']:<10} fired on {s['semantic_fired_cases']:>3} cases, "
            f"selected {s['semantic_selected_total']:>3} labels total"
        )
    print("\nGENERALIZATION SET (out-of-dictionary paraphrases, semantic decides):")
    for b in BACKENDS:
        gs = gen_summaries[b]
        print(
            f"  {b:<10} exact {gs['exact']:>2}/{gs['cases']} "
            f"({gs['exact_rate']:.1%}), semantic decided {gs['semantic_decided']:>2} cases"
        )
        for r in gen_runs[b]:
            flag = "✓" if r["match_type"] == "exact" else "✗"
            veto = f" [vetoed {r['sem_vetoed']}]" if r["sem_vetoed"] else ""
            print(
                f"    {flag} {r['match_type']:<7} exp={r['expected']} got={r['detected']}"
                f" src={r['source']} sem={r['sem_selected']}{veto}"
            )
    print("\nFRESH NEGATIVES (never in any training set, must emit nothing):")
    for b in BACKENDS:
        ns = neg_summaries[b]
        print(
            f"  {b:<10} clean {ns['clean']:>2}/{ns['cases']} ({ns['clean_rate']:.1%})"
        )
        for r in neg_runs[b]:
            flag = "✓" if r["match_type"] == "exact" else "✗"
            print(f"    {flag} {r['match_type']:<7} got={r['detected']} :: {r['text'][:55]!r}")
    print(f"\ndisagreements between backends: {len(disagreements)}")
    for d in disagreements[:25]:
        print(
            f"  #{d['test_id']:>3} [{d['tier'] or '?'}] {d['input_text'][:48]!r}\n"
            f"      expected={d['expected']}\n"
            f"      minilm  {d['minilm']['match']:<16} {d['minilm']['detected']}  sem={d['minilm']['sem']} src={d['minilm']['src']}\n"
            f"      sailor  {d['sailor']['match']:<16} {d['sailor']['detected']}  sem={d['sailor']['sem']} src={d['sailor']['src']}"
        )
    if len(disagreements) > 25:
        print(f"  ... and {len(disagreements) - 25} more (full list in backend_comparison.json)")
    print(f"\nsaved -> {OUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
