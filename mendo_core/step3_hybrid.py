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
import re
from typing import Dict, List, Optional, Tuple

from .step1 import extract_symptoms as extract_symptoms_dictionary


# ---------------------------------------------------------------------------
# RED-FLAG / TRIAGE LAYER
# ---------------------------------------------------------------------------
# Emergency symptoms that should NOT receive OTC recommendations.
# The system must redirect to "Consult a doctor immediately."
# Covers English, Tagalog, Bisaya, and Taglish.

RED_FLAG_PATTERNS: Dict[str, List[str]] = {
    "chest_pain": [
        # English
        r"\bchest\s+pain\b",
        r"\bchest\s+tightness\b",
        r"\btight\s+chest\b",
        r"\bpain\s+in\s+(my\s+)?chest\b",
        r"\bchest\s+hurts?\b",
        # Tagalog
        r"\bsakit\s+(ng\s+|sa\s+)?dibdib\b",
        r"\bmasakit\s+(ang\s+)?dibdib\b",
        r"\bsumasakit\s+(ang\s+)?dibdib\b",
        r"\bkirot\s+(ng\s+|sa\s+)?dibdib\b",
        # Bisaya
        r"\bsakit\s+(akong\s+)?dughan\b",
    ],
    "difficulty_breathing": [
        # English
        r"\bshortness\s+of\s+breath\b",
        r"\bdifficulty\s+breathing\b",
        r"\bcan'?t\s+breathe\b",
        r"\bhard\s+to\s+breathe\b",
        r"\btrouble\s+breathing\b",
        r"\bbreathing\s+difficulty\b",
        r"\bstruggle\s+to\s+breathe\b",
        # Tagalog
        r"\bhirap\s+huminga\b",
        r"\bhindi\s+(ako\s+)?makahinga\b",
        r"\bnahihirapan\s+huminga\b",
        r"\bhingal\s+na\s+hingal\b",
        r"\bdi\s+(ako\s+)?makahinga\b",
        # Bisaya
        r"\blisud\s+moginhawa\b",
        r"\bdili\s+(ko\s+)?makaginhawa\b",
    ],
    "blood_in_stool": [
        r"\bblood\s+in\s+(my\s+)?(stool|poop|feces)\b",
        r"\bbloody\s+(stool|poop|diarrhea)\b",
        r"\bmay\s+dugo\s+(sa|ang)\s+(dumi|tae)\b",
        r"\bdugo\s+(sa|ang)\s+(dumi|tae)\b",
        r"\bmadugo\s+(ang\s+)?(dumi|tae)\b",
    ],
    "blood_vomit": [
        r"\bvomiting\s+blood\b",
        r"\bblood\s+in\s+(my\s+)?vomit\b",
        r"\bbloody\s+vomit\b",
        r"\bnag(su)?suka\s+(ng|ako\s+ng?)\s+dugo\b",
        r"\bmay\s+dugo\s+(sa|ang)\s+suka\b",
    ],
    "severe_allergic_reaction": [
        r"\banaphyla(xis|ctic)\b",
        r"\bswollen\s+(throat|tongue|lips?|face)\b",
        r"\bface\s+swelling\b",
        r"\bnamamaga\s+(ang\s+)?(lalamunan|dila|labi|mukha)\b",
        r"\bhives\s+all\s+over\b",
        r"\bcan'?t\s+swallow\b",
        r"\bhindi\s+(ako\s+)?makalunok\b",
    ],
    "high_fever_prolonged": [
        r"\bfever\s+(?:of\s+)?4[0-2]\b",
        r"\b4[0-2]\s*(?:degrees?|deg|celsius)\b",
        r"\blagnat\s*(?:na\s*)?4[0-2]\b",
        r"\b4[0-2]\s*(?:degrees?|deg)\s*(?:na\s+)?lagnat\b",
        r"\bfever\b.*\b4[0-2]\b",
        r"\blagnat\b.*\b4[0-2]\b",
    ],
    "seizure": [
        r"\bseizure\b",
        r"\bconvulsion\b",
        r"\bkombulsyon\b",
        r"\bnanginginig\s+(buong|ang\s+buong)\s+katawan\b",
    ],
    "loss_of_consciousness": [
        r"\bfainted\b",
        r"\bpassed\s+out\b",
        r"\bunconscious\b",
        r"\bloss\s+of\s+consciousness\b",
        r"\bnahimatay\b",
        r"\bnawalan\s+ng\s+malay\b",
        r"\bhinimatay\b",
    ],
}

# Human-friendly label → message mapping
RED_FLAG_MESSAGES: Dict[str, str] = {
    "chest_pain": "Chest pain detected",
    "difficulty_breathing": "Difficulty breathing detected",
    "blood_in_stool": "Blood in stool detected",
    "blood_vomit": "Blood in vomit detected",
    "severe_allergic_reaction": "Severe allergic reaction signs detected",
    "high_fever_prolonged": "Dangerously high fever detected (≥40°C)",
    "seizure": "Seizure/convulsion reported",
    "loss_of_consciousness": "Loss of consciousness reported",
}


def detect_red_flags(user_input: str) -> List[Dict[str, str]]:
    """Scan user input for emergency/red-flag symptoms.

    Returns a list of dicts: [{"flag": "chest_pain", "message": "...", "matched": "..."}]
    Empty list means no red flags detected.

    NOTE: Uses a LIGHT normalization (lowercase + collapse whitespace) instead
    of the full de-jejemize ``_normalize()`` because the latter converts digits
    (0→o, 4→a, 1→i) which destroys temperature values like "40 degrees".
    """
    nt = user_input.lower().strip()
    nt = re.sub(r"[''']", "", nt)           # can't → cant
    nt = re.sub(r"\s+", " ", nt)
    flags: List[Dict[str, str]] = []
    seen: set = set()

    for flag_name, patterns in RED_FLAG_PATTERNS.items():
        for pat in patterns:
            m = re.search(pat, nt)
            if m and flag_name not in seen:
                seen.add(flag_name)
                flags.append({
                    "flag": flag_name,
                    "message": RED_FLAG_MESSAGES.get(flag_name, flag_name),
                    "matched": m.group(),
                })
                break  # one match per flag category is enough
    return flags


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
    text = re.sub(r"[^a-z0-9ñ\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _explicitly_negates_fever(user_input: str) -> bool:
    nt = _normalize(user_input)
    # Handle common mixed-language patterns like:
    # - "wala akong fever" / "walang fever" / "no fever"
    # - "wala akong lagnat" / "walang lagnat" / "walay hilanat"
    return (
        re.search(r"\b(wala|walang|walay|no|not|without|dili|di|hindi|hnd)\b(?:\s+\w+){0,2}\s+\bfever\b", nt)
        is not None
        or re.search(r"\b(wala|walang|walay|no|not|without|dili|di|hindi|hnd)\b(?:\s+\w+){0,2}\s+\blagnat\b", nt)
        is not None
        or re.search(r"\b(wala|walang|walay|no|not|without|dili|di|hindi|hnd)\b(?:\s+\w+){0,2}\s+\b(hilanat)\b", nt)
        is not None
    )


def _explicitly_negates_headache(user_input: str) -> bool:
    nt = _normalize(user_input)
    # Examples we want to respect:
    # - "no headache" / "not headache"
    # - "not sakit ulo" / "walang sakit ulo" / "dili sakit ulo"
    # - "wala akong headache" / "wala koy sakit ulo"
    neg = r"(wala|walang|walay|no|not|without|dili|di|hindi|hnd)"
    return (
        re.search(rf"\b{neg}\b(?:\s+\w+){{0,3}}\s+\b(headache|head|ulo)\b", nt) is not None
        or re.search(rf"\b{neg}\b(?:\s+\w+){{0,2}}\s+sakit\s+ulo\b", nt) is not None
        or re.search(rf"\b{neg}\b(?:\s+\w+){{0,2}}\s+labad\b(?:\s+\w+){{0,2}}\s+\b(head|ulo)\b", nt)
        is not None
    )


def _explicitly_negates_cough(user_input: str) -> bool:
    nt = _normalize(user_input)
    return (
        re.search(r"\b(wala|walang|walay|no|not|without|dili|di|hindi|hnd)\b(?:\s+\w+){0,2}\s+\b(ubo|cough|coughing|umuubo|inuubo)\b", nt)
        is not None
    )


def _has_any(normalized_text: str, keywords: List[str]) -> bool:
    for kw in keywords:
        nkw = _normalize(kw)
        if not nkw:
            continue
        if " " in nkw:
            if nkw in normalized_text:
                return True
        else:
            if re.search(rf"\b{re.escape(nkw)}\b", normalized_text):
                return True
    return False


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
    ]
    plema_keywords = ["plema", "phlegm", "mucus"]

    diarrhea_keywords = [
        "diarrhea",
        "loose stool",
        "watery stool",
        "stool",
        "bowel",
        "pagtatae",
        "nagtatae",
        "lbm",
        "kalibang",
        "tae",
        # Alternative phrasings
        "dumi",
        "pabalik balik",
        "loose bowel",
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
    ]

    fever_keywords = [
        "fever",
        "temperature",
        "hot",
        "feverish",
        "lagnat",
        "nilalagnat",
        "hilanat",
        "gihilanat",
        "init akong lawas",
        "mainit ang katawan",
        "mainit katawan",
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
    ]

    body_aches_keywords = [
        "body ache",
        "body aches",
        "aches",
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
        "buto",
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
    ]

    allowed: List[str] = []
    for s in semantic_detected:
        if s in {"COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"}:
            if _has_any(nt, cough_keywords):
                # For productive cough, require plema/phlegm/mucus mention too.
                if s == "COUGH_PRODUCTIVE" and not _has_any(nt, plema_keywords):
                    continue
                allowed.append(s)
            continue

        if s == "DIARRHEA":
            if _has_any(nt, diarrhea_keywords):
                allowed.append(s)
            continue

        if s in {"NASAL_CONGESTION", "RUNNY_NOSE", "ALLERGIC_RHINITIS"}:
            # If they mention nose/ilong/sipon, these are plausible.
            if _has_any(nt, nasal_keywords):
                allowed.append(s)
            else:
                # Still allow allergy if explicit "allergy" is mentioned.
                if s == "ALLERGIC_RHINITIS" and _has_any(nt, ["allergy", "allergic", "bahing", "sneeze", "makati", "katol"]):
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


def _get_semantic_extractor():
    """Lazy singleton to avoid re-loading the transformer every request."""
    global _SEMANTIC_EXTRACTOR
    if _SEMANTIC_EXTRACTOR is not None:
        return _SEMANTIC_EXTRACTOR

    from .step2 import EmbeddingSymptomExtractor, SYMPTOM_ANCHORS

    _SEMANTIC_EXTRACTOR = EmbeddingSymptomExtractor(SYMPTOM_ANCHORS)
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

    detected = extract_symptoms_dictionary(user_input)

    # Global negation override for cough at dictionary stage too.
    if _explicitly_negates_cough(user_input):
        detected = [s for s in detected if s not in {"COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"}]

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

    # Global negation override: don't re-add FEVER if explicitly negated.
    if _explicitly_negates_fever(user_input):
        semantic_detected = [s for s in semantic_detected if s != "FEVER"]

    # Global negation override: don't re-add HEADACHE if explicitly negated.
    if _explicitly_negates_headache(user_input):
        semantic_detected = [s for s in semantic_detected if s != "HEADACHE"]

    # Global negation override: don't re-add COUGH if explicitly negated.
    if _explicitly_negates_cough(user_input):
        semantic_detected = [s for s in semantic_detected if s not in {"COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"}]

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
        "final": {"symptoms": []},
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
            "details": dict_details,
        }
    )

    if dict_symptoms or not enable_semantic_fallback:
        report["final"]["symptoms"] = dict_symptoms
        report["final"]["source"] = "dictionary" if dict_symptoms else "dictionary_only"
        return report

    try:
        extractor = _get_semantic_extractor()
        semantic_detected, diag = extractor.analyze(user_input, threshold=semantic_threshold)
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

        # Global negation override: don't let semantic fallback re-add fever
        # when user explicitly denies it.
        if _explicitly_negates_fever(user_input):
            semantic_detected = [s for s in semantic_detected if s != "FEVER"]
            diag_sorted = [row for row in diag_sorted if row.get("symptom") != "FEVER"]

        # Global negation override: don't let semantic fallback re-add headache
        # when user explicitly denies it.
        if _explicitly_negates_headache(user_input):
            semantic_detected = [s for s in semantic_detected if s != "HEADACHE"]
            diag_sorted = [row for row in diag_sorted if row.get("symptom") != "HEADACHE"]

        # Global negation override: don't let semantic fallback re-add cough
        # when user explicitly denies it.
        if _explicitly_negates_cough(user_input):
            cough_labels = {"COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"}
            semantic_detected = [s for s in semantic_detected if s not in cough_labels]
            diag_sorted = [row for row in diag_sorted if row.get("symptom") not in cough_labels]
    except Exception as e:
        report["stages"].append(
            {
                "stage": "semantic",
                "used": True,
                "available": False,
                "error": str(e),
            }
        )
        report["final"]["symptoms"] = []
        report["final"]["source"] = "none"
        return report

    # Select TOP-N symptoms that passed the threshold.
    candidates = [row for row in diag_sorted if row["symptom"] in semantic_detected]
    selected = [row["symptom"] for row in candidates[:semantic_max_symptoms]]

    report["stages"].append(
        {
            "stage": "semantic",
            "used": True,
            "available": True,
            "threshold": semantic_threshold,
            "top_margin": semantic_top_margin,
            "max_symptoms": semantic_max_symptoms,
            "detected_raw": semantic_detected,
            "detected_selected": selected,
            "scores": diag_sorted,
        }
    )

    report["final"]["symptoms"] = selected
    report["final"]["source"] = "semantic_fallback" if selected else "none"
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
