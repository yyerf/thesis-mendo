"""Validate JSONL dataset labels against Mendo canonical labels.

Usage:
  python training/validate_dataset.py --data data/datasets/symptom_eval.sample.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mendo_core.symptom_models import SYMPTOM_LABELS


def _resolve(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (ROOT_DIR / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate dataset labels")
    parser.add_argument(
        "--data",
        type=str,
        default="data/datasets/symptom_eval.sample.jsonl",
        help="Path to JSONL dataset",
    )
    args = parser.parse_args()

    data_path = _resolve(args.data)

    unknown_labels: Dict[str, int] = {}
    total = 0
    rows_with_unknown = 0

    with data_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            total += 1
            obj = json.loads(line)
            labels = obj.get("labels") or []
            bad = [lbl for lbl in labels if lbl not in SYMPTOM_LABELS]
            if bad:
                rows_with_unknown += 1
                for b in bad:
                    unknown_labels[b] = unknown_labels.get(b, 0) + 1

    print("=== Dataset Validation ===")
    print(f"Rows: {total}")
    print(f"Rows with unknown labels: {rows_with_unknown}")
    if unknown_labels:
        print("\nUnknown label counts (top 20):")
        for label, count in sorted(unknown_labels.items(), key=lambda x: x[1], reverse=True)[:20]:
            print(f"  {label}: {count}")
    else:
        print("All labels are canonical.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
