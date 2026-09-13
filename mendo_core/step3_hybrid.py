"""step3_hybrid.py

HYBRID NLP PIPELINE (Defense-friendly)

Idea:
- Step 1 (dictionary) for speed + predictable behavior on common phrases.
- Step 2 (embeddings) as a fallback when exact match fails (slang/paraphrase).

This gives you a strong panel line:
"We cascade from deterministic keyword matching to a transformer-based embedding
model only when needed, making the system both fast and robust."

Install for Step 2 fallback:
  python -m pip install sentence-transformers
"""

from __future__ import annotations

import argparse
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .step1 import extract_symptoms as extract_symptoms_dictionary
from .step1 import extract_conditions as extract_conditions_dictionary


# ---------------------------------------------------------------------------
# STAGE 0 — TRIAGE / RED-FLAG SAFETY LAYER
# ---------------------------------------------------------------------------
# Uses proximity-based co-occurrence within token windows plus explicit
# exclusion tokens (negative constraints) to prevent over-triage.
#
# Architecture
# ─────────────────────────────────────────────────────────────────────────
# _TRIAGE_RULES    — co-occurrence rules: A-term + B-term within `window`
#                    tokens, vetoed by `exclude_terms` in `exclude_window`
# _detect_*        — special-case handlers for patterns that need 3-part
#                    matching (dehydration, hyperthermia, pregnancy)
# Direct-keyword   — single-word emergencies that fire unconditionally
# ---------------------------------------------------------------------------

RED_FLAG_MESSAGES: Dict[str, str] = {
    # GI bleeding
    "blood_in_stool":            "Possible GI hemorrhage — blood detected in stool",
    "blood_vomit":               "Possible upper GI bleed — blood detected in vomit",
    # Cardiac
    "chest_pain":                "Possible cardiac emergency — chest pain or pressure",
    # Respiratory
    "difficulty_breathing":      "Respiratory emergency — difficulty or inability to breathe",
    # Dengue / viral
    "dengue_warning":            "Dengue / viral hemorrhagic fever risk — fever with rashes or dengue keyword",
    # Neurological
    "stroke_warning":            "Possible neurological event (stroke) — paralysis, numbness, or speech loss",
    # Dehydration
    "severe_dehydration":        "Severe dehydration risk — diarrhea with absent or reduced urine output",
    # Pregnancy
    "pregnancy_contraindication": "Pregnancy detected — OTC selection requires pharmacist guidance",
    # Hyperthermia
    "high_fever_prolonged":      "Dangerous hyperthermia — fever at or above 40 °C",
    # Direct emergencies
    "seizure":                   "Seizure / convulsion reported — seek emergency care immediately",
    "loss_of_consciousness":     "Loss of consciousness reported — seek emergency care immediately",
    # Anaphylaxis
    "severe_allergic_reaction":  "Severe allergic reaction / anaphylaxis signs — seek emergency care",
    # Body-part bleeding
    "head_bleeding":             "Head or facial bleeding detected — seek emergency medical care",
    "nose_bleeding":             "Nosebleed detected — if persistent or accompanied by fever, seek medical attention",
    "ear_bleeding":              "Ear bleeding detected — may indicate head trauma or ruptured eardrum",
    "hemoptysis":                "Coughing blood detected — may indicate serious lung or respiratory condition",
    "blood_in_urine":            "Blood in urine (hematuria) detected — seek medical attention",
    "hypertension_risk":         "Hypertension / high blood pressure reported — consult medical expert before OTC self-medication",
}

# ---------------------------------------------------------------------------
# Co-occurrence rules
# Each rule fires when at least one A-term AND one B-term appear within
# `window` tokens of each other, AND no `exclude_terms` appear within
# `exclude_window` tokens of that matched span.
# ---------------------------------------------------------------------------
_TRIAGE_RULES: List[Dict[str, Any]] = [
    # ── 1. Gastrointestinal Hemorrhage (lower GI) ─────────────────────────
    {
        "flag":    "blood_in_stool",
        "message": RED_FLAG_MESSAGES["blood_in_stool"],
        "a_terms": [
            # English
            "blood", "bleeding", "bleed", "bloody",
            # Tagalog / Bisaya
            "dugo", "nagdurugo", "nadugo", "madugo", "maduguon", "gadugo",
            "may dugo", "naay dugo",
        ],
        "b_terms": [
            # English
            "stool", "poop", "feces", "bowel", "defecate",
            # Tagalog
            "dumi", "tae", "bawas", "kalibang", "pagtatae",
            # Bisaya
            "hugaw", "libang",
        ],
        "window": 8,
    },
    # ── 2. Upper GI Bleed (blood in vomit) ───────────────────────────────
    {
        "flag":    "blood_vomit",
        "message": RED_FLAG_MESSAGES["blood_vomit"],
        "a_terms": [
            "blood", "bleeding", "bleed", "bloody",
            "dugo", "nagdurugo", "nadugo", "madugo", "maduguon", "gadugo",
            "may dugo", "naay dugo",
        ],
        "b_terms": [
            # English
            "vomit", "vomiting", "vomited", "threw up",
            # Tagalog
            "suka", "nagsuka", "nasuka", "nagsusuka", "nagsuka", "nagsusuka",
            "sumuka", "lusuka",
            # Bisaya
            "suka", "misuka", "nagsuka",
        ],
        "window": 7,
    },
    # ── 3. Cardiac Emergency ──────────────────────────────────────────────
    {
        "flag":    "chest_pain",
        "message": RED_FLAG_MESSAGES["chest_pain"],
        "a_terms": [
            # English pain / pressure descriptors
            "pain", "pains", "painful", "hurts", "hurt", "aching", "aches",
            "tight", "tightness", "pressure", "pressing",
            "squeezing", "squeezed", "crushing", "crush",
            "heavy", "heaviness", "burning", "radiating",
            # Tagalog
            "masakit", "sumasakit", "kirot", "mabigat",
            "presyon", "nagbibigat", "paninikip", "paninigas",
            # Bisaya
            "sakit", "gikirot", "bug at", "mabug at",
        ],
        "b_terms": [
            "chest", "dibdib", "dughan", "pecho",
            # Heart — "sumasakit ang puso ko" must triage as cardiac
            "puso", "heart",
        ],
        "window": 6,
        # Chest pain caused purely by coughing/congestion is OTC-treatable
        "exclude_terms": [
            "halak", "plema", "phlegm", "ubo", "cough", "coughing",
            "congestion", "kumakalansing", "inuubo", "gi-ubo",
        ],
        "exclude_window": 10,
    },
    # ── 4. Respiratory Emergency ──────────────────────────────────────────
    {
        "flag":    "difficulty_breathing",
        "message": RED_FLAG_MESSAGES["difficulty_breathing"],
        "a_terms": [
            # English
            "hirap", "nahihirapan", "nahirapan", "hindi", "di",
            "wala", "walang", "mahirap",
            # Tagalog
            "hirap huminga", "hirap ng paghinga",
            # Bisaya
            "lisod", "lisud", "dili", "walay", "mabudlay",
        ],
        "b_terms": [
            # English
            "breathing", "breathe", "breath",
            # Tagalog
            "hinga", "huminga", "hihinga", "paghinga",
            "makahinga", "makapaghinga", "makaginhawa",
            # Bisaya
            "ginhawa", "muginhawa", "moginhawa",
        ],
        "window": 7,
    },
    # ── 5. Suspected Dengue / Viral Hemorrhagic Fever ─────────────────────
    {
        "flag":    "dengue_warning",
        "message": RED_FLAG_MESSAGES["dengue_warning"],
        "a_terms": [
            # Fever terms (signal)
            "fever", "lagnat", "hilanat", "nilalagnat", "nalalagnat",
            "gihilanat", "init", "mainit",
        ],
        "b_terms": [
            # Rash / spots
            "rash", "rashes", "spots", "red spots", "petechiae",
            "pantal", "butlig", "mantsa", "namumula",
        ],
        "window": 10,
        # Bite-related hives / mild allergic reaction → OTC antihistamine okay
        "exclude_terms": [
            "kagat", "bite", "bitten", "insect", "lamok", "mosquito",
            "allergy", "allergic", "alerdyi",
        ],
        "exclude_window": 10,
    },
    # ── 6. Neurological Event — Stroke ───────────────────────────────────
    {
        "flag":    "stroke_warning",
        "message": RED_FLAG_MESSAGES["stroke_warning"],
        "a_terms": [
            # Numbness / loss of sensation
            "numb", "numbness", "manhid", "namamanhid", "nangalay",
            "pamamanhid", "namimighati",
            # Weakness / paralysis
            "weak", "weakness", "nanghina", "nanghihina", "humina",
            "paralysis", "paralyzed", "paralysed",
            "hindi makagalaw", "di makagalaw", "dili makalihok",
            # Sudden speech loss (stroke sign)
            "slurred", "paos",
            "hindi makapagsalita", "di makapagsalita",
            "hindi makasalita", "dili makasulti",
        ],
        "b_terms": [
            # Face / head area
            "face", "mukha", "pisngi",
            # Half / side body
            "half", "kalahati", "one side", "tabi", "isang tabi",
            # Limbs
            "arm", "kamay", "braso",
            "leg", "binti", "paa",
            # General body
            "body", "katawan", "lawas",
        ],
        "window": 8,
        # Dental nerve pain radiating to face → OTC analgesic okay
        "exclude_terms": [
            "ngipin", "tooth", "teeth", "dental", "molar",
            "ipin", "panga", "labi",
        ],
        "exclude_window": 7,
    },
    # ── 7. Severe Allergic Reaction / Anaphylaxis ─────────────────────────
    {
        "flag":    "severe_allergic_reaction",
        "message": RED_FLAG_MESSAGES["severe_allergic_reaction"],
        "a_terms": [
            # English
            "swollen", "swelling", "swells", "swelled",
            # Tagalog
            "namamaga", "pamamaga", "nangamaga", "namaga", "lumobo",
            # Bisaya
            "namubong", "mubong",
        ],
        "b_terms": [
            # Airways / face
            "throat", "lalamunan", "tutunlan", "tilaok",
            "tongue", "dila",
            "lips", "labi",
            "face", "mukha",
            "airway",
        ],
        "window": 6,
    },
    # ── 8. Head / Facial Bleeding ───────────────────────────────────────────
    {
        "flag":    "head_bleeding",
        "message": RED_FLAG_MESSAGES["head_bleeding"],
        "a_terms": [
            "blood", "bleed", "bleeding", "bled", "bloody", "hemorrhage",
            "dugo", "nagdurugo", "nagdudugo", "dumudugo", "nagdugo",
            "nadugo", "nagadugo", "naay dugo", "madugo", "maduguon", "gadugo",
        ],
        "b_terms": [
            "head", "ulo", "bungo", "skull",
            "noo", "forehead", "temple",
            "mukha", "face", "pisngi",
            "utak", "brain",
        ],
        "window": 6,
    },
    # ── 9. Nosebleed ────────────────────────────────────────────────────
    {
        "flag":    "nose_bleeding",
        "message": RED_FLAG_MESSAGES["nose_bleeding"],
        "a_terms": [
            "blood", "bleed", "bleeding", "bled", "bloody",
            "dugo", "nagdurugo", "nagdudugo", "dumudugo", "nagdugo",
            "nadugo", "nagadugo", "naay dugo", "madugo", "gadugo",
        ],
        "b_terms": ["nose", "ilong", "nostrils", "nostril"],
        "window": 6,
    },
    # ── 10. Ear Bleeding ─────────────────────────────────────────────
    {
        "flag":    "ear_bleeding",
        "message": RED_FLAG_MESSAGES["ear_bleeding"],
        "a_terms": [
            "blood", "bleed", "bleeding", "bled", "bloody",
            "dugo", "nagdurugo", "nagdudugo", "dumudugo", "nagdugo",
            "nadugo", "nagadugo", "naay dugo", "madugo", "gadugo",
        ],
        "b_terms": ["ear", "ears", "tenga", "dalunggan"],
        "window": 6,
    },
    # ── 11. Hemoptysis (Coughing Blood) ──────────────────────────────────────
    {
        "flag":    "hemoptysis",
        "message": RED_FLAG_MESSAGES["hemoptysis"],
        "a_terms": [
            "blood", "bleed", "bleeding", "bled", "bloody",
            "dugo", "nagdurugo", "nagdudugo", "dumudugo", "nagdugo",
            "nadugo", "nagadugo", "naay dugo", "madugo", "gadugo",
        ],
        "b_terms": [
            "cough", "coughing", "coughed", "coughs",
            "ubo", "inuubo", "umuubo", "umubo", "inutubo",
            "gi-ubo", "giubo", "nag-ubo", "nauubo", "mag-ubo",
        ],
        "window": 7,
        # Avoid false positives when "blood" refers to BP/hypertension
        # or when blood is explicitly denied (e.g., "walay dugo").
        "exclude_terms": [
            "high blood",
            "highblood",
            "blood pressure",
            "hypertension",
            "hypertensive",
            "hbp",
            "presyon",
            "alta presyon",
            "blood sugar",
            "high sugar",
            "diabetes",
            "diabetic",
            "walang dugo",
            "wala dugo",
            "walay dugo",
            "no blood",
            "without blood",
        ],
        "exclude_window": 8,
    },
    # ── 12. Hematuria (Blood in Urine) ─────────────────────────────────────
    {
        "flag":    "blood_in_urine",
        "message": RED_FLAG_MESSAGES["blood_in_urine"],
        "a_terms": [
            "blood", "bleed", "bleeding", "bled", "bloody",
            "dugo", "nagdurugo", "nagdudugo", "dumudugo", "nagdugo",
            "nadugo", "nagadugo", "naay dugo", "madugo", "gadugo",
        ],
        "b_terms": [
            "urine", "pee", "peed", "urinate", "urinating",
            "ihi", "umiihi", "orina", "mihihi",
        ],
        "window": 8,
    },
]

# ---------------------------------------------------------------------------
# Direct single-keyword red flags (no co-occurrence required)
# ---------------------------------------------------------------------------

_PREGNANCY_TERMS = [
    "buntis", "pregnant", "nagbubuntis", "naglilihi",
    "pagbubuntis", "preggy", "expecting",
]
_PREGNANCY_EXCLUSIONS = [
    # Proxy purchasing context: buying OTC for a pregnant relative
    "asawa", "misis", "kapatid", "sister", "ate",
    "wife", "girlfriend", "partner",
    "nanay", "mama", "lola", "auntie", "tita",
]

_DIRECT_DENGUE_TERMS = [
    # If the patient explicitly says "dengue", no co-occurrence needed.
    "dengue",
]

_DIRECT_SEIZURE_TERMS = [
    "seizure", "seizures", "convulsion", "convulsions",
    "kombulsyon", "kumbulsyon", "fit", "fits",
    "nanginginig buong katawan",
]

_DIRECT_LOSS_CONSCIOUSNESS_TERMS = [
    "fainted", "fainting",
    "passed out", "passing out",
    "unconscious", "unresponsive",
    "nahimatay", "hinimatay", "namatay sa pagod",
    "nawalan ng malay", "nawalan ng ulirat",
    "blackout", "blacked out",
]

_HYPERTENSION_TERMS = [
    "high blood",
    "highblood",
    "blood pressure",
    "high bp",
    "hbp",
    "hypertension",
    "hypertensive",
    "alta presyon",
    "mataas presyon",
    "taas presyon",
    "presyon",
]

# OTC-target symptom cues. Used to suppress over-triage when hypertension is
# mentioned as background/comorbidity after a contrastive boundary.
_OTC_PRIMARY_SYMPTOM_CUES = [
    "ubo", "cough", "sipon", "runny", "barado", "ilong",
    "lagnat", "fever", "ulo", "headache", "tiyan", "stomach",
    "pagtatae", "diarrhea", "rash", "pantal", "lalamunan", "throat",
    "lawas", "katawan",
]

# Hyperthermia helpers
_FEVER_TERMS = [
    "fever", "lagnat", "hilanat", "hilanat",
    "temp", "temperature", "init", "mainit",
]
_TEMP_EXCLUSIONS = [
    "kilo", "kg", "pounds", "lb",
    "edad", "years old", "years", "taon", "gulang",
]

# Severe dehydration helpers (3-part: diarrhea + negation + urine)
# ---------------------------------------------------------------------------
# Shared blood-term vocabulary (used by triage rules + blood-context filter)
# ---------------------------------------------------------------------------
_ALL_BLOOD_TERMS: List[str] = [
    # English
    "blood", "bleed", "bleeding", "bled", "bloody", "hemorrhage",
    # Tagalog
    "dugo", "nagdurugo", "nagdudugo", "dumudugo", "nagdugo",
    "nadugo", "may dugo", "nagdididugo",
    # Bisaya / Cebuano  ("naga dugo" tokenises as ["naga","dugo"] so "dugo" alone fires)
    "nagadugo", "naay dugo", "madugo", "maduguon", "gadugo",
]

_DEHYDRATION_DIARRHEA_TERMS = [
    "diarrhea", "diarrea", "diarrhoea", "diarreha",
    "pagtatae", "nagtatae", "lbm", "kalibang",
    "loose stool", "watery stool", "loose bowel",
]
_DEHYDRATION_NEGATION_TERMS = [
    "wala", "walang", "walay", "no", "not",
    "hindi", "di", "dili", "without",
]
_DEHYDRATION_URINE_TERMS = [
    "ihi", "urine", "pee", "peeing", "urinate", "urinating",
    "umihi", "umiihi", "makaiihi",
]


def _normalize_for_triage(text: str) -> str:
    # Keep digits intact for temperature checks.
    nt = (text or "").lower().strip()
    nt = re.sub(r"[''']", "", nt)
    nt = re.sub(r"[^a-z0-9ñ\s]", " ", nt)
    nt = re.sub(r"\s+", " ", nt)
    return nt


def _tokenize_triage(text: str) -> List[str]:
    return [tok for tok in text.split(" ") if tok]


def _term_token_sequences(terms: List[str]) -> List[List[str]]:
    out: List[List[str]] = []
    for t in terms:
        toks = [x for x in t.strip().split(" ") if x]
        if toks:
            out.append(toks)
    return out


def _find_term_hits(tokens: List[str], terms: List[str]) -> List[Tuple[int, int, str]]:
    """Return (start, end, matched_text) for each term occurrence."""
    hits: List[Tuple[int, int, str]] = []
    seqs = _term_token_sequences(terms)
    if not tokens or not seqs:
        return hits

    for i in range(len(tokens)):
        for seq in seqs:
            n = len(seq)
            if i + n > len(tokens):
                continue
            if tokens[i : i + n] == seq:
                hits.append((i, i + n - 1, " ".join(tokens[i : i + n])))
    return hits


def _pair_gap(a: Tuple[int, int, str], b: Tuple[int, int, str]) -> int:
    a_start, a_end, _ = a
    b_start, b_end, _ = b
    if a_end < b_start:
        return b_start - a_end - 1
    if b_end < a_start:
        return a_start - b_end - 1
    return 0


def _has_local_exclusion(
    exclusion_hits: List[Tuple[int, int, str]],
    left: int,
    right: int,
    *,
    margin: int = 2,
) -> bool:
    lo = max(0, left - margin)
    hi = right + margin
    for s, e, _ in exclusion_hits:
        if e >= lo and s <= hi:
            return True
    return False


def _detect_by_cooccurrence(tokens: List[str], rule: Dict[str, Any]) -> Optional[str]:
    a_hits = _find_term_hits(tokens, rule.get("a_terms", []))
    b_hits = _find_term_hits(tokens, rule.get("b_terms", []))
    if not a_hits or not b_hits:
        return None

    exclusion_hits = _find_term_hits(tokens, rule.get("exclude_terms", []))
    window = int(rule.get("window", 5))
    exclusion_margin = int(rule.get("exclude_window", 2))

    for a in a_hits:
        for b in b_hits:
            if _pair_gap(a, b) > window:
                continue
            left = min(a[0], b[0])
            right = max(a[1], b[1])
            if exclusion_hits and _has_local_exclusion(exclusion_hits, left, right, margin=exclusion_margin):
                continue
            return f"{a[2]} + {b[2]}"
    return None


def _detect_pregnancy(tokens: List[str]) -> Optional[str]:
    preg_hits = _find_term_hits(tokens, _PREGNANCY_TERMS)
    if not preg_hits:
        return None
    excl_hits = _find_term_hits(tokens, _PREGNANCY_EXCLUSIONS)
    for p in preg_hits:
        if excl_hits and _has_local_exclusion(excl_hits, p[0], p[1], margin=3):
            continue
        return p[2]
    return None


def _detect_hyperthermia(tokens: List[str]) -> Optional[str]:
    """Fever + temperature digit (40/41/42) within a token window.
    Excludes weight/age numbers via _TEMP_EXCLUSIONS.
    """
    fever_hits = _find_term_hits(tokens, _FEVER_TERMS)
    if not fever_hits:
        return None

    temp_hits: List[Tuple[int, int, str]] = []
    for i, tok in enumerate(tokens):
        if tok in {"40", "41", "42"}:
            temp_hits.append((i, i, tok))
            continue
        # Handle fused tokens like "40c", "41deg", "42degrees"
        m = re.match(r"^(40|41|42)(c|deg|degrees|degree|celsius)?$", tok)
        if m:
            temp_hits.append((i, i, m.group(1)))

    if not temp_hits:
        return None

    excl_hits = _find_term_hits(tokens, _TEMP_EXCLUSIONS)
    for fh in fever_hits:
        for th in temp_hits:
            if _pair_gap(fh, th) > 9:
                continue
            left = min(fh[0], th[0])
            right = max(fh[1], th[1])
            if excl_hits and _has_local_exclusion(excl_hits, left, right, margin=3):
                continue
            return f"{fh[2]} + {th[2]}"
    return None


def _detect_dehydration(tokens: List[str]) -> Optional[str]:
    """Three-part check: diarrhea term + negation + urine term nearby.

    Multi-word b_terms like 'walang ihi' fail token-sequence matching when
    particles intervene ('walang akong ihi'). This handler implements the
    semantics properly: negation must be within 3 tokens of a urine word,
    and that negation-urine cluster must be within 12 tokens of a diarrhea word.
    """
    diarrhea_hits = _find_term_hits(tokens, _DEHYDRATION_DIARRHEA_TERMS)
    if not diarrhea_hits:
        return None
    neg_hits = _find_term_hits(tokens, _DEHYDRATION_NEGATION_TERMS)
    urine_hits = _find_term_hits(tokens, _DEHYDRATION_URINE_TERMS)
    if not neg_hits or not urine_hits:
        return None
    for neg in neg_hits:
        for urine in urine_hits:
            if _pair_gap(neg, urine) > 3:
                continue
            # Confirmed negation-urine pair
            pair_left = min(neg[0], urine[0])
            pair_right = max(neg[1], urine[1])
            for dh in diarrhea_hits:
                if _pair_gap(dh, (pair_left, pair_right, "")) <= 14:
                    return f"{dh[2]} + {neg[2]} {urine[2]}"
    return None


def _segment_has_any_phrase(segment: str, terms: List[str]) -> bool:
    for term in terms:
        t = term.strip().lower()
        if not t:
            continue
        if " " in t:
            if re.search(rf"\b{re.escape(t)}\b", segment):
                return True
        else:
            if re.search(rf"\b{re.escape(t)}\b", segment):
                return True
    return False


def _first_matched_phrase(segment: str, terms: List[str]) -> Optional[str]:
    for term in terms:
        t = term.strip().lower()
        if not t:
            continue
        if " " in t:
            if re.search(rf"\b{re.escape(t)}\b", segment):
                return t
        else:
            if re.search(rf"\b{re.escape(t)}\b", segment):
                return t
    return None


def _detect_hypertension_context(normalized_text: str) -> Optional[str]:
    """Detect hypertension as a safety red-flag with context-aware suppression.

    Policy:
    - Flag primary hypertension complaints (e.g., "naa koy high blood").
    - Do NOT over-triage incidental comorbidity mentions after contrastive
      boundaries when another OTC symptom is the active complaint
      (e.g., "may sipon at ubo ako, pero may high blood ako").
    """
    nt = normalized_text
    if not _segment_has_any_phrase(nt, _HYPERTENSION_TERMS):
        return None

    # Respect explicit negation such as "wala koy high blood".
    neg = r"\b(wala|walang|walay|no|not|without|dili|di|hindi|hnd)\b"
    if re.search(rf"{neg}(?:\s+\w+){{0,2}}\s+\b(high\s+blood|highblood|blood\s+pressure|high\s+bp|hbp|hypertension|hypertensive|alta\s+presyon|mataas\s+presyon|taas\s+presyon|presyon)\b", nt):
        return None

    segments = [s.strip() for s in re.split(r"\b(?:pero|but|kaso|however|though)\b", nt) if s.strip()]
    if not segments:
        return None

    for idx, seg in enumerate(segments):
        matched = _first_matched_phrase(seg, _HYPERTENSION_TERMS)
        if not matched:
            continue

        # If hypertension appears in a later contrastive segment AND earlier
        # segment already contains the likely OTC-target complaint, treat
        # hypertension as background context (no triage for this rule).
        if idx > 0:
            if any(_segment_has_any_phrase(prev, _OTC_PRIMARY_SYMPTOM_CUES) for prev in segments[:idx]):
                continue

        return matched

    return None



def _apply_blood_context_filter(
    user_input: str,
    detected: List[str],
) -> List[str]:
    """Remove symptom labels that are dangerous misclassifications when blood
    context is present near the body-part keyword that triggered the match.

    Runs on BOTH dictionary and semantic results so "naga dugo akong ulo"
    never returns HEADACHE, "nagdudugo ilong" never returns RUNNY_NOSE, etc.
    """
    if not detected:
        return detected

    nt = _normalize_for_triage(user_input)
    tokens = _tokenize_triage(nt)

    blood_hits = _find_term_hits(tokens, _ALL_BLOOD_TERMS)
    if not blood_hits:
        return detected

    filtered = list(detected)

    def _drop_if_near(body_terms: List[str], symptom_labels: set, window: int) -> None:
        nonlocal filtered
        body_hits = _find_term_hits(tokens, body_terms)
        for bh in blood_hits:
            for oh in body_hits:
                if _pair_gap(bh, oh) <= window:
                    filtered = [s for s in filtered if s not in symptom_labels]
                    return

    # Blood near head/ulo → not a headache; it is head bleeding
    _drop_if_near(
        ["head", "ulo", "bungo", "noo", "forehead", "utak", "brain", "mukha", "pisngi"],
        {"HEADACHE"}, window=6,
    )
    # Blood near nose/ilong → not a runny nose / congestion
    _drop_if_near(
        ["nose", "ilong", "nostrils", "nostril"],
        {"RUNNY_NOSE", "NASAL_CONGESTION", "ALLERGIC_RHINITIS"}, window=6,
    )
    # Blood near stool/dumi → not diarrhea; it is GI bleed
    _drop_if_near(
        ["stool", "poop", "feces", "bowel", "dumi", "tae", "bawas", "kalibang", "hugaw", "libang"],
        {"DIARRHEA"}, window=8,
    )
    # Blood near cough/ubo → not OTC cough; it is hemoptysis
    _drop_if_near(
        ["cough", "coughing", "coughed", "ubo", "inuubo", "umuubo", "umubo", "gi-ubo", "giubo", "nag-ubo", "nauubo"],
        {"COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"}, window=7,
    )
    return filtered


def detect_red_flags(user_input: str) -> List[Dict[str, str]]:
    """Stage 0 triage safety detector.

    Uses lexical co-occurrence within token windows and local exclusion terms
    to reduce both missed emergencies and false positives.

    Returns:
        List of dicts: [{"flag": str, "message": str, "matched": str}]
        Empty list means no red flags detected — safe to proceed to OTC.
    """
    nt = _normalize_for_triage(user_input)
    tokens = _tokenize_triage(nt)

    flags: List[Dict[str, str]] = []

    # ── Co-occurrence rules ──
    for rule in _TRIAGE_RULES:
        matched = _detect_by_cooccurrence(tokens, rule)
        if not matched:
            continue
        flags.append({
            "flag":    str(rule["flag"]),
            "message": str(rule.get("message") or RED_FLAG_MESSAGES.get(str(rule["flag"]), str(rule["flag"]))),
            "matched": matched,
        })

    # ── Pregnancy: single keyword with proxy-purchase exclusion ──
    preg_match = _detect_pregnancy(tokens)
    if preg_match:
        flags.append({
            "flag":    "pregnancy_contraindication",
            "message": RED_FLAG_MESSAGES["pregnancy_contraindication"],
            "matched": preg_match,
        })

    # ── Hyperthermia: fever + 40/41/42 within window ──
    hyper_match = _detect_hyperthermia(tokens)
    if hyper_match:
        flags.append({
            "flag":    "high_fever_prolonged",
            "message": RED_FLAG_MESSAGES["high_fever_prolonged"],
            "matched": hyper_match,
        })

    # ── Severe dehydration: 3-part diarrhea + negation + urine ──
    dehydration_match = _detect_dehydration(tokens)
    if dehydration_match:
        # Deduplicate against co-occurrence rule hit (if it already fired)
        if not any(f["flag"] == "severe_dehydration" for f in flags):
            flags.append({
                "flag":    "severe_dehydration",
                "message": RED_FLAG_MESSAGES["severe_dehydration"],
                "matched": dehydration_match,
            })

    # ── Direct dengue keyword ──
    dengue_direct = _find_term_hits(tokens, _DIRECT_DENGUE_TERMS)
    if dengue_direct and not any(f["flag"] == "dengue_warning" for f in flags):
        flags.append({
            "flag":    "dengue_warning",
            "message": RED_FLAG_MESSAGES["dengue_warning"],
            "matched": dengue_direct[0][2],
        })

    # ── Seizure / convulsion ──
    seizure_hits = _find_term_hits(tokens, _DIRECT_SEIZURE_TERMS)
    if seizure_hits:
        flags.append({
            "flag":    "seizure",
            "message": RED_FLAG_MESSAGES["seizure"],
            "matched": seizure_hits[0][2],
        })

    # ── Loss of consciousness / fainting ──
    loc_hits = _find_term_hits(tokens, _DIRECT_LOSS_CONSCIOUSNESS_TERMS)
    if loc_hits:
        flags.append({
            "flag":    "loss_of_consciousness",
            "message": RED_FLAG_MESSAGES["loss_of_consciousness"],
            "matched": loc_hits[0][2],
        })

    # ── Hypertension context (primary complaint only) ──
    hypertension_match = _detect_hypertension_context(nt)
    if hypertension_match:
        flags.append({
            "flag":    "hypertension_risk",
            "message": RED_FLAG_MESSAGES["hypertension_risk"],
            "matched": hypertension_match,
        })

    # A co-occurrence window is not enough when one component is explicitly
    # denied (for example "walang pantal pero may lagnat").
    if _explicitly_negates_fever(user_input) or _explicitly_negates_rash(user_input):
        flags = [row for row in flags if row.get("flag") != "dengue_warning"]

    # De-duplicate while preserving first-hit order
    deduped: List[Dict[str, str]] = []
    seen: set[str] = set()
    for row in flags:
        name = row.get("flag", "")
        if name in seen:
            continue
        seen.add(name)
        deduped.append(row)
    return deduped


def _normalize(text: str) -> str:
    text = (text or "").lower().strip()

    # De-jejemize / leetspeak normalization (keep deterministic)
    text = text.translate(
        str.maketrans(
            {
                "@": "a",
                "0": "o",
                "1": "i",
                "3": "e",
                "4": "a",
                "5": "s",
                "7": "t",
                "8": "b",
                "$": "s",
                "!": "i",
                "|": "i",
            }
        )
    )
    # Apostrophes are stripped entirely (not replaced by space) so English
    # contractions match the neg-word lists: "isn't" -> "isnt", "don't" -> "dont".
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9ñ\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Shared negation word set (normalized: apostrophes stripped, so "isn't"
# becomes "isnt" and matches "isnt"). Window is up to 4 filler words.
_NEG_RX = (
    r"(?:wala|walang|walay|waley|no|not|without|never|none|neither|nor|"
    r"no\s+more|dont|doesnt|didnt|isnt|arent|wasnt|werent|havent|hasnt|"
    r"cant|wont|dili|di|dli|hindi|hnd|wara|wa)"
)
_NEG_WINDOW = 4


def _explicitly_negates_fever(user_input: str, _nt: str = "") -> bool:
    nt = _nt or _normalize(user_input)
    # Handle common mixed-language patterns like:
    # - "wala akong fever" / "walang fever" / "no fever"
    # - "wala akong lagnat" / "walang lagnat" / "walay hilanat"
    # - "i dont have a fever" (contractions)
    return (
        re.search(
            rf"\b{_NEG_RX}\b(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+\b(fever|lagnat|sinat|hilanat|hilantan)\b",
            nt,
        )
        is not None
    )


def _explicitly_negates_headache(user_input: str, _nt: str = "") -> bool:
    nt = _nt or _normalize(user_input)
    # Examples we want to respect:
    # - "no headache" / "not headache"
    # - "not sakit ulo" / "walang sakit ulo" / "dili sakit ulo"
    # - "wala akong headache" / "wala koy sakit ulo"
    # Guard: "dili mawala ang sakit sakong ulo" (won't go away) is NOT a
    # negation of headache — the neg word targets the trap verb, not the symptom.
    _TRAP_RX = (
        r"(?:mawala|nawawala|nawala|nawagtang|mohunong|hunong|huminto|"
        r"tigil|hinto|stop|undang|naundang)"
    )
    has_trap = re.search(
        rf"\b{_NEG_RX}\b(?:\s+\w+){{0,3}}\s+\b{_TRAP_RX}\b", nt
    ) is not None
    if has_trap:
        return False
    return (
        re.search(rf"\b{_NEG_RX}\b(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+\b(headache|head|ulo)\b", nt) is not None
        or re.search(rf"\b{_NEG_RX}\b(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+sakit\s+ulo\b", nt) is not None
        or re.search(
            rf"\b{_NEG_RX}\b(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+labad\b(?:\s+\w+){{0,2}}\s+\b(head|ulo)\b",
            nt,
        )
        is not None
    )


def _explicitly_negates_cough(user_input: str, _nt: str = "") -> bool:
    nt = _nt or _normalize(user_input)
    # The negation must live in the SAME clause as the cough: split on
    # contrast / consequence / assertion words so "hindi ako nilalagnat pero
    # may ubo ako" never negates the cough across the "pero".
    for clause in re.split(
        r"\b(?:pero|but|apan|kundi|gawas|maliban|kaso|dahil|because|so|"
        r"however|though|kung|tapos|then|unya|mao|busa|bisan|bisag|naa|"
        r"naay|may|meron|mayroon)\b",
        nt,
    ):
        matches = re.finditer(
            rf"\b{_NEG_RX}\b((?:\s+\w+){{0,{_NEG_WINDOW}}})\s+\b(ubo|cough|coughing|umuubo|inuubo|gihubo|nagubo|nahubo|mihubo)\b",
            clause,
        )
        for m in matches:
            filler_tokens = m.group(1).split()
            # "no plema ... coughing" negates plema, not cough; "isn't a dry
            # cough" negates DRY, not the cough itself; "dili mawala akong ubo"
            # negates MAWALA (won't stop), so the cough persists.
            if any(tok in {"plema", "phlegm", "mucus", "dry", "wet", "tuyo",
                           "tuyong", "uga", "basa", "basang", "productive",
                           "tickly", "mawala", "nawawala", "nawala", "nawagtang",
                           "mohunong", "hunong", "huminto", "tigil", "hinto",
                           "stop", "undang", "naundang"}
                   for tok in filler_tokens):
                continue
            return True
    return False


def _explicitly_negates_diarrhea(user_input: str, _nt: str = "") -> bool:
    nt = _nt or _normalize(user_input)
    return re.search(
        rf"\b{_NEG_RX}\b(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+"
        r"\b(diarrhea|lbm|pagtatae|nagtatae|kalibang|loose\s+stools?|watery\s+stools?)\b",
        nt,
    ) is not None


def _explicitly_negates_sore_throat(user_input: str, _nt: str = "") -> bool:
    nt = _nt or _normalize(user_input)
    return (
        re.search(
            rf"\b{_NEG_RX}\b(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+"
            r"\b(sore\s+throat|throat\s+pain|lalamunan|tutunlan|tilaok)\b",
            nt,
        )
        is not None
        or re.search(
            rf"\b{_NEG_RX}\b(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+(masakit|hapdi|garas)\b"
            rf"(?:\s+\w+){{0,3}}\s+\b(lalamunan|tutunlan|tilaok)\b",
            nt,
        )
        is not None
    )


def _explicitly_negates_nasal(user_input: str, _nt: str = "") -> bool:
    nt = _nt or _normalize(user_input)
    decisions: List[bool] = []
    for clause in re.split(r"\b(?:pero|but|kaso|however|though)\b", nt):
        if not re.search(
            r"\b(sipon|sip-on|runny\s+nose|stuffy\s+nose|nasal\s+congestion|barado|ilong|nose|running|dripping|tumatakbo|tumutulo|nagtulo|tulo|pagtulo)\b",
            clause,
        ):
            continue
        decisions.append(
            re.search(
                rf"\b{_NEG_RX}\b(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+"
                r"\b(sipon|sip-on|runny\s+nose|stuffy\s+nose|nasal\s+congestion|running|dripping|tumatakbo|tumutulo|nagtulo|tulo|pagtulo)\b",
                clause,
            )
            is not None
            or re.search(
                rf"\b{_NEG_RX}\b(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+barado\b(?:\s+\w+){{0,3}}\s+\b(ilong|nose)\b",
                clause,
            )
            is not None
        )
    return decisions[-1] if decisions else False


def _explicitly_negates_allergy(user_input: str, _nt: str = "") -> bool:
    nt = _nt or _normalize(user_input)
    if re.search(r"\b(di|hindi|dili)\s+(ko|ako)\s+alam\s+kung\b", nt):
        return False
    decisions: List[bool] = []
    for clause in re.split(r"\b(?:pero|but|kaso|however|though)\b", nt):
        if not re.search(r"\b(allergy|allergies|allergic)\b", clause):
            continue
        decisions.append(
            re.search(
                rf"\b{_NEG_RX}\b(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+\b(allergy|allergies|allergic)\b",
                clause,
            )
            is not None
        )
    return decisions[-1] if decisions else False


def _explicitly_negates_rash(user_input: str, _nt: str = "") -> bool:
    nt = _nt or _normalize(user_input)
    decisions: List[bool] = []
    for clause in re.split(r"\b(?:pero|but|kaso|however|though)\b", nt):
        if not re.search(r"\b(pantal|rash|rashes|hives|butlig)\b", clause):
            continue
        decisions.append(
            re.search(
                rf"\b{_NEG_RX}\b(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+\b(pantal|rash|rashes|hives|butlig)\b",
                clause,
            )
            is not None
        )
    return decisions[-1] if decisions else False


def _explicitly_negates_body_aches(user_input: str, _nt: str = "") -> bool:
    """Recognize common English, Tagalog, and Cebuano body-pain negations."""
    nt = _nt or _normalize(user_input)
    return (
        re.search(
            rf"\b{_NEG_RX}\b(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+"
            r"\b(body\s*aches?|body\s*pain|katawan|lawas|kalamnan|muscle|muscles)\b",
            nt,
        )
        is not None
        or re.search(
            rf"\b{_NEG_RX}\b(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+\b(sakit|masakit|pain|ache)\b"
            rf"(?:\s+\w+){{0,2}}\s+\b(katawan|body|lawas|kalamnan|muscle)\b",
            nt,
        )
        is not None
    )


def _explicitly_negates_stomach_ache(user_input: str, _nt: str = "") -> bool:
    """Recognize English, Tagalog, and Cebuano stomach-pain negations, in
    both word orders ("my stomach doesn't hurt" / "walang sakit ang tiyan").

    Clause-scoped: the negation must sit in the same clause as the stomach
    word ("stomach pain, but there is no pain in my head" keeps the ache).
    Wellness words consume the negation ("dili maayo akong paminaw sa tiyan"
    means the stomach is NOT fine = the symptom is present, not negated).
    """
    nt = _nt or _normalize(user_input)
    wellness = frozenset({
        "maayo", "maayos", "ok", "okay", "okey", "ayos", "normal", "fine",
        "mauli", "tarong", "taas", "ubos",
    })
    clauses = re.split(
        r"\b(pero|but|kaso|however|though|although)\b", nt
    )
    for clause in clauses:
        neg_pat = rf"\b{_NEG_RX}\b(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+"
        if re.search(
            rf"{neg_pat}\b(stomach|tummy|belly|abdomen|tiyan|tyan|sikmura)\b",
            clause,
        ):
            m = re.search(
                rf"\b({_NEG_RX})\b((?:\s+\w+){{0,{_NEG_WINDOW}}})\s+"
                r"\b(stomach|tummy|belly|abdomen|tiyan|tyan|sikmura)\b",
                clause,
            )
            if m and not any(tok in wellness for tok in m.group(2).split()):
                return True
        if re.search(
            rf"{neg_pat}\b(sakit|masakit|pain|ache|sumasakit)\b"
            rf"(?:\s+\w+){{0,2}}\s+\b(tiyan|stomach|sikmura|tummy|tyan|belly|abdomen)\b",
            clause,
        ):
            return True
        if re.search(
            rf"\b(stomach|tummy|belly|abdomen|tiyan|tyan|sikmura)\b"
            rf"(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+"
            rf"{neg_pat}"
            r"\b(hurt|hurts|pain|ache|aches|sakit|masakit)\b",
            clause,
        ):
            return True
    return False


def _has_any(normalized_text: str, keywords: List[str]) -> bool:
    for kw in keywords:
        # Keywords are expected to already be lowercase simple words;
        # skip the full _normalize() call for speed.
        nkw = kw.lower().strip()
        if not nkw:
            continue
        if " " in nkw:
            if re.search(rf"\b{re.escape(nkw)}\b", normalized_text):
                return True
        else:
            if re.search(rf"\b{re.escape(nkw)}\b", normalized_text):
                return True
    return False


def _apply_semantic_safety_filters(
    user_input: str,
    semantic_detected: List[str],
    diag_rows: Optional[List[dict]] = None,
    red_flags: Optional[List[Dict[str, str]]] = None,
) -> Tuple[List[str], Optional[List[dict]]]:
    filtered = list(semantic_detected)
    filtered_rows = list(diag_rows) if diag_rows is not None else None

    # Normalize once, reuse across all negation checks
    nt = _normalize(user_input)

    def _drop(symptoms: set[str]) -> None:
        nonlocal filtered, filtered_rows
        filtered = [s for s in filtered if s not in symptoms]
        if filtered_rows is not None:
            filtered_rows = [row for row in filtered_rows if row.get("symptom") not in symptoms]

    if _explicitly_negates_fever(user_input, _nt=nt):
        _drop({"FEVER"})

    if _explicitly_negates_headache(user_input, _nt=nt):
        _drop({"HEADACHE"})

    if _explicitly_negates_cough(user_input, _nt=nt):
        _drop({"COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"})

    if _explicitly_negates_diarrhea(user_input, _nt=nt):
        _drop({"DIARRHEA"})

    if _explicitly_negates_sore_throat(user_input, _nt=nt):
        _drop({"SORE_THROAT"})

    if _explicitly_negates_nasal(user_input, _nt=nt):
        _drop({"NASAL_CONGESTION", "RUNNY_NOSE", "ALLERGIC_RHINITIS"})

    if _explicitly_negates_allergy(user_input, _nt=nt):
        _drop({"ALLERGIC_RHINITIS"})

    if _explicitly_negates_body_aches(user_input, _nt=nt):
        _drop({"BODY_ACHES"})

    if _explicitly_negates_stomach_ache(user_input, _nt=nt):
        _drop({"STOMACH_ACHE"})

    if _explicitly_negates_rash(user_input, _nt=nt):
        _drop({"RASHES"})

    # A wholly negative statement must not acquire an unrelated semantic
    # symptom (for example "walang sore throat" -> BODY_ACHES).
    if (
        re.match(r"^(wala|walang|walay|no|not|without|dili|di|hindi|hnd)\b", nt)
        and not re.search(r"\b(pero|but|kaso|however|though)\b", nt)
    ):
        _drop(set(filtered))

    # Blood-context safety filter — shared with dictionary path.
    blood_filtered = _apply_blood_context_filter(user_input, filtered)
    removed_by_blood = set(filtered) - set(blood_filtered)
    if removed_by_blood:
        _drop(removed_by_blood)

    red_flag_names = {row.get("flag") for row in (red_flags or detect_red_flags(user_input))}
    if "blood_in_stool" in red_flag_names:
        _drop({"DIARRHEA"})
    if "hemoptysis" in red_flag_names:
        _drop({"COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"})
    if "head_bleeding" in red_flag_names:
        _drop({"HEADACHE"})
    if "nose_bleeding" in red_flag_names:
        _drop({"RUNNY_NOSE", "NASAL_CONGESTION", "ALLERGIC_RHINITIS"})
    if "severe_allergic_reaction" in red_flag_names:
        _drop({"SORE_THROAT"})
    if "blood_vomit" in red_flag_names:
        _drop({"STOMACH_ACHE"})

    return filtered, filtered_rows


def _semantic_lexical_guard(user_input: str, semantic_detected: List[str]) -> List[str]:
    """Reduce semantic false-positives using cheap keyword gating.

    Rationale: embeddings can over-match short/ambiguous inputs.
    We only allow certain symptoms if the sentence contains at least one
    related keyword family.
    """

    nt = _normalize(user_input)
    if not semantic_detected:
        return semantic_detected

    cough_keywords = [
        "cough",
        "coughing",
        "ubo",
        "inuubo",
        "gi ubo",
        "gi-ubo",
        "g-ubo",
        "gubo",
        "hubak",
        "halak",
        "rattly chest",
        "kumakalansing",
    ]
    plema_keywords = ["plema", "phlegm", "mucus", "yellow stuff", "bringing up", "bring up", "sticky", "glue"]

    diarrhea_keywords = [
        "diarrhea",
        "diarreha",     # common misspelling
        "diarrea",      # common misspelling
        "diarhea",      # common misspelling
        "dayarya",      # Tagalog phonetic
        "loose stool",
        "watery stool",
        "loo",
        "bathroom",
        "toilet",
        "liquid",
        "stool",
        "bowel",
        "pagtatae",
        "nagtatae",
        "lbm",
        "kalibang",
        "nagkalibang",
        "nagkalibanga",
        "kalibanga",
        "gi kalibang",
        "gi kalibang",
        "gi-kalibang",
        "gikalibang",
        "tae",
        "bawas",
        # Alternative phrasings
        "dumi",
        "pabalik balik",
        "loose bowel",
        "tinatae",
        "nagpapataes",
        "gikalibang",
    ]

    nasal_keywords = [
        "nose",
        "ilong",
        "sipon",
        "runny",
        "stuffy",
        "barado",
        "bara",
        "tumutulo",
        "nagatulo",
        "kasimhot",
        "simhot",
    ]

    # Label-specific nasal cues: blocked/stuffy = congestion cues, dripping
    # = runny cues. A bare nose/ilong mention must not let RUNNY_NOSE through.
    nasal_runny_keywords = [
        "sipon",
        "runny",
        "running",
        "tumutulo",
        "nagatulo",
        "dripping",
        "drip",
        "tulo",
    ]
    nasal_congestion_keywords = [
        "stuffy",
        "stuffy nose",
        "blocked",
        "blocked nose",
        "clogged",
        "clogged nose",
        "barado",
        "bara",
        "congestion",
        "nasal congestion",
        "lisod",
        "hard to breathe",
    ]

    fever_keywords = [
        "fever",
        "temperature",
        "hot",
        "warm",
        "feverish",
        "lagnat",
        "nilalagnat",
        "hilanat",
        "gihilanat",
        "init akong lawas",
        "mainit ang katawan",
        "mainit katawan",
        "noo",
        "sinusunog",
        "nasusunog",
        "nanginginig",
        "binat",
        "ginahilanat",
        "nililagnat",
        "sinat",
    ]

    headache_keywords = [
        "headache",
        "head ache",
        "head",
        "ulo",
        "sakit ulo",
        "masakit ulo",
        "labad",
        "migraine",
        # Alternative phrasings
        "tumitibok",
        "kumikislot",
        "humahapdi",
        "pounding",
        "throbbing",
        "gibukbok",
        "sasabog",
        "binibiyak",
        "brain",
        "explode",
        "exploding",
        "pulsing",
        "bumbunan",
    ]

    body_aches_keywords = [
        "body ache",
        "body aches",
        "aches",
        "aching",
        "sore",
        "nanakit ang katawan",
        "masakit katawan",
        "sakit katawan",
        "sakit sa lawas",
        "lawas",
        "katawan",
        "kalamnan",
        "muscle",
        "joints",
        "kasukasuan",
        "likod",
        "back pain",
        # Alternative phrasings
        "binugbog",
        "pinukpok",
        "nanlalamig",
        "giniginaw",
        "nanlalambot",
        "ngalay",
        "nangangalay",
        "buto",
        "bugat",
        "bug at",
        "tibuok lawas",
        "heavy body",
        # Fatigue / weakness
        "nanghihina",
        "nanghina",
        "pagod",
        "luya",
        "kapoy",
        "nahihilo",
        "dizzy",
        "hilo",
        "bigat",
        "mabigat",
    ]

    stomach_keywords = [
        "stomach",
        "tummy",
        "abdomen",
        "abdominal",
        "tiyan",
        "tyan",
        "sikmura",
        "hilab",
        "kabag",
        "sakit tiyan",
        "sakit sa tiyan",
        "sakit sa sikmura",
        "stomach ache",
        # Alternative phrasings
        "buhol buhol",
        "kumukulo",
        "kinukurot",
        "puson",
        "hyperacidity",
        "acidic",
        "heartburn",
        "maasim",
        "cramping",
        # Digestive discomfort
        "gastric",
    ]

    rhinitis_keywords = [
        "sipon",
        "runny nose",
        "stuffy nose",
        "nasal",
        "nose",
        "ilong",
        "bahing",
        "sneeze",
        "sneezing",
        "itchy nose",
        "katol ilong",
        "makati ilong",
        "watery eyes",
        "itchy eyes",
        "katol mata",
        "makati mata",
        # Alternative phrasings
        "alerdyi",
        "aalerdyi",
    ]

    rash_keywords = [
        "rash",
        "rashes",
        "hives",
        "urticaria",
        "pantal",
        "butlig",
        "balat",
        "panit",
        "itch",
        "itchy",
        "makati",
        "katol",
        "pula",
        "red",
        "namumula",
        "nagpula",
        "bumps",
        "red bumps",
    ]

    sore_throat_keywords = [
        "sore throat",
        "throat",
        "lalamunan",
        "tutunlan",
        "tulon",
        "katulon",
        "lunukin",
        "paos",
        "hapdi",
        "garas",
        "tilaok",
        "mutulon",
        "scratchy",
    ]

    allowed: List[str] = []
    for s in semantic_detected:
        if s in {"COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"}:
            if s == "COUGH_PRODUCTIVE":
                has_classic_cough = _has_any(nt, cough_keywords) and _has_any(nt, plema_keywords)
                has_chest_expectoration = _has_any(nt, ["chest", "dibdib", "congestion", "kumakalansing"]) and _has_any(nt, plema_keywords)
                if has_classic_cough or has_chest_expectoration:
                    allowed.append(s)
                continue
            if _has_any(nt, cough_keywords):
                allowed.append(s)
            continue

        if s == "DIARRHEA":
            if _has_any(nt, diarrhea_keywords):
                allowed.append(s)
            continue

        if s in {"NASAL_CONGESTION", "RUNNY_NOSE", "ALLERGIC_RHINITIS"}:
            # Label-specific cues: a runny-nose prediction needs a dripping
            # cue; a congestion prediction needs a stuffiness/blockage cue.
            # Generic nose/ilong mention alone must not elevate RUNNY_NOSE.
            if s == "RUNNY_NOSE":
                if _has_any(nt, nasal_runny_keywords):
                    allowed.append(s)
            elif s == "NASAL_CONGESTION":
                if _has_any(nt, nasal_congestion_keywords) or _has_any(nt, nasal_keywords):
                    allowed.append(s)
            else:
                # ALLERGIC_RHINITIS — allergy/sneeze/itch context.
                if _has_any(nt, ["allergy", "allergic", "bahing", "sneeze", "makati", "katol"]):
                    allowed.append(s)
            continue

        if s == "FEVER":
            if _has_any(nt, fever_keywords):
                allowed.append(s)
            continue

        if s == "HEADACHE":
            if _has_any(nt, headache_keywords):
                allowed.append(s)
            continue

        if s == "BODY_ACHES":
            if _has_any(nt, body_aches_keywords):
                allowed.append(s)
            continue

        if s == "STOMACH_ACHE":
            if _has_any(nt, stomach_keywords):
                allowed.append(s)
            continue

        if s == "ALLERGIC_RHINITIS":
            # Only allow if the sentence is actually about nose/eyes/sneezing.
            if _has_any(nt, rhinitis_keywords):
                allowed.append(s)
            continue

        if s == "RASHES":
            if _has_any(nt, rash_keywords):
                allowed.append(s)
            continue

        if s == "SORE_THROAT":
            if _has_any(nt, sore_throat_keywords):
                allowed.append(s)
            continue

        # Default: keep other symptoms as-is
        allowed.append(s)

    return list(dict.fromkeys(allowed))


def _dictionary_matches(user_input: str) -> List[dict]:
    """Return which symptom + phrase(s) matched in the dictionary stage."""
    try:
        from .step1 import SYMPTOM_DICTIONARY  # type: ignore
    except Exception:
        return []

    normalized_text = _normalize(user_input)
    out: List[dict] = []
    for symptom, phrases in SYMPTOM_DICTIONARY.items():
        matched: List[str] = []
        for p in phrases:
            np = _normalize(p)
            if not np:
                continue
            if " " in np:
                if np in normalized_text:
                    matched.append(p)
            else:
                if re.search(rf"\b{re.escape(np)}\b", normalized_text):
                    matched.append(p)
        if matched:
            out.append({"symptom": symptom, "matched_phrases": matched[:3]})
    return out


_SEMANTIC_EXTRACTOR = None


# ---------------------------------------------------------------------------
# Anchor-based token spell correction for semantic input
# ---------------------------------------------------------------------------
# Before passing text to MiniLM, replace tokens that are misspelled versions
# of the 18 English fuzzy anchors with their correct forms. This dramatically
# improves semantic scores on inputs like "throbing hedache" -> "throbbing headache".
# Only English anchor tokens are corrected; Tagalog/Bisaya tokens are untouched.

from .step1 import (
    _FUZZY_ANCHORS,
    _levenshtein_within,
    _dictionary_word_set,
    _FUZZY_EXCLUDE,
    _NEG_WORDS as _STEP1_NEG_WORDS,
    _NEG_SCOPE_END as _STEP1_NEG_SCOPE_END,
)

# Canonical correction map: anchor word -> correct English spelling to substitute
_ANCHOR_CORRECTIONS: dict = {
    "headache": "headache",
    "toothache": "toothache",
    "stomachache": "stomachache",
    "stomach": "stomach",
    "tummy": "tummy",
    "diarrhea": "diarrhea",
    "fever": "fever",
    "cough": "cough",
    "throat": "throat",
    "sorethroat": "sore throat",
    "nose": "nose",
    "rash": "rash",
    "itchy": "itchy",
    "sneeze": "sneeze",
    "allergy": "allergy",
    "allergic": "allergic",
    "body": "body",
    "runny": "runny",
}

# Tokens that must never be "corrected" — real words, negators, Filipino terms.
# Reuse the same exclusion sets as fuzzy rescue.
_CORRECTION_SKIP: frozenset = frozenset(
    set(_STEP1_NEG_WORDS) | _FUZZY_EXCLUDE | set(_STEP1_NEG_SCOPE_END)
)


def _correct_for_semantic(user_input: str) -> str:
    """Replace misspelled English anchor tokens with their canonical forms.

    This is called only when the semantic stage is about to run — it gives
    MiniLM clean embeddings for tokens that fuzzy rescue already mapped to
    the right label, but which the raw subword tokenizer struggles with.

    Rules (same as fuzzy rescue for safety):
    - Only alphabetic tokens >= 4 chars within |len_diff| <= 2 of an anchor
    - Skips tokens already in the dictionary, negation set, or exclusion set
    - Skips known Tagalog/Bisaya tokens (not in the anchor set)
    - Each token is corrected at most once (first matching anchor wins)
    """
    from .step1 import _normalize as _n1, _KNOWN_LOCAL_TOKENS
    
    # Try to use advanced fuzzy matching if available
    try:
        from .advanced_fuzzy import advanced_fuzzy_match, _ADVANCED_ANCHORS
        use_advanced = True
    except ImportError:
        use_advanced = False

    dict_words = _dictionary_word_set()
    skip = _CORRECTION_SKIP | dict_words

    tokens = user_input.split()
    corrected = []
    for tok in tokens:
        bare = tok.lower().strip(".,;:!?()'\"")
        # Skip: short, non-alpha, known-good, negators, Filipino words
        if (
            len(bare) < 3  # Lower threshold for advanced matching
            or not bare.isalpha()
            or bare in skip
            or bare in _KNOWN_LOCAL_TOKENS
        ):
            corrected.append(tok)
            continue
        
        replaced = False
        
        # Try advanced matching first
        if use_advanced:
            for anchor, label, max_dist, variants in _ADVANCED_ANCHORS:
                if abs(len(bare) - len(anchor)) > 3:
                    continue
                matched = advanced_fuzzy_match(bare, anchor, label, max_dist, variants, min_ngram_score=0.55)
                if matched:
                    corrected.append(anchor)  # Use canonical anchor form
                    replaced = True
                    break
        
        # Fall back to legacy matching
        if not replaced:
            for anchor, label, max_dist in _FUZZY_ANCHORS:
                if abs(len(bare) - len(anchor)) > 2:
                    continue
                if _levenshtein_within(bare, anchor, max_dist):
                    corrected.append(_ANCHOR_CORRECTIONS.get(anchor, anchor))
                    replaced = True
                    break
        
        if not replaced:
            corrected.append(tok)
    
    return " ".join(corrected)


def _get_semantic_extractor():
    """Lazy singleton factory for the semantic fallback backend.

    MENDO_SEMANTIC_BACKEND selects the engine:
      - "minilm" (default) → sentence-transformers embeddings, cosine
        similarity vs. the curated anchor sentences (step2.py)
      - "sailor"            → local LLM (Sailor2) via Ollama (sailor_semantic.py)

    All backends expose the same analyze() protocol, so nothing else in
    the pipeline changes when the engine is swapped.
    """
    global _SEMANTIC_EXTRACTOR
    if _SEMANTIC_EXTRACTOR is not None:
        return _SEMANTIC_EXTRACTOR

    backend = os.getenv("MENDO_SEMANTIC_BACKEND", "minilm").strip().lower()
    if backend == "minilm":
        from .step2 import EmbeddingSymptomExtractor, SYMPTOM_ANCHORS

        _SEMANTIC_EXTRACTOR = EmbeddingSymptomExtractor(SYMPTOM_ANCHORS)
    else:
        from .sailor_semantic import LLMSymptomExtractor

        _SEMANTIC_EXTRACTOR = LLMSymptomExtractor()
    return _SEMANTIC_EXTRACTOR


def extract_symptoms_hybrid(
    user_input: str,
    *,
    semantic_threshold: float = 0.65,
    semantic_top_margin: float = 0.08,
    semantic_max_symptoms: int = 2,
    enable_semantic_fallback: bool = True,
) -> List[str]:
    """Hybrid symptom extraction.

    1) Try dictionary-based extraction.
    2) If nothing found AND fallback enabled, try semantic extraction.

    Returns a distinct list of symptom labels.
    """

    red_flags = detect_red_flags(user_input)
    detected = extract_symptoms_dictionary(user_input)

    # Global negation override for cough at dictionary stage too.
    if _explicitly_negates_cough(user_input):
        detected = [s for s in detected if s not in {"COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"}]

    # Blood-context safety filter: runs on dictionary results so that
    # e.g. "naga dugo akong ulo" never surfaces HEADACHE.
    detected = _apply_blood_context_filter(user_input, detected)

    if detected or not enable_semantic_fallback:
        return detected

    # Lazy import so step3 can still run without sentence-transformers installed
    try:
        from .step2 import EmbeddingSymptomExtractor, SYMPTOM_ANCHORS
    except Exception:
        # If semantic components are not available, gracefully return dictionary result.
        return detected

    try:
        extractor = _get_semantic_extractor()
        semantic_detected, diag = extractor.analyze(user_input, threshold=semantic_threshold)
    except Exception:
        # If the semantic backend isn't available (e.g., dependency not installed),
        # fail safely by returning the deterministic result.
        return detected

    # Reduce false positives while still allowing multi-symptom output:
    # take the TOP-N symptoms that pass the threshold.
    # (semantic_top_margin is kept as a tunable argument, but selection is
    # primarily controlled by the threshold + top-N cap.)
    semantic_detected = _semantic_lexical_guard(user_input, semantic_detected)

    semantic_detected, _ = _apply_semantic_safety_filters(user_input, semantic_detected, red_flags=red_flags)

    scored = sorted(
        ((m.symptom, float(m.score)) for m in diag if m.symptom in semantic_detected),
        key=lambda x: x[1],
        reverse=True,
    )
    selected = [symptom for symptom, _score in scored[:semantic_max_symptoms]]

    # Distinct merge (dictionary first)
    merged = list(dict.fromkeys(detected + selected))
    return merged


def extract_symptoms_hybrid_report(
    user_input: str,
    *,
    semantic_threshold: float,
    semantic_top_margin: float,
    semantic_max_symptoms: int,
    enable_semantic_fallback: bool,
) -> dict:
    """Like extract_symptoms_hybrid, but returns a structured report for benchmarking."""

    report: dict = {
        "input": user_input,
        "stages": [],
        "final": {"symptoms": [], "conditions": []},
    }

    # ── RED-FLAG / TRIAGE CHECK (runs before everything else) ──
    red_flags = detect_red_flags(user_input)
    if red_flags:
        report["red_flags"] = red_flags
        # NOTE: We do NOT short-circuit here — we still extract symptoms so
        # the benchmark can validate symptom detection accuracy.  The triage
        # warning is consumed by step4 / the route layer which decides whether
        # to suppress OTC recommendations and show a "consult a doctor" alert.

    dict_symptoms = extract_symptoms_dictionary(user_input)
    dict_conditions = extract_conditions_dictionary(user_input)

    # Global negation override for cough at dictionary stage.
    if _explicitly_negates_cough(user_input):
        cough_labels = {"COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"}
        dict_symptoms = [s for s in dict_symptoms if s not in cough_labels]

    dict_details = _dictionary_matches(user_input)
    report["stages"].append(
        {
            "stage": "dictionary",
            "used": True,
            "detected": dict_symptoms,
            "detected_conditions": dict_conditions,
            "details": dict_details,
        }
    )

    # Always try semantic model — even when dictionary has results — so the
    # transformer can correct dictionary false positives (e.g. "ngipon" → RUNNY_NOSE).
    try:
        extractor = _get_semantic_extractor()
        observational_only = getattr(extractor, "fallback_only", False) and bool(dict_symptoms)
        # When the dictionary already hit, MiniLM still runs to produce audit
        # scores (visible in the admin logs), but its output does NOT influence
        # the final decision — the dictionary result is authoritative.

        # Spell-correct English anchor tokens before encoding — "throbing hedache"
        # -> "throbbing headache" gives MiniLM a clean embedding instead of
        # broken subword pieces. Tagalog/Bisaya tokens are never touched.
        semantic_input = _correct_for_semantic(user_input)
        semantic_detected, diag = extractor.analyze(semantic_input, threshold=semantic_threshold)
        semantic_detected = _semantic_lexical_guard(user_input, semantic_detected)
        diag_sorted = sorted(
            [
                {
                    "symptom": m.symptom,
                    "score": float(m.score),
                    "best_anchor": m.best_anchor,
                }
                for m in diag
            ],
            key=lambda x: x["score"],
            reverse=True,
        )

        semantic_detected, diag_sorted = _apply_semantic_safety_filters(
            user_input,
            semantic_detected,
            diag_rows=diag_sorted,
            red_flags=red_flags,
        )

        # Partition the audit rows so symptoms the lexical guard / safety
        # filters rejected are NOT ranked ahead of plausible candidates. The
        # raw cosine list is otherwise noise-driven: DIARRHEA's best anchor can
        # out-rank FEVER's on a fever sentence even though DIARRHEA was vetoed.
        kept = set(semantic_detected)
        candidate_rows = [row for row in diag_sorted if row["symptom"] in kept]
        vetoed_rows = [
            {**row, "vetoed": True, "veto_reason": "rejected_by_lexical_guard_or_safety_filter"}
            for row in diag_sorted
            if row["symptom"] not in kept
        ]
        diag_sorted = candidate_rows + vetoed_rows
    except Exception as e:
        # Semantic unavailable — fall back to dictionary-only
        report["stages"].append(
            {
                "stage": "semantic",
                "used": True,
                "available": False,
                "error": str(e),
            }
        )
        report["final"]["symptoms"] = dict_symptoms
        report["final"]["conditions"] = dict_conditions
        report["final"]["source"] = "dictionary" if dict_symptoms else "none"
        return report

    # Select TOP-N semantic candidates
    candidates = [row for row in diag_sorted if row["symptom"] in semantic_detected]
    semantic_selected = [row["symptom"] for row in candidates[:semantic_max_symptoms]]

    report["stages"].append(
        {
            "stage": "semantic",
            "used": True,
            "available": True,
            "observational_only": observational_only,
            "threshold": semantic_threshold,
            "top_margin": semantic_top_margin,
            "max_symptoms": semantic_max_symptoms,
            "input_corrected": semantic_input if semantic_input != user_input else None,
            "detected_raw": semantic_detected,
            "detected_selected": semantic_selected,
            "scores": diag_sorted,
        }
    )

    # When the dictionary already matched, it is the authoritative source.
    # Semantic scores are recorded for audit/display but do not alter the result.
    if observational_only:
        report["final"]["symptoms"] = dict_symptoms
        report["final"]["conditions"] = dict_conditions
        report["final"]["source"] = "dictionary"
        return report

    # Merge semantic candidates with deterministic dictionary hits. Dictionary
    # phrases already pass explicit negation, idiom, and safety filters; a
    # pretrained similarity model must not veto strong lexical evidence.
    merged = list(semantic_selected)  # semantic takes priority
    for s in dict_symptoms:
        if s not in merged:
            merged.append(s)

    merged = list(dict.fromkeys(merged))

    report["final"]["symptoms"] = merged
    report["final"]["conditions"] = dict_conditions
    report["final"]["source"] = "hybrid_merged" if merged else "none"
    return report


def _interactive_loop(args: argparse.Namespace) -> int:
    print("Hybrid Symptom Extractor (type 'exit' to quit)")
    if args.flow:
        print("Tip: use --debug to show matches/scores.")
    print("")
    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            return 0

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "q"}:
            return 0

        report = extract_symptoms_hybrid_report(
            user_input,
            semantic_threshold=args.semantic_threshold,
            semantic_top_margin=args.semantic_top_margin,
            semantic_max_symptoms=args.semantic_max_symptoms,
            enable_semantic_fallback=not args.no_semantic,
        )

        if args.json:
            print(json.dumps(report, ensure_ascii=False))
            continue

        if args.flow or args.debug:
            _print_flow(report, debug=args.debug)
        else:
            print("DETECTED:", report["final"]["symptoms"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Hybrid symptom extractor (dictionary + semantic fallback)")
    parser.add_argument("--text", type=str, default=None, help="Analyze a single input text")
    parser.add_argument("--interactive", action="store_true", help="Start an interactive prompt")
    parser.add_argument("--semantic-threshold", type=float, default=0.65, help="Semantic similarity threshold")
    parser.add_argument("--semantic-top-margin", type=float, default=0.08, help="Keep matches within this margin of top score")
    parser.add_argument("--semantic-max-symptoms", type=int, default=2, help="Max symptoms from semantic fallback")
    parser.add_argument("--no-semantic", action="store_true", help="Disable semantic fallback (dictionary only)")
    parser.add_argument("--flow", action="store_true", help="Print step-by-step tagged flow output")
    parser.add_argument("--debug", action="store_true", help="Print deeper debug (matched phrases + top semantic scores)")
    parser.add_argument("--json", action="store_true", help="Print JSON per input (good for benchmarking logs)")
    args = parser.parse_args()

    if args.text is not None:
        report = extract_symptoms_hybrid_report(
            args.text,
            semantic_threshold=args.semantic_threshold,
            semantic_top_margin=args.semantic_top_margin,
            semantic_max_symptoms=args.semantic_max_symptoms,
            enable_semantic_fallback=not args.no_semantic,
        )
        if args.json:
            print(json.dumps(report, indent=2, ensure_ascii=False))
        elif args.flow or args.debug:
            _print_flow(report, debug=args.debug)
        else:
            print("INPUT:", args.text)
            print("DETECTED:", report["final"]["symptoms"])
        return 0

    # Default behavior: interactive if no --text provided.
    if args.interactive or args.text is None:
        return _interactive_loop(args)

    return 0


def _print_flow(report: dict, *, debug: bool) -> None:
    """Pretty, thesis-panel-friendly flow output."""

    user_input = report.get("input", "")
    final = report.get("final", {})
    final_symptoms = final.get("symptoms", [])
    final_source = final.get("source", "unknown")

    print(f"INPUT:   {user_input}")

    # Stage 1: dictionary
    dict_stage = next((s for s in report.get("stages", []) if s.get("stage") == "dictionary"), None)
    if dict_stage is not None:
        dict_detected = dict_stage.get("detected", [])
        print(f"STAGE1:  DICTIONARY -> {dict_detected}")
        if debug and dict_stage.get("details"):
            for d in dict_stage["details"]:
                phrases = d.get("matched_phrases", [])
                print(f"         hit {d.get('symptom')}: {phrases}")

    # Stage 2: semantic
    sem_stage = next((s for s in report.get("stages", []) if s.get("stage") == "semantic"), None)
    if sem_stage is not None:
        if not sem_stage.get("available", True):
            print(f"STAGE2:  SEMANTIC (unavailable) -> error={sem_stage.get('error')}")
        else:
            thr = sem_stage.get("threshold")
            top_margin = sem_stage.get("top_margin")
            max_sym = sem_stage.get("max_symptoms")
            raw = sem_stage.get("detected_raw", [])
            selected = sem_stage.get("detected_selected", [])
            print(f"STAGE2:  SEMANTIC fallback -> selected={selected}")
            if debug:
                print(f"         params: threshold={thr} top_margin={top_margin} max={max_sym} raw={raw}")
                for row in sem_stage.get("scores", [])[:6]:
                    print(
                        f"         score {row['symptom']}: {row['score']:.4f} (anchor: {row['best_anchor']!r})"
                    )

    print(f"FINAL:   {final_symptoms}  (source={final_source})")


if __name__ == "__main__":
    raise SystemExit(main())
