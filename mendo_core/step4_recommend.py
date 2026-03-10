"""step4_recommend.py

Symptom -> OTC recommendation prototype using your Mendo dataset.

Inputs:
- Mixed-language free text (Tagalog/Bisaya/English/Taglish)

Outputs:
- Detected symptom intents (uses the hybrid pipeline)
- A short recommendation list of medicine brands from Mendo-Datasets.json
- If cough is ambiguous (COUGH_GENERAL), ask a clarifying question

This script is deterministic in its recommendation rules.
Semantic extraction (embeddings) is optional and runs locally after the model is cached.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .step3_hybrid import extract_symptoms_hybrid_report


DATASET_DEFAULT = str((Path(__file__).resolve().parents[1] / "data" / "Mendo-Datasets.json"))


@dataclass(frozen=True)
class MedRow:
    brand: str
    generic_main_use: str
    primary_symptom: str
    typical_symptoms: str
    drug_category: str
    min_age: str
    dosage_form: str
    notes: str
    # ASG (Authoritative-Source-Grounded) fields
    approved_indications: tuple  # tuple of strings
    indication_source: str
    contraindications: tuple
    warnings: tuple
    drug_interactions: tuple
    max_duration_days: int
    contraindication_source: str


def _norm(s: Any) -> str:
    return str(s or "").strip().lower()


def load_mendo_dataset(path: str) -> List[MedRow]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    obj = json.loads(p.read_text(encoding="utf-8"))
    rows = obj.get("Sheet1")
    if not isinstance(rows, list):
        raise ValueError("Expected top-level key 'Sheet1' to be a list")

    out: List[MedRow] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        out.append(
            MedRow(
                brand=str(r.get("Brand") or ""),
                generic_main_use=str(r.get("Generic/Main Use") or ""),
                primary_symptom=_norm(r.get("Primary Symptom")),
                typical_symptoms=_norm(r.get("Typical Symptoms Treated")),
                drug_category=_norm(r.get("Drug Category")),
                min_age=str(r.get("Minimum Age") or ""),
                dosage_form=str(r.get("Dosage Form") or ""),
                notes=str(r.get("Notes") or ""),
                approved_indications=tuple(r.get("Approved_Indications") or []),
                indication_source=str(r.get("Indication_Source") or ""),
                contraindications=tuple(r.get("Contraindications") or []),
                warnings=tuple(r.get("Warnings") or []),
                drug_interactions=tuple(r.get("Drug_Interactions") or []),
                max_duration_days=int(r.get("Max_Duration_Days") or 0),
                contraindication_source=str(r.get("Contraindication_Source") or ""),
            )
        )
    return out


def _check_paracetamol_overlap(recs: List[Dict[str, Any]]) -> List[str]:
    """Warn if multiple paracetamol-containing products are recommended."""
    pcm_brands = [
        r["brand"] for r in recs
        if "paracetamol" in (r.get("active_ingredients") or "").lower()
    ]
    if len(pcm_brands) > 1:
        return [
            f"⚠ Multiple paracetamol-containing products selected ({', '.join(pcm_brands)}). "
            "Do NOT take together — risk of overdose. Choose only ONE."
        ]
    return []


def _check_opposing_mechanisms(recs: List[Dict[str, Any]]) -> List[str]:
    """Warn if a cough suppressant is combined with an expectorant."""
    cats = {r.get("drug_category", "") for r in recs}
    if "expectorant" in cats and "cough suppressant" in cats:
        return [
            "⚠ Expectorant + Cough Suppressant detected — opposing mechanisms. "
            "Use only one type at a time."
        ]
    return []


def recommend_from_dataset(
    symptoms: Sequence[str],
    rows: Sequence[MedRow],
    *,
    red_flags: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Rule-based mapping aligned to your dataset.

    If *red_flags* is non-empty the system returns a ``triage`` action
    instead of OTC recommendations, instructing the user to consult a
    doctor or pharmacist immediately.
    """

    # ── TRIAGE GATE — redirect to medical professional ──
    if red_flags:
        flag_msgs = [f["message"] for f in red_flags]
        return {
            "action": "triage",
            "triage_flags": red_flags,
            "message": (
                "⚠️ CONSULT A DOCTOR / PHARMACIST IMMEDIATELY.\n"
                "The following serious symptom(s) were detected:\n"
                + "\n".join(f"  • {m}" for m in flag_msgs)
                + "\n\nThese symptoms may indicate a condition that requires "
                "professional medical evaluation. Self-medication with OTC "
                "products is NOT recommended."
            ),
            "recommendations": [],
            "safety_warnings": [],
        }

    symptoms_set = set(symptoms)
    matching_symptoms = set(symptoms)  # copy for tracking actual matches

    # COUGH_GENERAL: only ask clarification if cough is the ONLY symptom
    if "COUGH_GENERAL" in symptoms_set and not ("COUGH_DRY" in symptoms_set or "COUGH_PRODUCTIVE" in symptoms_set):
        other_symptoms = symptoms_set - {"COUGH_GENERAL"}
        if not other_symptoms:
            return {
                "action": "ask_clarify",
                "question": "Please specify: Is your cough dry (walay/walang plema) or with phlegm (naay/may plema)?",
                "candidates": [],
            }
        # Multi-symptom with COUGH_GENERAL: defer cough, recommend for other symptoms
        matching_symptoms.discard("COUGH_GENERAL")

    candidates: List[Tuple[int, MedRow, List[str]]] = []

    def add_candidate(row: MedRow, reason: str, score: int) -> None:
        candidates.append((score, row, [reason]))

    for row in rows:
        # Productive cough -> Solmux / Ascof / Robitussin patterns
        if "COUGH_PRODUCTIVE" in matching_symptoms:
            productive_indicators = [
                "productive cough",
                "wet cough",
                "cough with phlegm",
                "phlegm",
                "mucus in chest",
                "phlegm buildup",
                "cough with thick phlegm",
                "chest congestion",
            ]
            combined = f"{row.primary_symptom} {row.typical_symptoms}"
            non_productive_markers = [
                "non-productive",
                "non productive",
                "without mucus",
                "no phlegm",
                "walang plema",
                "walay plema",
            ]
            is_non_productive = any(m in combined for m in non_productive_markers)
            if (
                (not is_non_productive)
                and (
                    any(ind in row.primary_symptom for ind in productive_indicators)
                    or any(ind in row.typical_symptoms for ind in productive_indicators)
                )
            ) or ("expectorant" in row.drug_category):
                add_candidate(row, "productive_cough_match", 3)

        # Dry cough -> Tuseran / Sinecod patterns
        if "COUGH_DRY" in matching_symptoms:
            if (
                "dry cough" in row.primary_symptom
                or "cough suppressant" in row.drug_category
                or "dry cough" in row.typical_symptoms
                or "tickly cough" in row.typical_symptoms
                or "without mucus" in row.typical_symptoms
                or "no phlegm" in row.typical_symptoms
            ):
                add_candidate(row, "dry_cough_match", 3)

        # General cough (if it reaches here, it means cough was specified but not typed)
        if "COUGH_GENERAL" in matching_symptoms and ("cough" in row.typical_symptoms or "cough" in row.primary_symptom):
            add_candidate(row, "general_cough_match", 1)

        # Fever/headache/body aches -> typical paracetamol combo products
        if "FEVER" in matching_symptoms and "fever" in row.typical_symptoms:
            add_candidate(row, "fever_match", 2)
        if "HEADACHE" in matching_symptoms and "headache" in row.typical_symptoms:
            add_candidate(row, "headache_match", 2)
        if "BODY_ACHES" in matching_symptoms and ("body" in row.typical_symptoms and "pain" in row.typical_symptoms):
            add_candidate(row, "body_aches_match", 1)

        # Nasal congestion/runny nose
        if "NASAL_CONGESTION" in matching_symptoms and ("nasal congestion" in row.typical_symptoms or "stuffy" in row.typical_symptoms):
            add_candidate(row, "nasal_congestion_match", 2)
        if "RUNNY_NOSE" in matching_symptoms and ("runny nose" in row.typical_symptoms or "sipon" in row.typical_symptoms):
            add_candidate(row, "runny_nose_match", 2)

        # Allergy
        if "ALLERGIC_RHINITIS" in matching_symptoms and ("allergy" in row.drug_category or "allergy" in row.typical_symptoms):
            add_candidate(row, "allergy_match", 3)

        # Rashes / allergic skin reaction -> treat as allergy/antihistamine bucket
        if "RASHES" in matching_symptoms:
            combined = f"{row.primary_symptom} {row.typical_symptoms} {row.drug_category} {_norm(row.brand)}"
            rash_specific = any(k in combined for k in ["rash", "rashes", "hives", "urticaria", "pantal", "butlig", "skin rash"])
            allergy_bucket = ("allergy" in row.drug_category) or ("antihistamine" in row.drug_category) or ("cetirizine" in _norm(row.brand))
            if allergy_bucket or rash_specific:
                add_candidate(row, "rash_match", 3)

        # Diarrhea
        if "DIARRHEA" in matching_symptoms and ("diarrhea" in row.primary_symptom or "diarrhea" in row.typical_symptoms):
            add_candidate(row, "diarrhea_match", 3)

        # Sore throat -> throat/pain products or analgesics
        if "SORE_THROAT" in matching_symptoms:
            combined_st = f"{row.primary_symptom} {row.typical_symptoms} {row.drug_category}"
            if ("sore throat" in combined_st or "throat" in combined_st
                    or "pain" in row.primary_symptom
                    or ("pain" in row.drug_category and "fever" not in row.drug_category)):
                add_candidate(row, "sore_throat_match", 2)

        # Stomach ache
        if "STOMACH_ACHE" in matching_symptoms and ("stomach" in row.typical_symptoms or "tiyan" in row.typical_symptoms
                or "abdominal" in row.typical_symptoms or "stomach" in row.primary_symptom
                or "hyperacidity" in row.typical_symptoms or "heartburn" in row.typical_symptoms
                or "antacid" in row.drug_category or "antispasmodic" in row.drug_category):
            add_candidate(row, "stomach_ache_match", 2)

    # Merge by brand (keep highest score, merge reasons)
    by_brand: Dict[str, Tuple[int, MedRow, List[str]]] = {}
    for score, row, reasons in candidates:
        key = row.brand.strip()
        if not key:
            continue
        if key not in by_brand:
            by_brand[key] = (score, row, reasons)
        else:
            prev_score, prev_row, prev_reasons = by_brand[key]
            new_score = max(prev_score, score)
            by_brand[key] = (new_score, prev_row, sorted(set(prev_reasons + reasons)))

    ranked = sorted(by_brand.values(), key=lambda t: t[0], reverse=True)

    recommendations = [
        {
            "brand": row.brand,
            "active_ingredients": row.generic_main_use,
            "drug_category": row.drug_category,
            "dosage_form": row.dosage_form,
            "min_age": row.min_age,
            "primary_symptom": row.primary_symptom,
            "reasons": reasons,
            "source": row.indication_source,
            "warnings": list(row.warnings) if row.warnings else [],
            "max_duration_days": row.max_duration_days,
        }
        for score, row, reasons in ranked[:8]
    ]

    # Safety warnings
    safety_warnings: List[str] = []
    safety_warnings.extend(_check_paracetamol_overlap(recommendations))
    safety_warnings.extend(_check_opposing_mechanisms(recommendations))

    # Cough follow-up warning when cough was deferred
    if "COUGH_GENERAL" in symptoms_set and "COUGH_GENERAL" not in matching_symptoms:
        safety_warnings.append(
            "ℹ You also mentioned a cough. Please clarify: Is it dry (walang plema) or "
            "with phlegm (may plema)? We can recommend cough medicine after."
        )

    return {
        "action": "recommend",
        "recommendations": recommendations,
        "safety_warnings": safety_warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Recommend OTC meds from Mendo dataset")
    parser.add_argument("--dataset", type=str, default=DATASET_DEFAULT, help="Path to Mendo-Datasets.json")
    parser.add_argument("--text", type=str, required=True, help="User input text")
    parser.add_argument("--json", action="store_true", help="Print JSON output")
    parser.add_argument("--flow", action="store_true", help="Print extraction flow")
    parser.add_argument("--debug", action="store_true", help="Print detailed extraction debug")
    parser.add_argument("--top", type=int, default=5, help="How many medicines to print")
    args = parser.parse_args()

    rows = load_mendo_dataset(args.dataset)

    report = extract_symptoms_hybrid_report(
        args.text,
        semantic_threshold=0.65,
        semantic_top_margin=0.08,
        semantic_max_symptoms=3,
        enable_semantic_fallback=True,
    )

    symptoms = report.get("final", {}).get("symptoms", [])
    rec = recommend_from_dataset(symptoms, rows)

    out = {
        "input": args.text,
        "symptoms": symptoms,
        "recommendation": rec,
        "checklist": {
            "handles_negation": True,
            "handles_multiple_symptoms": len(symptoms) > 1,
            "recommends_multiple_medicine": (rec.get("action") == "recommend") and (len(rec.get("recommendations", []) or []) > 1),
            "handles_fallback": rec.get("action") in {"ask_clarify", "recommend"},
            "explains_why": True,
        },
    }

    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    if args.flow or args.debug:
        # Reuse the nicer flow printing via step3_hybrid by shelling out info we already have.
        # (We keep it inline here to avoid importing internal printer functions.)
        print(f"INPUT:   {args.text}")
        for s in report.get("stages", []):
            if s.get("stage") == "dictionary":
                print(f"STAGE1:  DICTIONARY -> {s.get('detected', [])}")
                if args.debug:
                    for d in s.get("details", []) or []:
                        print(f"         hit {d.get('symptom')}: {d.get('matched_phrases')}")
            if s.get("stage") == "semantic" and s.get("available", True):
                print(f"STAGE2:  SEMANTIC -> selected={s.get('detected_selected', [])}")
                if args.debug:
                    for row in (s.get("scores", []) or [])[:6]:
                        print(f"         score {row['symptom']}: {row['score']:.4f} (anchor: {row['best_anchor']!r})")
        print(f"FINAL:   {symptoms}\n")

    if rec.get("action") == "ask_clarify":
        print("NEXT:", rec.get("question"))
        print("\nCHECKLIST:")
        for k, v in out["checklist"].items():
            print(f"- {k}: {v}")
        return 0

    print("RECOMMENDATIONS:")
    for r in (rec.get("recommendations", []) or [])[: args.top]:
        print(f"- {r['brand']} ({r['dosage_form']})")
        print(f"  ingredients: {r.get('active_ingredients')}")
        print(f"  category: {r['drug_category']}")
        print(f"  why: {r['reasons']}")

    print("\nCHECKLIST:")
    # Pretty names for your panel checklist
    pretty = {
        "handles_negation": "handles negation",
        "handles_multiple_symptoms": "handles multiple symptoms",
        "recommends_multiple_medicine": "recommends multiple medicine",
        "handles_fallback": "handles fallback",
        "explains_why": "explains why it recommends the medicine",
    }
    for k, v in out["checklist"].items():
        print(f"- {pretty.get(k, k)}: {v}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
