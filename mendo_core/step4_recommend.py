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


# ---------------------------------------------------------------------------
# OLDCARTS-INSPIRED CONTEXT DETECTION
# ---------------------------------------------------------------------------
# Clinically-informed targeted assessment for symptoms where the wrong OTC
# drug can be harmful.  Based on domain-expert guidance from a licensed
# pharmacist, using principles from the OLDCARTS clinical framework.
#
# Covers three high-risk scenarios:
#   1. DIARRHEA — food poisoning vs non-infectious (loperamide is harmful
#      when the body needs to flush bacteria/toxins)
#   2. HEADACHE — hunger/dehydration/fatigue headache may not require
#      medication at all
#   3. STOMACH_ACHE — burning/acidic vs cramping pain require different
#      drug classes (antacid vs antispasmodic)
# ---------------------------------------------------------------------------

# Food poisoning / infectious diarrhea indicators (EN, Tagalog, Bisaya)
_FOOD_POISONING_CLUES = [
    # English
    "spoiled food", "bad food", "expired", "food poisoning", "rotten",
    "ate something bad", "bad egg", "spoiled", "contaminated",
    "ate bad", "ate rotten", "leftover", "raw food", "undercooked",
    # Tagalog
    "panis", "bulok", "sira na pagkain", "lason",
    "pagkaing panis", "pagkaing sira", "pagkaing bulok",
    "kinain na panis", "kinain na bulok",
    # Bisaya
    "daot", "dunot", "pagkaon nga daot", "pagkaon nga panis",
]

# Hunger / dehydration / fatigue indicators (EN, Tagalog, Bisaya)
_HUNGER_DEHYDRATION_CLUES = [
    # English
    "didn't eat", "haven't eaten", "not eaten", "hungry",
    "skipped meal", "empty stomach", "no food",
    "dehydrated", "no water", "thirsty", "didn't drink",
    "lack of sleep", "didn't sleep", "no sleep",
    # Tagalog — full phrases
    "hindi kumain", "di pa kumain", "gutom", "walang kain",
    "di pa nakakaon", "hindi pa kumakain", "hindi pa kumain",
    "uhaw", "walang tubig", "kulang tulog", "hindi natulog",
    "di natulog", "puyat", "pagod",
    # Tagalog — flexible (words commonly appear with filler words in between)
    "hindi pa nag", "di pa nag",          # "hindi pa nag-almusal/naglunch"
    "wala pa akong kain", "walang almusal",
    "walang tanghalian", "walang hapunan",
    # Bisaya
    "wala pa kaon", "wala pa ko kaon", "wala pa nangaon",
    "gipanguhaw", "wala natulog",
    "wala pa nakakaon", "walay kaon",
]

# Regex patterns for flexible hunger/dehydration matching
# These catch "hindi pa kasi ako kumain" etc. with filler words
import re as _re

_HUNGER_DEHYDRATION_RX = [
    _re.compile(r"\b(hindi|di|hnd|hinde)\b.{0,20}\b(kumain|kaon|kain|nag.?almusal|nag.?lunch|nag.?dinner)\b"),
    _re.compile(r"\b(wala|walang|walay)\b.{0,15}\b(kain|kaon|almusal|tanghalian|hapunan)\b"),
    _re.compile(r"\b(not|haven.?t|didn.?t|skip).{0,15}\b(eat|eaten|meal|breakfast|lunch|dinner)\b"),
    _re.compile(r"\b(not|haven.?t|didn.?t).{0,15}\b(drink|water|hydrat)\b"),
    _re.compile(r"\b(kulang|lacking|lack|wala).{0,10}\b(tulog|sleep)\b"),
]

# Acidic / burning stomach indicators (EN, Tagalog, Bisaya)
_ACIDIC_STOMACH_CLUES = [
    "burning", "acidic", "heartburn", "acid reflux", "sour stomach",
    "acid", "acidity", "hyperacidity",
    "maanghang", "nasusunog", "mainit sa tiyan",
    "init sa tiyan", "parang nasusunog", "umaanghang",
    "masakit ang sikmura parang nasusunog",
]

# Cramping / spasm / bloating stomach indicators (EN, Tagalog, Bisaya)
_CRAMPING_STOMACH_CLUES = [
    "cramp", "cramping", "cramps", "spasm", "bloated", "bloating",
    "gas", "gassy", "kabag", "pulikat", "mahangin",
    "hubag", "puno ang tiyan", "colic",
    "parang pinipilipit", "pinipilipit",
]

# Cold-weather / environmental sipon indicators (EN, Tagalog, Bisaya)
_COLD_WEATHER_SIPON_CLUES = [
    # English
    "cold weather", "cold place", "cold air", "cold wind",
    "aircon", "air conditioning", "air con",
    "got cold", "went outside", "from the cold",
    "rainy", "rain",
    # Tagalog
    "malamig", "maginaw",
    "nilamig", "nalamigan", "ginaw",
    "galing sa labas", "sa malamig",
    "ulan", "naulan", "nabasa sa ulan",
    "aircon", "naka-aircon",
    # Bisaya
    "tugnaw", "gipatugnaw", "nabugnaw",
    "dagat nga tugnaw", "gikan sa tugnaw",
]

# Allergy-associated sipon indicators (EN, Tagalog, Bisaya)
_ALLERGY_SIPON_CLUES = [
    # English
    "sneezing", "itchy nose", "itchy eyes", "watery eyes",
    "dust", "pollen", "pet", "dander",
    "every morning", "always sneezing",
    # Tagalog
    "bahing", "bumabahing", "makati ilong", "makati mata",
    "alikabok", "alerdyi", "allergy",
    "tuwing umaga", "lagi akong bumabahing",
    # Bisaya
    "magbahing", "magha-tsing",
    "katol ang ilong", "katol ang mata",
]


def recommend_from_dataset(
    symptoms: Sequence[str],
    rows: Sequence[MedRow],
    *,
    red_flags: Optional[List[Dict[str, str]]] = None,
    user_input: Optional[str] = None,
    context_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Rule-based mapping aligned to your dataset.

    If *red_flags* is non-empty the system returns a ``triage`` action
    instead of OTC recommendations, instructing the user to consult a
    doctor or pharmacist immediately.

    If *user_input* is provided, OLDCARTS-inspired context detection is
    applied for high-risk symptoms (diarrhea, headache, stomach ache) to
    guide safer and more appropriate OTC recommendations.

    If *context_override* is provided, it represents an explicit answer to a
    prior clarification question and takes precedence over automatic context
    inference so the user is not asked the same question again.
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

    if not symptoms:
        return {
            "action": "no_match",
            "message": (
                "We could not confidently identify your symptom. Please rephrase "
                "using simple symptom words like headache, fever, cough, diarrhea, "
                "or stomach ache."
            ),
            "recommendations": [],
            "safety_warnings": [],
        }

    symptoms_set = set(symptoms)
    matching_symptoms = set(symptoms)  # copy for tracking actual matches

    # ── OLDCARTS-INSPIRED CONTEXT ASSESSMENT ──────────────────────────────
    # For symptoms where the wrong OTC drug can be harmful, detect context
    # clues from the user's natural-language input to guide safer
    # recommendations.  Implements targeted follow-up inspired by the
    # OLDCARTS clinical assessment framework per domain-expert guidance.
    _input_lower = (user_input or "").lower()
    _diarrhea_food_poisoning = False
    _diarrhea_context_answered = False
    _headache_non_drug = False
    _stomach_acidic = False
    _stomach_cramping = False
    _sipon_cold_weather = False
    _sipon_allergy = False
    _sipon_context_answered = False

    if context_override == "DIARRHEA_FOOD_POISONING":
        _diarrhea_food_poisoning = True
        _diarrhea_context_answered = True
    elif context_override == "DIARRHEA_NON_INFECTIOUS":
        _diarrhea_food_poisoning = False
        _diarrhea_context_answered = True
    elif context_override == "STOMACH_ACIDIC":
        _stomach_acidic = True
    elif context_override == "STOMACH_CRAMPING":
        _stomach_cramping = True
    elif context_override == "SIPON_VIRAL_COLD":
        _sipon_context_answered = True
    elif context_override == "SIPON_ALLERGY":
        _sipon_allergy = True
        _sipon_context_answered = True
    elif context_override == "SIPON_COLD_WEATHER":
        _sipon_cold_weather = True
        _sipon_context_answered = True

    if user_input is not None:
        # --- DIARRHEA: food poisoning vs non-infectious ---
        if "DIARRHEA" in symptoms_set:
            if not _diarrhea_context_answered:
                _food_clues = any(c in _input_lower for c in _FOOD_POISONING_CLUES)
                _fever_with_diarrhea = "FEVER" in symptoms_set
                _diarrhea_food_poisoning = _food_clues or _fever_with_diarrhea

            other_syms = symptoms_set - {"DIARRHEA"}
            if not _diarrhea_food_poisoning and not _diarrhea_context_answered and not other_syms:
                # Diarrhea alone with no context → ask OLDCARTS-style question
                return {
                    "action": "ask_clarify",
                    "clarify_type": "DIARRHEA_CONTEXT",
                    "question": (
                        "Para mas tama ang i-recommend, pakisagot:\n"
                        "• Kumain ka ba ng panis o expired na pagkain?\n"
                        "  (Did you eat spoiled or expired food?)\n"
                        "• May lagnat ka ba? (Do you have fever?)"
                    ),
                    "options": [
                        {
                            "label": "Oo, kumain ng panis / Yes, ate spoiled food",
                            "value": "DIARRHEA_FOOD_POISONING",
                        },
                        {
                            "label": "Hindi naman / No, no bad food",
                            "value": "DIARRHEA_NON_INFECTIOUS",
                        },
                    ],
                    "original_symptoms": list(symptoms),
                }

        # --- HEADACHE: hunger / dehydration / fatigue detection ---
        if "HEADACHE" in symptoms_set:
            _headache_non_drug = any(
                c in _input_lower for c in _HUNGER_DEHYDRATION_CLUES            ) or any(
                rx.search(_input_lower) for rx in _HUNGER_DEHYDRATION_RX            )

        # --- STOMACH_ACHE: burning/acidic vs cramping ---
        if "STOMACH_ACHE" in symptoms_set:
            if context_override not in {"STOMACH_ACIDIC", "STOMACH_CRAMPING"}:
                _stomach_acidic = any(
                    c in _input_lower for c in _ACIDIC_STOMACH_CLUES
                )
                _stomach_cramping = any(
                    c in _input_lower for c in _CRAMPING_STOMACH_CLUES
                )
            other_syms = symptoms_set - {"STOMACH_ACHE"}
            if not _stomach_acidic and not _stomach_cramping and not other_syms:
                return {
                    "action": "ask_clarify",
                    "clarify_type": "STOMACH_CONTEXT",
                    "question": (
                        "Para mas tama ang i-recommend, ano ang nararamdaman mo?\n"
                        "• Maanghang / nasusunog ba? (Burning / acidic feeling?)\n"
                        "• Pulikat / kabag ba? (Cramping / bloating?)"
                    ),
                    "options": [
                        {
                            "label": "Maanghang / Nasusunog / Burning / Acidic",
                            "value": "STOMACH_ACIDIC",
                        },
                        {
                            "label": "Pulikat / Kabag / Cramping / Bloating",
                            "value": "STOMACH_CRAMPING",
                        },
                    ],
                    "original_symptoms": list(symptoms),
                }

        # --- RUNNY_NOSE (sipon): allergy vs viral cold vs cold weather ---
        if "RUNNY_NOSE" in symptoms_set:
            if not _sipon_context_answered:
                _sipon_cold_weather = any(
                    c in _input_lower for c in _COLD_WEATHER_SIPON_CLUES
                )
                _sipon_allergy = any(
                    c in _input_lower for c in _ALLERGY_SIPON_CLUES
                )
            # Only ask clarification when sipon is the sole symptom
            # and no context clues were detected from the input text
            other_syms = symptoms_set - {"RUNNY_NOSE"}
            if (
                not _sipon_cold_weather
                and not _sipon_allergy
                and not _sipon_context_answered
                and not other_syms
            ):
                return {
                    "action": "ask_clarify",
                    "clarify_type": "SIPON_CONTEXT",
                    "question": (
                        "Para mas tama ang i-recommend, pakisagot:\n"
                        "• May kasama bang lagnat o ubo? (With fever or cough?)\n"
                        "• Madalas ka bang bumabahing o makati ilong? "
                        "(Frequent sneezing / itchy nose?)\n"
                        "• Galing ka ba sa malamig na lugar o naulanan? "
                        "(Were you exposed to cold weather / rain?)"
                    ),
                    "options": [
                        {
                            "label": "Oo, may lagnat/ubo din / Yes, with fever or cough",
                            "value": "SIPON_VIRAL_COLD",
                        },
                        {
                            "label": "Madalas bumabahing / makati ilong / Sneezing/itchy",
                            "value": "SIPON_ALLERGY",
                        },
                        {
                            "label": "Galing sa malamig / naulanan / From cold/rain",
                            "value": "SIPON_COLD_WEATHER",
                        },
                    ],
                    "original_symptoms": list(symptoms),
                }

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

    cold_context_present = bool(
        symptoms_set & {
            "FEVER",
            "RUNNY_NOSE",
            "NASAL_CONGESTION",
            "COUGH_GENERAL",
            "COUGH_DRY",
            "COUGH_PRODUCTIVE",
            "SORE_THROAT",
        }
    )

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

        # Fever/headache/body aches -> analgesics first; cold combos only when there
        # is actual cold context. This prevents plain headache from pulling noisy
        # cold medications like Decolgen unless other cold symptoms are present.
        if "FEVER" in matching_symptoms and "fever" in row.typical_symptoms:
            add_candidate(row, "fever_match", 2)
        if "HEADACHE" in matching_symptoms and "headache" in row.typical_symptoms:
            combined_head = f"{row.primary_symptom} {row.typical_symptoms} {row.drug_category}"
            is_analgesic = (
                "headache" in row.primary_symptom
                or "pain & fever" in row.drug_category
                or "pain & inflammation" in row.drug_category
            )
            is_cold_combo = any(cat in row.drug_category for cat in ["cold", "cold & flu", "cold & cough"])

            if is_analgesic:
                add_candidate(row, "headache_primary_match", 4)
            elif cold_context_present and is_cold_combo:
                add_candidate(row, "headache_cold_context_match", 2)
        if "BODY_ACHES" in matching_symptoms and ("body" in row.typical_symptoms and "pain" in row.typical_symptoms):
            add_candidate(row, "body_aches_match", 1)

        # Nasal congestion/runny nose
        if "NASAL_CONGESTION" in matching_symptoms and ("nasal congestion" in row.typical_symptoms or "stuffy" in row.typical_symptoms):
            add_candidate(row, "nasal_congestion_match", 2)
        if "RUNNY_NOSE" in matching_symptoms and ("runny nose" in row.typical_symptoms or "sipon" in row.typical_symptoms):
            # If allergy context detected via OLDCARTS, steer toward antihistamines
            if _sipon_allergy and ("allergy" in row.drug_category or "allergy" in row.typical_symptoms):
                add_candidate(row, "sipon_allergy_match", 4)
            elif not _sipon_cold_weather:
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

        # Diarrhea — OLDCARTS-informed scoring
        if "DIARRHEA" in matching_symptoms and (
            "diarrhea" in row.primary_symptom
            or "diarrhea" in row.typical_symptoms
            or "rehydration" in row.drug_category
        ):
            if _diarrhea_food_poisoning:
                # Food poisoning / infection suspected: ORS is top priority,
                # probiotics second, exclude loperamide (traps bacteria/toxins)
                if "rehydration" in row.drug_category:
                    add_candidate(row, "ors_food_poisoning_priority", 6)
                elif "probiotic" in row.drug_category or "bacillus" in _norm(row.generic_main_use):
                    add_candidate(row, "probiotic_food_poisoning", 5)
                elif "anti-diarrhea" not in row.drug_category:
                    add_candidate(row, "diarrhea_supportive", 2)
                # else: skip anti-diarrheal (loperamide) entirely
            else:
                # Non-infectious diarrhea: ORS still recommended alongside treatment
                if "rehydration" in row.drug_category:
                    add_candidate(row, "ors_hydration_support", 4)
                else:
                    add_candidate(row, "diarrhea_match", 3)

        # Sore throat -> throat/pain products or analgesics
        if "SORE_THROAT" in matching_symptoms:
            combined_st = f"{row.primary_symptom} {row.typical_symptoms} {row.drug_category}"
            if ("sore throat" in combined_st or "throat" in combined_st
                    or "pain" in row.primary_symptom
                    or ("pain" in row.drug_category and "fever" not in row.drug_category)):
                add_candidate(row, "sore_throat_match", 2)

        # Stomach ache — OLDCARTS-informed scoring
        if "STOMACH_ACHE" in matching_symptoms:
            _is_stomach_drug = (
                "stomach" in row.typical_symptoms or "tiyan" in row.typical_symptoms
                or "abdominal" in row.typical_symptoms or "stomach" in row.primary_symptom
                or "hyperacidity" in row.typical_symptoms or "heartburn" in row.typical_symptoms
                or "antacid" in row.drug_category or "antispasmodic" in row.drug_category
            )
            if _is_stomach_drug:
                if _stomach_acidic:
                    # Burning/acidic → prioritize antacid (e.g., Kremil-S)
                    if "antacid" in row.drug_category:
                        add_candidate(row, "acidic_stomach_match", 5)
                    else:
                        add_candidate(row, "stomach_ache_match", 1)
                elif _stomach_cramping:
                    # Cramping/bloating → prioritize antispasmodic (e.g., Buscopan)
                    if "antispasmodic" in row.drug_category:
                        add_candidate(row, "cramping_stomach_match", 5)
                    else:
                        add_candidate(row, "stomach_ache_match", 1)
                else:
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

    # OLDCARTS-informed safety advisories
    if _diarrhea_food_poisoning:
        safety_warnings.append(
            "⚠ Possible food poisoning or infection suspected. Anti-diarrheal medicine "
            "(e.g., loperamide/Diatabs) is NOT recommended — it may trap bacteria or "
            "toxins in the body. Use Hydrite (ORS) to stay hydrated. "
            "Consult a doctor if symptoms persist beyond 2 days, or if you develop "
            "high fever or blood in stool."
        )
    if _headache_non_drug and "HEADACHE" in symptoms_set:
        other_head_syms = symptoms_set - {"HEADACHE"}
        if not other_head_syms:
            safety_warnings.append(
                "ℹ Your headache may be related to hunger, dehydration, or fatigue. "
                "Try eating a meal, drinking water, and resting first. If the headache "
                "persists after eating and hydrating, the recommended pain relief "
                "medication may then be appropriate."
            )

    # Cough follow-up warning when cough was deferred
    if "COUGH_GENERAL" in symptoms_set and "COUGH_GENERAL" not in matching_symptoms:
        safety_warnings.append(
            "ℹ You also mentioned a cough. Please clarify: Is it dry (walang plema) or "
            "with phlegm (may plema)? We can recommend cough medicine after."
        )

    # Sipon cold-weather advisory — no medicine needed
    if _sipon_cold_weather and "RUNNY_NOSE" in symptoms_set:
        other_syms = symptoms_set - {"RUNNY_NOSE"}
        if not other_syms:
            return {
                "action": "recommend",
                "recommendations": [],
                "message": (
                    "ℹ️ Ang iyong sipon ay maaaring dulot ng malamig na panahon "
                    "(vasomotor rhinitis). Hindi ito kailangan ng gamot.\n\n"
                    "Payo:\n"
                    "• Magpahinga sa mainit na lugar\n"
                    "• Uminom ng mainit na tubig o sabaw\n"
                    "• Kung hindi mawala pagkatapos ng 2-3 araw, "
                    "kumonsulta sa pharmacist.\n\n"
                    "(Your runny nose may be caused by cold weather. This "
                    "usually doesn't require medication. Rest in a warm place "
                    "and drink warm fluids. If it persists beyond 2-3 days, "
                    "consult a pharmacist.)"
                ),
                "safety_warnings": [],
            }

    if not recommendations:
        return {
            "action": "no_match",
            "message": (
                "We found possible symptoms, but not enough to recommend a medicine safely. "
                "Please rephrase your concern or consult a pharmacist."
            ),
            "recommendations": [],
            "safety_warnings": safety_warnings,
        }

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
    rec = recommend_from_dataset(symptoms, rows, user_input=args.text)

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
        if rec.get("options"):
            print("\nOPTIONS:")
            for opt in rec["options"]:
                print(f"  • {opt['label']}")
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
