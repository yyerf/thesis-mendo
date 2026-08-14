"""export_validation_set.py — build an anonymized pharmacist validation export.

Iteration-2 field validation (pharmacist-annotated, human-derived accuracy):
this tool packages kiosk-style inputs into a de-identified export for a
licensed pharmacist to annotate with expected symptom labels.

Privacy (RA 10173 / PH Data Privacy Act):
  - Each row is identified ONLY by "mendo-" + sha256(input)[:16]. No patient
    name, age, or transaction data is ever included.
  - Raw inputs are clinical in nature (they describe symptoms). Keep the
    export file on the device / secured research storage; do not commit it.
  - The exported "expected" field is null for the annotator to fill.

Sources (in order): optional kiosk log (logs/interactions.jsonl) then
benchmark inputs. Stratified sampling keeps all 13 labels represented.

Usage:
  python testing/validation/export_validation_set.py --max 100 --seed 7 \
      --out testing/validation/export_validation.jsonl

Schema (JSONL, one row per case):
  {"id": "mendo-3f9a...", "input": "...", "detected": [...],
   "engine_id": "...", "engine_available": true, "latency_ms": 12.3,
   "expected": null, "source": "log|benchmark"}
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

SYMPTOM_LABELS = {
    "HEADACHE", "FEVER", "COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE",
    "SORE_THROAT", "STOMACH_ACHE", "BODY_ACHES", "DIARRHEA",
    "NASAL_CONGESTION", "RUNNY_NOSE", "RASHES", "ALLERGIC_RHINITIS",
    "TOOTHACHE",
}


def case_id(text: str) -> str:
    return "mendo-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def load_log_rows() -> list[dict]:
    """Rows from logs/interactions.jsonl (safe no-op when absent)."""
    rows = []
    path = ROOT / "logs" / "interactions.jsonl"
    if not path.exists():
        return rows
    for line in open(path, encoding="utf-8"):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        text = rec.get("input") or rec.get("text") or rec.get("user_input")
        if not text or not str(text).strip():
            continue
        detected = rec.get("detected") or rec.get("symptoms") or rec.get("labels") or []
        engine = rec.get("engine_id") or rec.get("engine") or "unknown"
        latency = rec.get("latency_ms")
        rows.append({
            "input": str(text).strip(),
            "detected": sorted({d for d in detected if d in SYMPTOM_LABELS}),
            "engine_id": engine,
            "latency_ms": latency,
            "source": "log",
        })
    return rows


def load_benchmark_rows() -> list[dict]:
    """Rows from the 288-case benchmark (known-good coverage of all labels)."""
    rows = []
    path = ROOT / "testing" / "benchmark" / "testing.csv"
    if not path.exists():
        return rows
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            text = row["input_text"].strip()
            if not text:
                continue
            exp = [e for e in row["expected_symptoms"].upper().split(",") if e]
            rows.append({
                "input": text,
                "detected": [],
                "engine_id": "benchmark-synthetic",
                "latency_ms": None,
                "source": "benchmark",
            })
    return rows


def annotate(rows: list[dict]) -> list[dict]:
    """Run the live pipeline on each row to record honest detected + latency."""
    from mendo_core.prediction_pipeline import predict_symptoms

    out = []
    for r in rows:
        t0 = time.perf_counter()
        report = predict_symptoms(r["input"])
        dt = (time.perf_counter() - t0) * 1000.0
        detected = [s for s in report["final"]["symptoms"] if s in SYMPTOM_LABELS]
        out.append({
            **r,
            "detected": sorted(detected),
            "engine_id": report.get("semantic", {}).get("engine_id", "dictionary-only"),
            "engine_available": report.get("semantic", {}).get("available", False),
            "latency_ms": round(dt, 2),
        })
    return out


def stratify(rows: list[dict], max_n: int, rng: random.Random) -> list[dict]:
    """Stratified sample: every label keeps >=1 representative when present."""
    by_label: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        for lab in r["detected"]:
            by_label[lab].append(r)
    chosen: list[dict] = []
    seen = set()
    for lab, bucket in sorted(by_label.items()):
        pool = [r for r in bucket if r["id"] not in seen]
        if not pool:
            continue
        pick = rng.choice(pool)
        chosen.append(pick)
        seen.add(pick["id"])
    rest = [r for r in rows if r["id"] not in seen]
    rng.shuffle(rest)
    for r in rest:
        if len(chosen) >= max_n:
            break
        chosen.append(r)
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("Usage:")[0])
    ap.add_argument("--max", type=int, default=100)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=Path, default=ROOT / "testing" / "validation" / "export_validation.jsonl")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    raw = load_log_rows() + load_benchmark_rows()
    if not raw:
        print("no source rows found (no kiosk log, no benchmark csv)")
        sys.exit(1)
    seen_inputs = set()
    dedup = []
    for r in raw:
        key = r["input"].lower().strip()
        if key in seen_inputs:
            continue
        seen_inputs.add(key)
        dedup.append(r)
    print(f"candidate inputs: {len(dedup)} (log={len(load_log_rows())}, "
          f"benchmark={len(load_benchmark_rows())})")

    print("running live pipeline (this loads the semantic model) ...")
    annotated = annotate(dedup)
    labeled = [
        {**r, "id": case_id(r["input"]), "expected": None}
        for r in annotated
    ]
    sampled = stratify(labeled, args.max, rng)
    print(f"label histogram in export:")
    hist: Counter[str] = Counter()
    for r in sampled:
        for lab in r["detected"]:
            hist[lab] += 1
    for lab in sorted(SYMPTOM_LABELS):
        print(f"  {lab:<20} {hist.get(lab, 0)}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        for r in sampled:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"wrote {len(sampled)} rows -> {args.out}")
    print("NOTE: inputs are clinical in nature; keep this file secured (RA 10173).")


if __name__ == "__main__":
    main()
