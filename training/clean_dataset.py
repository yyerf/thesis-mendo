"""Clean a JSONL dataset by mapping labels to Mendo canonical labels.

Default: rewrites the input file and creates a .bak backup.

Usage:
  python training/clean_dataset.py --data data/datasets/symptom_eval.sample.jsonl
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, List, Tuple

import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mendo_core.symptom_models import SYMPTOM_LABELS


LABEL_MAP: Dict[str, List[str]] = {
    # Cough variants
    "dry_cough": ["cough"],
    "productive_cough": ["cough"],
    "cough_general": ["cough"],
    "asthmatic_cough": ["cough"],
    "barking_cough": ["cough"],
    "cough_urge": ["cough"],
    # Headache variants
    "severe_headache": ["headache"],
    "throbbing_headache": ["headache"],
    "migraine": ["headache"],
    "severe_migraine": ["headache"],
    "cold_induced_headache": ["headache"],
    # Fever variants
    "mild_fever": ["fever"],
    "high_fever": ["fever"],
    "relapse_fever": ["fever"],
    "flu_symptoms": ["fever"],
    "chills": ["fever"],
    # Throat / voice
    "itchy_throat": ["sore_throat"],
    "tickly_throat": ["sore_throat"],
    "odynophagia": ["sore_throat"],
    "throat_obstruction": ["sore_throat"],
    "throat_lump": ["sore_throat"],
    "loss_of_voice": ["sore_throat"],
    "hoarseness": ["sore_throat"],
    # Nose
    "nasal_congestion": ["stuffy_nose"],
    "congestion": ["stuffy_nose"],
    # Stomach
    "stomach_pain": ["stomach_ache"],
    "stomach_cramps": ["stomach_ache"],
    "severe_stomach_pain": ["stomach_ache"],
    "hyperacidity": ["stomach_ache"],
    "acid_reflux": ["stomach_ache"],
    "gerd": ["stomach_ache"],
    "heartburn": ["stomach_ache"],
    "gastric_pain": ["stomach_ache"],
    "epigastric_pain": ["stomach_ache"],
    "stomach_gurgling": ["stomach_ache"],
    # Body aches
    "muscle_pain": ["body_aches"],
    "muscle_strain": ["body_aches"],
    "muscle_soreness": ["body_aches"],
    "severe_body_aches": ["body_aches"],
    # Dizziness
    "vertigo": ["dizziness"],
    "fainting_sensation": ["dizziness"],
    "blacking_out": ["dizziness"],
    "brain_fog": ["dizziness"],
    # Nausea/Vomiting
    "vomiting": ["vomiting"],
    "nausea": ["nausea"],
    # Diarrhea
    "diarrhea_precursor": ["diarrhea"],
    # Chest
    "chest_pressure": ["chest_pain"],
    "sharp_chest_pain": ["chest_pain"],
    "pricking_chest_pain": ["chest_pain"],
    # Breathing
    "difficulty_breathing": ["shortness_of_breath"],
    # Fatigue
    "weakness": ["fatigue"],
    "lethargy": ["fatigue"],
}


def _resolve(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (ROOT_DIR / path).resolve()


def _parse_json_line(line: str) -> dict:
    raw = line.strip()
    if not raw:
        return {}
    if raw.endswith(","):
        raw = raw[:-1]
    return json.loads(raw)


def _map_labels(raw_labels: List[str]) -> Tuple[List[str], List[str]]:
    mapped: List[str] = []
    dropped: List[str] = []
    for lbl in raw_labels:
        key = (lbl or "").strip().lower()
        if not key:
            continue
        if key in SYMPTOM_LABELS:
            mapped.append(key)
        elif key in LABEL_MAP:
            mapped.extend(LABEL_MAP[key])
        else:
            dropped.append(key)
    mapped = sorted(set([m for m in mapped if m in SYMPTOM_LABELS]))
    return mapped, dropped


def main() -> int:
    parser = argparse.ArgumentParser(description="Clean JSONL dataset labels")
    parser.add_argument(
        "--data",
        type=str,
        default="data/datasets/symptom_eval.sample.jsonl",
        help="Path to JSONL dataset",
    )
    parser.add_argument(
        "--out",
        type=str,
        default="",
        help="Optional output path. If empty, rewrite input and create .bak",
    )
    args = parser.parse_args()

    data_path = _resolve(args.data)
    out_path = _resolve(args.out) if args.out else data_path

    if out_path == data_path:
        backup = data_path.with_suffix(data_path.suffix + ".bak")
        shutil.copy2(data_path, backup)

    total = 0
    kept = 0
    dropped_counts: Dict[str, int] = {}
    rows_with_empty = 0
    errors = 0

    cleaned_lines: List[str] = []

    with data_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            total += 1
            try:
                obj = _parse_json_line(line)
            except Exception:
                errors += 1
                continue

            text = (obj.get("text") or "").strip()
            labels = obj.get("labels") or []
            if not isinstance(labels, list):
                labels = []

            mapped, dropped = _map_labels(labels)
            if dropped:
                for d in dropped:
                    dropped_counts[d] = dropped_counts.get(d, 0) + 1

            if not mapped:
                rows_with_empty += 1

            record = {
                "id": obj.get("id") or f"row_{total}",
                "text": text,
                "labels": mapped,
            }
            cleaned_lines.append(json.dumps(record, ensure_ascii=False))
            if mapped:
                kept += 1

    out_path.write_text("\n".join(cleaned_lines) + "\n", encoding="utf-8")

    print("=== Clean Complete ===")
    print(f"Input rows: {total}")
    print(f"Rows with labels kept: {kept}")
    print(f"Rows with empty labels: {rows_with_empty}")
    print(f"Parse errors skipped: {errors}")
    if dropped_counts:
        top = sorted(dropped_counts.items(), key=lambda x: x[1], reverse=True)
        print("\nDropped label counts (top 20):")
        for name, count in top[:20]:
            print(f"  {name}: {count}")

    print(f"\nOutput JSONL: {out_path}")
    if out_path == data_path:
        print(f"Backup created: {data_path.with_suffix(data_path.suffix + '.bak')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
