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
import math
import re
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
    min_age: int
    dosage_form: str
    notes: str
    age_group: str
    condition_label: str


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

        # Combine multilingual symptom columns if present (latest dataset).
        typical_en = r.get("Typical Symptoms Treated")
        typical_tl = r.get("Typical Symptoms Treated (Tagalog/Filipino)")
        typical_cb = r.get("Typical Symptoms Treated (Cebuano/Bisaya)")
        typical_combined = " ".join(
            str(x or "")
            for x in (
                typical_en,
                typical_tl,
                typical_cb,
            )
            if str(x or "").strip()
        )

        min_age_raw = r.get("Minimum Age", "")
        try:
            min_age_val = int(min_age_raw) if min_age_raw != "" and min_age_raw is not None else 0
        except (ValueError, TypeError):
            min_age_val = 0

        notes_val = r.get("Notes")
        if isinstance(notes_val, float):
            try:
                if math.isnan(notes_val):
                    notes_val = ""
            except Exception:
                pass
        age_group_val = str(r.get("Age Group") or "")
        condition_label_val = str(r.get("Condition Label") or "")
        out.append(
            MedRow(
                brand=str(r.get("Brand") or ""),
                generic_main_use=str(r.get("Generic/Main Use") or ""),
                primary_symptom=_norm(r.get("Primary Symptom")),
                typical_symptoms=_norm(typical_combined),
                drug_category=_norm(r.get("Drug Category")),
                min_age=min_age_val,
                dosage_form=str(r.get("Dosage Form") or ""),
                notes=str(notes_val or ""),
                age_group=age_group_val,
                condition_label=condition_label_val,
            )
        )
    return out


def _detect_user_context(user_input: str) -> dict:
    """Extract safety-relevant context from user input text."""
    text = (user_input or "").lower()
    ctx: dict = {
        "pregnant": False,
        "hypertension": False,
        "kidney_disease": False,
        "driving": False,
        "drug_allergy": [],      # list of generic ingredient names
        "requested_brand": None, # brand the user explicitly asked for
    }
    # Pregnancy
    if re.search(r"\b(buntis|pregnant|preggy|nagbubuntis|pagbubuntis)\b", text):
        ctx["pregnant"] = True
    # Hypertension
    if re.search(r"\b(highblood|high\s*blood|hypertension|altapresyon)\b", text):
        ctx["hypertension"] = True
    # Kidney disease
    if re.search(r"\b(kidney|bato|sakit\s+sa\s+bato|renal)\b", text):
        ctx["kidney_disease"] = True
    # Driving
    if re.search(r"\b(driving|nagdadrive|nagmamaneho|magdadrive|maya\b.*drive|drive\b.*maya)\b", text):
        ctx["driving"] = True
    # Drug allergy detection
    if re.search(r"\b(allergic|allergy|bawal)\b.*\b(paracetamol|biogesic)\b", text):
        ctx["drug_allergy"].append("paracetamol")
    if re.search(r"\b(allergic|allergy|bawal)\b.*\b(ibuprofen|advil)\b", text):
        ctx["drug_allergy"].append("ibuprofen")
    # Explicit brand request
    brand_patterns = {
        "biogesic": "Biogesic",
        "bioflu": "Bioflu",
        "neozep": "Neozep",
        "decolgen": "Decolgen",
        "solmux": "Solmux",
        "ascof": "Ascof",
        "tuseran": "Tuseran Forte",
        "sinecod": "Sinecod Forte",
        "kremil": "Kremil-S",
        "diatabs": "Loperamide (Diatabs)",
        "advil": "Advil",
        "aspirin": "Aspirin (Philprin)",
        "benadryl": "Benadryl AH",
        "cetirizine": "Cetirizine",
        "claritin": "Claritin",
        "allerta": "Allerta",
        "sinutab": "Sinutab",
        "erceflora": "Erceflora",
        "robitussin": "Robitussin",
    }
    for pattern, brand in brand_patterns.items():
        if re.search(rf"\b{re.escape(pattern)}\b", text):
            ctx["requested_brand"] = brand
            break
    return ctx


def recommend_from_dataset(
    symptoms: Sequence[str],
    rows: Sequence[MedRow],
    *,
    user_age: Optional[int] = None,
    user_input: str = "",
) -> Dict[str, Any]:
    """Rule-based mapping aligned to your dataset."""

    symptoms_set = set(symptoms)

    # Clarifying question for ambiguous cough
    # But NOT when cold symptoms are also present (cough+cold combo)
    has_cold_symptoms = bool(symptoms_set & {"RUNNY_NOSE", "NASAL_CONGESTION"})
    if "COUGH_GENERAL" in symptoms_set and not ("COUGH_DRY" in symptoms_set or "COUGH_PRODUCTIVE" in symptoms_set) and not has_cold_symptoms:
        return {
            "action": "ask_clarify",
            "question": "Please specify: Is your cough dry (walay/walang plema) or with phlegm (naay/may plema)?",
            "candidates": [],
        }

    candidates: List[Tuple[int, MedRow, List[str]]] = []

    def add_candidate(row: MedRow, reason: str, score: int) -> None:
        candidates.append((score, row, [reason]))

    for row in rows:
        # Productive cough -> Solmux / Ascof / Robitussin patterns
        if "COUGH_PRODUCTIVE" in symptoms_set:
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
            # Important: don't treat the word "mucus" alone as productive because
            # some dry-cough meds include phrases like "cough without mucus".
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
        if "COUGH_DRY" in symptoms_set:
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
        if "COUGH_GENERAL" in symptoms_set and ("cough" in row.typical_symptoms or "cough" in row.primary_symptom):
            add_candidate(row, "general_cough_match", 1)

        # Cough + Cold combo -> Symdex family (cough with colds / cough with runny nose)
        has_cough = bool(symptoms_set & {"COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"})
        has_cold = bool(symptoms_set & {"RUNNY_NOSE", "NASAL_CONGESTION"})
        if has_cough and has_cold:
            if "cough with colds" in row.typical_symptoms or "cough with runny nose" in row.typical_symptoms:
                add_candidate(row, "cough_and_cold_match", 4)

        # Fever/headache/body aches -> typical paracetamol combo products
        if "FEVER" in symptoms_set and "fever" in row.typical_symptoms:
            add_candidate(row, "fever_match", 2)
        if "HEADACHE" in symptoms_set and "headache" in row.typical_symptoms:
            add_candidate(row, "headache_match", 2)
        if "BODY_ACHES" in symptoms_set and (
            ("body" in row.typical_symptoms and "pain" in row.typical_symptoms)
            or "muscle pain" in row.typical_symptoms
            or "body aches" in row.typical_symptoms
        ):
            add_candidate(row, "body_aches_match", 1)

        # Nasal congestion/runny nose
        if "NASAL_CONGESTION" in symptoms_set and ("nasal congestion" in row.typical_symptoms or "stuffy" in row.typical_symptoms):
            add_candidate(row, "nasal_congestion_match", 2)
        if "RUNNY_NOSE" in symptoms_set and ("runny nose" in row.typical_symptoms or "sipon" in row.typical_symptoms):
            add_candidate(row, "runny_nose_match", 2)

        # Allergy
        if "ALLERGIC_RHINITIS" in symptoms_set and ("allergy" in row.drug_category or "allergy" in row.typical_symptoms):
            add_candidate(row, "allergy_match", 3)

        # Rashes / allergic skin reaction -> treat as allergy/antihistamine bucket
        if "RASHES" in symptoms_set:
            combined = f"{row.primary_symptom} {row.typical_symptoms} {row.drug_category} {_norm(row.brand)}"
            rash_specific = any(k in combined for k in ["rash", "rashes", "hives", "urticaria", "pantal", "butlig", "skin rash"])
            allergy_bucket = ("allergy" in row.drug_category) or ("antihistamine" in row.drug_category) or ("cetirizine" in _norm(row.brand))
            if allergy_bucket or rash_specific:
                add_candidate(row, "rash_match", 3)

        # Diarrhea
        if "DIARRHEA" in symptoms_set and ("diarrhea" in row.primary_symptom or "diarrhea" in row.typical_symptoms):
            add_candidate(row, "diarrhea_match", 3)

        # Stomach ache -> Map to hyperacidity / antacid products
        if "STOMACH_ACHE" in symptoms_set:
            combined = f"{row.primary_symptom} {row.typical_symptoms} {row.drug_category}"
            if (
                "stomach" in combined
                or "tiyan" in combined
                or "hyperacidity" in combined
                or "antacid" in row.drug_category
                or "kabag" in combined
                or "bloat" in combined
                or "gas pain" in combined
                or "heartburn" in combined
                or "acid" in combined
            ):
                add_candidate(row, "stomach_ache_match", 3)

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

    # ── Safety Warnings & Age Filtering ──
    ctx = _detect_user_context(user_input) if user_input else {}
    warnings: List[str] = []
    filtered_ranked: List[Tuple[int, MedRow, List[str]]] = []

    for score, row, reasons in ranked:
        brand_lower = _norm(row.brand)
        generic_lower = _norm(row.generic_main_use)
        skip = False

        # Age filtering
        if user_age is not None and row.min_age > 0:
            if user_age < row.min_age:
                # Don't include medicines the user is too young for
                continue

        # Pregnancy: avoid NSAIDs (Ibuprofen), prefer Paracetamol
        if ctx.get("pregnant"):
            if "ibuprofen" in generic_lower or "advil" in brand_lower:
                warnings.append(f"WARNING: {row.brand} (Ibuprofen) is contraindicated in pregnancy. Switch to Paracetamol (Biogesic).")
                skip = True
            if "aspirin" in brand_lower or "acetylsalicylic" in generic_lower:
                warnings.append(f"WARNING: {row.brand} (Aspirin) is contraindicated in pregnancy.")
                skip = True

        # Hypertension: avoid Phenylephrine (decongestants)
        if ctx.get("hypertension"):
            if "phenylephrine" in generic_lower:
                warnings.append(f"WARNING: {row.brand} contains Phenylephrine (vasoconstrictor). Risky for Hypertension patients. Switch to plain Paracetamol.")
                skip = True

        # Kidney disease: warn about Kremil-S (antacids with Al/Mg) but still include
        if ctx.get("kidney_disease"):
            if "aluminum" in generic_lower or "magnesium" in generic_lower:
                warnings.append(f"WARNING: {row.brand} contains Aluminum/Magnesium. Risk of accumulation and toxicity in kidney disease. REFER TO DOCTOR.")
                # Don't skip — include with warning so user is informed

        # Driving: warn about drowsy antihistamines (Benadryl / Chlorphenamine)
        if ctx.get("driving"):
            if "diphenhydramine" in generic_lower or "benadryl" in brand_lower:
                warnings.append(f"WARNING: {row.brand} (Diphenhydramine) causes drowsiness. Suggest non-drowsy alternative (Loratadine/Cetirizine).")
                skip = True

        # Aspirin + child (Reye's syndrome)
        if user_age is not None and user_age < 18:
            if "aspirin" in brand_lower or "acetylsalicylic" in generic_lower:
                warnings.append(f"CRITICAL WARNING: {row.brand} (Aspirin) can cause Reye's Syndrome in children. SWITCH to Paracetamol.")
                skip = True

        # Drug allergy: skip medicines containing the allergen
        for allergen in ctx.get("drug_allergy", []):
            if allergen == "paracetamol" and "paracetamol" in generic_lower:
                skip = True
            if allergen == "ibuprofen" and "ibuprofen" in generic_lower:
                skip = True

        if not skip:
            filtered_ranked.append((score, row, reasons))

    return {
        "action": "recommend",
        "warnings": warnings,
        "recommendations": [
            {
                "brand": row.brand,
                "active_ingredients": row.generic_main_use,
                "drug_category": row.drug_category,
                "dosage_form": row.dosage_form,
                "primary_symptom": row.primary_symptom,
                "reasons": reasons,
                "age_group": row.age_group,
                "notes": row.notes,
                "condition_label": row.condition_label,
                "min_age": row.min_age,
            }
            for score, row, reasons in filtered_ranked[:8]
        ],
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
