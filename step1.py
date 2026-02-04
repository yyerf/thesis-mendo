"""step1.py

Phrase-Based Symptom Extraction (Deterministic / Dictionary-Based)

Goal (thesis-friendly):
- Handle mixed-language input (Tagalog, Bisaya, English, Taglish/Conyo)
- No ML, no language detection
- Use a fixed dictionary of symptom -> phrases, then scan the sentence

How it works:
1) Normalize the input to make matching consistent (lowercase, remove punctuation)
2) For each symptom, check if any of its phrases appear in the normalized input
3) Return a distinct list of detected symptom labels

You can expand the dictionary by adding more phrases per symptom.
"""

from __future__ import annotations

import re
from typing import Dict, List


# ---------------------------------------------------------------------------
# 1) DICTIONARY: symptom label -> list of phrases/keywords (Tagalog/Bisaya/English)
# ---------------------------------------------------------------------------
# Notes:
# - Keep symptom labels in ALL CAPS so your output is presentation-friendly.
# - Phrases can be single words (e.g., "ubo") or multi-word phrases (e.g., "sakit ulo").
# - Add as many variants/slang as you need for your population.

SYMPTOM_DICTIONARY: Dict[str, List[str]] = {
    "HEADACHE": [
        # English
        "headache",
        "head ache",
        "head hurts",
        "my head hurts",
        # Tagalog / Taglish
        "sakit ulo",
        "masakit ulo",
        "masakit ang ulo",
        "sumasakit ulo",
        "labad ulo",
        "kirot ulo",
        "masakit head",
        "sakit head",
        # Bisaya
        "labad akong ulo",
        "sakit akong ulo",
        "sakit ako'g ulo",
    ],
    # NOTE (thesis/panel-friendly): COUGH is split into 3 intents.
    # - COUGH_PRODUCTIVE: cough with phlegm/mucus (wet cough)
    # - COUGH_DRY: cough without phlegm (dry/tickly cough)
    # - COUGH_GENERAL: user said "ubo" but did not specify wet vs dry
    #
    # These lists are used for basic matching + explanation/debug, but the
    # actual cough-type decision is handled by a dedicated qualifier function
    # (see _extract_cough_type) to properly handle negative matching.
    "COUGH_PRODUCTIVE": [
        # English
        "productive cough",
        "wet cough",
        "cough with phlegm",
        "cough with mucus",
        "chest congestion",
        # Tagalog / Taglish
        "may plema",
        "basang ubo",
        "malapot na plema",
        "ubo na may plema",
        # Bisaya / Conyo
        "naay plema",
        "basa nga ubo",
        "ubo na naay plema",
        "with plema",
        "halak",
        "hubak",
    ],
    "COUGH_DRY": [
        # English
        "dry cough",
        "tickly cough",
        "no phlegm",
        "without phlegm",
        "itchy throat",
        "scratchy throat",
        # Tagalog
        "tuyong ubo",
        "walang plema",
        "makati lalamunan",
        # Bisaya
        "uga nga ubo",
        "walay plema",
        "makatol ang tutunlan",
    ],
    "COUGH_GENERAL": [
        # English
        "cough",
        "coughing",
        # Tagalog / Taglish
        "ubo",
        "inuubo",
        "inu-ubo",
        "inuubo ako",
        "nag ubo",
        "nag-ubo",
        "may ubo",
        # Bisaya
        "gi ubo",
        "gi-ubo",
        "g-ubo",
        "gubo",
        "ubo ko",
    ],
    "FEVER": [
        # English
        "fever",
        "high fever",
        # Tagalog
        "lagnat",
        "may lagnat",
        "nilalagnat",
        "nilalagnat ako",
        "mainit ang katawan",
        # Bisaya
        "hilanat",
        "gihilanat",
        "ginahilanat",
        "naay hilanat",
    ],
    # Optional: you can add more symptoms later (examples below)
    "SORE_THROAT": [
        "sore throat",
        "throat pain",
        "masakit lalamunan",
        "sakit lalamunan",
        "masakit tutunlan",  # common Bisaya word for throat
        "sakit tutunlan",
    ],
    "RUNNY_NOSE": [
        "runny nose",
        "sipon",
        "may sipon",
        "tumutulo ilong",
        "nagatulo ilong",
    ],
}


def _extract_cough_type(normalized_text: str) -> List[str]:
    """Return cough intent(s) based on qualifiers.

    Why we need this:
    - "walay plema" contains the word "plema".
      A naive matcher might classify it as PRODUCTIVE.
    - We solve it using explicit DRY (negative) phrases.

    Returns:
        [] if no cough mentioned
        ['COUGH_DRY'] or ['COUGH_PRODUCTIVE']
        ['COUGH_GENERAL'] if cough exists but no qualifier
    """

    cough_present = _phrase_in_text(normalized_text, "cough") or _phrase_in_text(normalized_text, "ubo")
    if not cough_present:
        # Also handle common cough verbs without the literal 'cough'
        cough_present = any(
            _phrase_in_text(normalized_text, _normalize(p))
            for p in (
                "coughing",
                "inuubo",
                "gi ubo",
                "gi-ubo",
            )
        )
    if not cough_present:
        return []

    dry_qualifiers = [
        # English
        "dry cough",
        "no phlegm",
        "without phlegm",
        "no plema",
        "without plema",
        # Tagalog
        "walang plema",
        "tuyong ubo",
        # Bisaya
        "walay plema",
        "uga nga ubo",
    ]
    wet_qualifiers = [
        # English
        "wet cough",
        "productive cough",
        "cough with phlegm",
        "cough with mucus",
        "chest congestion",
        # Tagalog / Taglish
        "may plema",
        "basang ubo",
        "ubo na may plema",
        # Bisaya / Conyo
        "naay plema",
        "ubo na naay plema",
        "basa nga ubo",
        "with plema",
        "halak",
        "hubak",
    ]

    is_dry = any(_phrase_in_text(normalized_text, _normalize(p)) for p in dry_qualifiers)
    is_wet = any(_phrase_in_text(normalized_text, _normalize(p)) for p in wet_qualifiers)

    # Priority: explicit DRY phrases win over WET.
    if is_dry:
        return ["COUGH_DRY"]
    if is_wet:
        return ["COUGH_PRODUCTIVE"]
    return ["COUGH_GENERAL"]


# ---------------------------------------------------------------------------
# 2) NORMALIZATION + MATCHING LOGIC
# ---------------------------------------------------------------------------

def _normalize(text: str) -> str:
    """Normalize text for consistent phrase matching.

    - Lowercase
    - Replace punctuation with spaces
    - Collapse repeated whitespace

    We keep it simple and deterministic so it's easy to explain.
    """

    text = (text or "").lower().strip()
    # Replace any non-letter/digit characters with spaces.
    # This helps match phrases even if the user typed punctuation.
    text = re.sub(r"[^a-z0-9ñ\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _phrase_in_text(normalized_text: str, normalized_phrase: str) -> bool:
    """Check if a phrase exists in the text.

    - Multi-word phrases: substring match is fine.
    - Single-word keywords: use word boundaries to avoid false hits.
      Example: avoid matching 'ubo' inside 'tubo'.
    """

    if not normalized_phrase:
        return False

    if " " in normalized_phrase:
        return normalized_phrase in normalized_text

    # Single token: enforce word boundary.
    return re.search(rf"\b{re.escape(normalized_phrase)}\b", normalized_text) is not None


def extract_symptoms(user_input: str) -> List[str]:
    """Extract a distinct list of symptom labels from a mixed-language sentence.

    Steps:
    1) Normalize input
    2) Iterate over dictionary: symptom -> phrases
    3) If any phrase matches, add symptom

    Returns:
        A list like ['HEADACHE', 'COUGH']

    Important property:
    - Overlaps are naturally handled: the function keeps scanning and can return
      multiple symptoms from the same sentence.
    """

    normalized_text = _normalize(user_input)

    detected: List[str] = []

    # Special handling for cough type (productive vs dry vs general)
    detected.extend(_extract_cough_type(normalized_text))

    # Remaining symptoms via dictionary scan (skip cough labels because we already decided them)
    cough_labels = {"COUGH_PRODUCTIVE", "COUGH_DRY", "COUGH_GENERAL"}
    for symptom_label, phrases in SYMPTOM_DICTIONARY.items():
        if symptom_label in cough_labels:
            continue
        for phrase in phrases:
            normalized_phrase = _normalize(phrase)
            if _phrase_in_text(normalized_text, normalized_phrase):
                detected.append(symptom_label)
                break  # stop checking more phrases for this symptom

    # Distinct list (preserve dictionary order). Since Python 3.7+, dict preserves insertion order.
    return list(dict.fromkeys(detected))


# ---------------------------------------------------------------------------
# 4) TEST CASES (proof it works)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        "Gi ubo ko unya labad akong ulo",  # Bisaya
        "Medyo inuubo ako tapos masakit head ko",  # Conyo/Taglish
        "I have a fever and dry cough",  # English
        "ubo na naay plema",
        "cough without plema",
    ]

    for t in tests:
        print("INPUT:", t)
        print("DETECTED:", extract_symptoms(t))
        print("-" * 50)
