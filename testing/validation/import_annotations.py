"""import_annotations.py — ingest pharmacist-annotated validation exports.

Validates an annotated export (CSV or JSONL) and appends accepted rows to
testing/benchmark/pharmacist_validated.jsonl, the Iteration-2 corpus used
as an evaluation/validation resource for the detection pipeline.

Annotation format (CSV):
  id,input,expected
  mendo-3f9a...,"masakit ulo ko","HEADACHE"

  - id: the export's anonymized id (sha256 of input) — verified
  - expected: comma-separated symptom labels from the 14-label set,
    or "NONE" for no symptom; empty cell -> row is skipped (not annotated)

Accepted labels: HEADACHE, FEVER, COUGH_GENERAL, COUGH_DRY, COUGH_PRODUCTIVE,
SORE_THROAT, STOMACH_ACHE, BODY_ACHES, DIARRHEA, NASAL_CONGESTION,
RUNNY_NOSE, RASHES, ALLERGIC_RHINITIS, TOOTHACHE.

Usage:
  python testing/validation/import_annotations.py --in annotated.csv \
      --out testing/benchmark/pharmacist_validated.jsonl
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

LABELS = {
    "HEADACHE", "FEVER", "COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE",
    "SORE_THROAT", "STOMACH_ACHE", "BODY_ACHES", "DIARRHEA",
    "NASAL_CONGESTION", "RUNNY_NOSE", "RASHES", "ALLERGIC_RHINITIS",
    "TOOTHACHE",
}


def check_id(case_id: str, text: str) -> bool:
    if not case_id or not case_id.startswith("mendo-"):
        return False
    expect = "mendo-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return case_id == expect


def parse_expected(raw: str) -> list[str] | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.upper() == "NONE":
        return []
    labels = []
    for part in raw.split(","):
        lab = part.strip().upper()
        if lab not in LABELS:
            raise ValueError(f"unknown label {lab!r} in {raw!r}")
        if lab not in labels:
            labels.append(lab)
    return labels


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in open(path, encoding="utf-8")]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("Usage:")[0])
    ap.add_argument("--in", dest="src", type=Path, required=True)
    ap.add_argument("--out", type=Path,
                    default=ROOT / "testing" / "benchmark" / "pharmacist_validated.jsonl")
    args = ap.parse_args()

    if args.src.suffix.lower() == ".csv":
        recs = list(csv.DictReader(open(args.src, encoding="utf-8-sig")))
    else:
        recs = read_jsonl(args.src)

    accepted, skipped = [], []
    for i, rec in enumerate(recs):
        case = (rec.get("id") or "").strip()
        text = (rec.get("input") or "").strip()
        raw_exp = rec.get("expected")
        if not text:
            skipped.append((i, "empty input"))
            continue
        if not check_id(case, text):
            skipped.append((i, f"id mismatch: {case!r}"))
            continue
        try:
            exp = parse_expected(raw_exp)
        except ValueError as exc:
            skipped.append((i, str(exc)))
            continue
        if exp is None:
            skipped.append((i, "not annotated"))
            continue
        accepted.append({"id": case, "input": text, "expected": exp})

    existing: dict[str, dict] = {}
    if args.out.exists():
        for rec in read_jsonl(args.out):
            existing[rec["id"]] = rec
    dup = 0
    for rec in accepted:
        if rec["id"] in existing:
            dup += 1
            continue
        existing[rec["id"]] = rec

    with open(args.out, "w", encoding="utf-8") as f:
        for rec in sorted(existing.values(), key=lambda r: r["id"]):
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    from collections import Counter
    hist: Counter[str] = Counter()
    for rec in existing.values():
        for lab in rec["expected"]:
            hist[lab] += 1

    print(f"rows read: {len(recs)}")
    print(f"accepted: {len(accepted)}  duplicates skipped: {dup}  "
          f"rejected: {len(skipped)}")
    for i, reason in skipped:
        print(f"  skip row {i}: {reason}")
    print(f"corpus now: {len(existing)} rows -> {args.out}")
    for lab in sorted(LABELS):
        if hist.get(lab):
            print(f"  {lab:<20} {hist[lab]}")


if __name__ == "__main__":
    main()
