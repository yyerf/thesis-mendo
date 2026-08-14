"""run_evidence.py — single reproducible evidence run for the thesis.

Assembles every measured number into one JSON + a markdown report:
  Suite A  288-case detection benchmark (guided pipeline w/ clarification)
  Suite B  520-case multilingual sheet (per-language exact)
  Suite C  held-out 16 paraphrases (guarded pipeline, cosine-anchor backend)
  Suite D  held-out 20 fresh negatives (pipeline emissions)
  Suite E  duration safeguard (Tier 5, 31 cases)
  Suite F  headache intake (60 tests)
  Suite G  pytest regression suites

Everything is pinned in the report: python/torch/transformers versions,
MENDO_SEMANTIC_BACKEND, engine id, anchor counts, and data-file hashes.

Usage:
  python testing/run_evidence.py                # full run (loads the model)
  python testing/run_evidence.py --reuse        # skip suites, rebuild report
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

OUT = ROOT / "testing" / "benchmark" / "results" / "evidence.json"
REPORT = ROOT / "testing" / "benchmark" / "results" / "evidence_report.md"

DATA_FILES = [
    "testing/benchmark/testing.csv",
    "testing/benchmark/test_xlsx_cases.jsonl",
    "testing/benchmark/semantic_generalization.jsonl",
    "testing/benchmark/semantic_fresh_negatives.jsonl",
    "testing/benchmark/idiom_enrichment.jsonl",
    "testing/benchmark/duration_cases.csv",
    "data/Mendo-Datasets.json",
]

PY = sys.executable
SUITES = {
    "A": [PY, "-X", "utf8", "testing/test_algorithm.py"],
    "B": [PY, "-X", "utf8", "testing/eval_xlsx_suite.py"],
    "E": [PY, "-X", "utf8", "testing/test_duration.py"],
    "F": [PY, "-X", "utf8", "testing/test_headache_intake.py"],
    "G": [PY, "-X", "utf8", "-m", "pytest", "testing/test_regressions.py", "-q"],
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def run_suite(name: str, cmd: list[str]) -> dict:
    t0 = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=ROOT)
    dt = round(time.perf_counter() - t0, 2)
    out = (proc.stdout or "") + (proc.stderr or "")
    tail = [ln for ln in out.splitlines() if ln.strip()][-12:]
    return {"name": name, "cmd": " ".join(cmd), "exit": proc.returncode,
            "seconds": dt, "tail": tail}


def parse_288(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    m = data.get("metrics", {})
    return {
        "engine_id": data.get("engine_id"),
        "raw": m.get("raw_input", {}),
        "guided": m.get("guided_workflow", {}),
        "overall": data.get("overall_stats", {}),
    }


def parse_520(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    per_lang: dict[str, dict] = {}
    for r in data.get("results", []):
        b = per_lang.setdefault(r.get("lang", "?"),
                                {"ok": 0, "total": 0})
        b["total"] += 1
        b["ok"] += int(bool(r.get("ok")))
    return {"engine_id": data.get("engine_id"), "total": data.get("total"),
            "ok": data.get("ok"), "per_language": per_lang}


def run_model_suites() -> dict:
    from mendo_core.prediction_pipeline import predict_symptoms
    from mendo_core.step2 import SYMPTOM_ANCHORS
    from mendo_core.step3_hybrid import extract_symptoms_hybrid

    gen = [json.loads(l) for l in open(
        ROOT / "testing" / "benchmark" / "semantic_generalization.jsonl",
        encoding="utf-8")]
    neg = [json.loads(l) for l in open(
        ROOT / "testing" / "benchmark" / "semantic_fresh_negatives.jsonl",
        encoding="utf-8")]

    norm = lambda s: "BODY_ACHES" if s == "BODY_ACHE" else s

    # C: guarded full pipeline (dictionary-first + precision-first fallback,
    # cosine-anchor MiniLM backend).
    c_guarded, c_guarded_cases = 0, []
    for g in gen:
        det = extract_symptoms_hybrid(g["text"])
        exp = {norm(e.upper()) for e in g["expected"]}
        ok = set(det) == exp
        c_guarded += int(ok)
        c_guarded_cases.append({"text": g["text"], "exact": ok,
                                "expected": sorted(exp), "detected": sorted(det)})

    d_clean, d_fp = 0, []
    for n in neg:
        det = extract_symptoms_hybrid(n["text"])
        if det:
            d_fp.append({"text": n["text"], "detected": sorted(det)})
        else:
            d_clean += 1

    return {
        "anchor_sentences_total": sum(
            len(phrases) for phrases in SYMPTOM_ANCHORS.values()),
        "anchor_sentences_per_symptom": {
            symptom: len(phrases) for symptom, phrases in SYMPTOM_ANCHORS.items()},
        "C_guarded_16": {"exact": c_guarded, "total": len(gen)},
        "C_guarded_cases": c_guarded_cases,
        "D_fresh_negatives": {"clean": d_clean, "fp": d_fp, "total": len(neg)},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reuse", action="store_true",
                    help="skip suite subprocesses; rebuild report only")
    args = ap.parse_args()

    env = {
        "backend": __import__("os").environ.get(
            "MENDO_SEMANTIC_BACKEND", "minilm"),
        "engine_id": None,
        "python": platform.python_version(),
        "torch": None, "transformers": None, "sentence_transformers": None,
    }
    try:
        import torch, transformers
        env["torch"] = torch.__version__
        env["transformers"] = transformers.__version__
        try:
            import sentence_transformers
            env["sentence_transformers"] = sentence_transformers.__version__
        except ImportError:
            pass
    except ImportError:
        pass
    try:
        from mendo_core.prediction_pipeline import predict_symptoms
        env["engine_id"] = predict_symptoms("sakit ng isa kong ngipin sa tabi"
                                            ).get("engine", {}).get(
                                                "engine_id", "unknown")
    except Exception:
        pass

    data_hashes = {p: sha256(ROOT / p) for p in DATA_FILES}

    suites = {}
    if not args.reuse:
        for name, cmd in SUITES.items():
            suites[name] = run_suite(name, cmd)
            print(f"suite {name} done: exit={suites[name]['exit']} "
                  f"({suites[name]['seconds']}s)")
        model_results = run_model_suites()
        print("model suites done")
    elif OUT.exists():
        prev = json.loads(OUT.read_text(encoding="utf-8"))
        suites = prev.get("suites", {})
        model_results = prev.get("model", {"reused": True})
    else:
        model_results = {"reused": True}

    # Read suite result artifacts (freshly written or reused).
    try:
        c288 = parse_288(ROOT / "testing" / "benchmark" / "results" / "current.json")
    except Exception:
        c288 = {"error": "current.json unreadable"}
    try:
        c520 = parse_520(ROOT / "testing" / "benchmark" / "results" / "xlsx_suite_results.json")
    except Exception:
        c520 = {"error": "xlsx_suite_results.json unreadable"}

    evidence = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "env": env,
        "data_hashes": data_hashes,
        "A_288": c288,
        "B_520": c520,
        "E_duration": suites.get("E", {"reused": True}),
        "F_headache": suites.get("F", {"reused": True}),
        "G_pytest": suites.get("G", {"reused": True}),
        "model": model_results if not args.reuse else {"reused": True},
        "suites": suites,
    }
    OUT.write_text(json.dumps(evidence, ensure_ascii=False, indent=1),
                   encoding="utf-8")

    h = evidence["model"]
    lines = [
        "# MendoVendo Evidence Run", "",
        f"Generated {evidence['generated']}  |  backend "
        f"`{env['backend']}`  |  engine `{env['engine_id']}`  |  ",
        f"python {env['python']} / torch {env['torch']} / "
        f"transformers {env['transformers']}", "",
        "## Results", "",
    ]
    a = evidence["A_288"]
    raw = a.get("raw", {})
    guided = a.get("guided", {})
    lines.append(f"- **A. 288 benchmark (engine {a.get('engine_id')}):** "
                 f"guided {guided.get('exact_match_rate')} exact "
                 f"(raw input {raw.get('exact_match_rate')}; micro "
                 f"P {raw.get('micro_precision'):.3f} "
                 f"R {raw.get('micro_recall'):.3f} "
                 f"F1 {raw.get('micro_f1'):.3f}, "
                 f"macro F1 {raw.get('macro_f1'):.3f})")
    b = evidence["B_520"]
    per = ", ".join(f"{k} {v['ok']}/{v['total']}"
                    for k, v in b.get("per_language", {}).items())
    lines.append(f"- **B. 520 sheet (engine {b.get('engine_id')}):** "
                 f"{b.get('ok')}/{b.get('total')} ({per})")
    if not args.reuse:
        m = evidence["model"]
        lines += [
            f"- **C. 16 paraphrases:** guarded pipeline "
            f"{m['C_guarded_16']['exact']}/16 "
            f"(BODY_ACHE->BODY_ACHES canonicalized; cosine-anchor backend, "
            f"{m['anchor_sentences_total']} anchors, threshold 0.65)",
            f"- **D. 20 fresh negatives:** {m['D_fresh_negatives']['clean']}/20 "
            f"clean ({len(m['D_fresh_negatives']['fp'])} FP)",
            f"- **anchors:** {m['anchor_sentences_total']} total "
            f"({json.dumps(m['anchor_sentences_per_symptom'], ensure_ascii=False)})",
        ]
    for name in ("E", "F", "G"):
        s = evidence["suites"].get(name, {})
        tail = (s.get("tail") or [])[-1] if s.get("tail") else ""
        lines.append(f"- **{name}.** exit={s.get('exit')} "
                     f"({s.get('seconds')}s) last line: `{tail}`")
    lines += ["", "## Data fingerprints"]
    for path, sig in data_hashes.items():
        lines.append(f"- `{path}` sha256[:16] `{sig}`")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"evidence -> {OUT}")
    print(f"report  -> {REPORT}")


if __name__ == "__main__":
    main()