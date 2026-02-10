"""Generate a synthetic JSONL dataset with canonical labels only.

Usage:
  python training/generate_synthetic_dataset.py \
    --out data/datasets/symptom_eval.synthetic.jsonl \
    --max 300
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Tuple

import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mendo_core.symptom_models import SYMPTOM_LABELS


TEMPLATES = {
    "cough": [
        "Ubo ako",
        "Umuubo ako since yesterday",
        "Coughing ako, walang tigil",
        "May ubo ako",
        "Kahapon pa ako umuubo",
        "Ubo ng ubo",
        "Dry cough ako",
        "Ubo with plema",
    ],
    "headache": [
        "Masakit ulo ko",
        "Labad ulo ko",
        "Headache ako ngayon",
        "My head hurts",
        "Sumasakit ang ulo ko",
        "Sakit ng ulo ko",
        "Headache and stress",
    ],
    "fever": [
        "May lagnat ako",
        "Nilalagnat ako",
        "Mainit ang katawan ko",
        "I have fever",
        "Sinat lang siguro",
        "Parang may lagnat",
    ],
    "sore_throat": [
        "Masakit lalamunan ko",
        "Makati lalamunan ko",
        "Sore throat",
        "My throat is sore",
        "Sakit ng lalamunan",
    ],
    "runny_nose": [
        "May sipon ako",
        "Sipon lang",
        "Runny nose",
        "Sinisipon ako",
        "Tumutulo ilong ko",
    ],
    "stuffy_nose": [
        "Barado ilong ko",
        "Stuffy nose",
        "Nasal congestion",
        "Hirap huminga dahil barado ilong",
    ],
    "dizziness": [
        "Nahihilo ako",
        "Dizzy ako",
        "Parang umiikot ulo ko",
        "Hilo ko",
    ],
    "nausea": [
        "Nasusuka ako",
        "Nauseous ako",
        "Parang masusuka",
        "Naduduwal ako",
    ],
    "vomiting": [
        "Sumusuka ako",
        "Nagvomit ako",
        "Pagsusuka since umaga",
        "Vomiting ako",
    ],
    "diarrhea": [
        "Nagtatae ako",
        "Loose stool ako",
        "Diarrhea since yesterday",
        "Pabalik balik CR",
    ],
    "fatigue": [
        "Pagod na pagod ako",
        "Walang energy",
        "I feel tired",
        "Hina ng katawan",
    ],
    "body_aches": [
        "Masakit katawan ko",
        "Body aches",
        "Ngawngaw katawan",
        "Sakit ng katawan",
    ],
    "shortness_of_breath": [
        "Hirap huminga",
        "Shortness of breath",
        "Nangingibabaw ang hininga",
        "Di ako makahinga nang maayos",
    ],
    "chest_pain": [
        "Masakit dibdib ko",
        "Chest pain",
        "Sakit sa dibdib",
    ],
    "stomach_ache": [
        "Masakit tiyan ko",
        "Stomach ache",
        "Sakit ng tiyan",
        "Sumasakit sikmura ko",
    ],
}

COMBOS: List[Tuple[List[str], str]] = [
    (["cough", "fever"], "May ubo at lagnat ako"),
    (["cough", "runny_nose"], "Ubo at sipon"),
    (["fever", "headache"], "Lagnat at sakit ng ulo"),
    (["runny_nose", "stuffy_nose"], "Sipon at barado ilong"),
    (["dizziness", "nausea"], "Nahihilo ako at nasusuka"),
    (["diarrhea", "stomach_ache"], "Nagtatae ako at masakit tiyan"),
    (["body_aches", "fever"], "Masakit katawan ko at nilalagnat"),
    (["sore_throat", "cough"], "Masakit lalamunan at ubo"),
    (["stuffy_nose", "headache"], "Barado ilong ko at sakit ulo"),
    (["fatigue", "headache"], "Pagod ako at masakit ulo"),
    (["shortness_of_breath", "chest_pain"], "Hirap huminga at masakit dibdib"),
]


def _resolve(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (ROOT_DIR / path).resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate synthetic dataset")
    parser.add_argument(
        "--out",
        type=str,
        default="data/datasets/symptom_eval.synthetic.jsonl",
        help="Output JSONL path",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=300,
        help="Maximum number of rows to generate",
    )
    args = parser.parse_args()

    out_path = _resolve(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows: List[dict] = []
    idx = 1

    for label, phrases in TEMPLATES.items():
        if label not in SYMPTOM_LABELS:
            continue
        for text in phrases:
            rows.append({"id": f"syn{idx:04d}", "text": text, "labels": [label]})
            idx += 1

    for labels, text in COMBOS:
        if all(l in SYMPTOM_LABELS for l in labels):
            rows.append({"id": f"syn{idx:04d}", "text": text, "labels": labels})
            idx += 1

    # Repeat with slight variants to reach max
    variants = [
        "kanina pa",
        "since yesterday",
        "medyo",
        "grabe",
        "pero ok naman",
        "tapos",
        "ngayon",
        "kagabi pa",
    ]

    base_rows = rows.copy()
    for v in variants:
        for r in base_rows:
            if len(rows) >= args.max:
                break
            rows.append({
                "id": f"syn{idx:04d}",
                "text": f"{r['text']} {v}",
                "labels": r["labels"],
            })
            idx += 1
        if len(rows) >= args.max:
            break

    rows = rows[: args.max]

    with out_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"Generated {len(rows)} rows -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
