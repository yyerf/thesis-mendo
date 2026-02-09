"""step1.py

Phrase-Based Symptom Extraction (Deterministic / Dictionary-Based)

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
        "splitting headache",
        "head is pounding",
        # Tagalog / Taglish
        "sakit ulo",
        "sakit ng ulo",
        "masakit ulo",
        "masakit ang ulo",
        "masakit ang ulo ko",
        "masakit ulo ko",
        "sumasakit ulo",
        "sumasakit ang ulo",
        "sumakit ulo",
        "sumakit ang ulo",
        "sumakit ulo ko",
        "labad ulo",
        "kirot ulo",
        "masakit head",
        "sakit head",
        "binibiyak",
        "binibiyak ang ulo",
        "binibiyak ang ulo ko",
        "may headache",
        # Bisaya
        "labad akong ulo",
        "sakit akong ulo",
        "sakit ako'g ulo",
        "gibukbok",
        "gibukbok akong ulo",
        "sakit sa ulo",
        # Toothache (treated as pain)
        "sakit ng ngipin",
        "sakit ngipin",
        "masakit ngipin",
        "toothache",
        "tooth pain",
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
        "phlegm in chest",
        # Tagalog / Taglish
        "may plema",
        "my plema",
        "basang ubo",
        "malapot na plema",
        "ubo na may plema",
        "hirap ilabas yung plema",
        "hirap ilabas ang plema",
        "plema sa dibdib",
        # Bisaya / Conyo
        "naay plema",
        "basa nga ubo",
        "ubo na naay plema",
        "with plema",
        "halak",
        "hubak",
        "plema sa dughan",
        "pure phlegm",
        "pure plema",
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
        "makati ang lalamunan",
        "makati ang lalamunan ko",
        "kati ng lalamunan",
        "kati lalamunan",
        "kati ang lalamunan",
        "makati ang lalamunan ko tapos ubo",
        # Bisaya
        "uga nga ubo",
        "walay plema",
        "makatol ang tutunlan",
        "makatol akong tutunlan",
        "katol sa tutunlan",
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
        # Common shorthand
        "sige ubo",
        "cge ubo",
    ],
    "FEVER": [
        # English
        "fever",
        "high fever",
        "feverish",
        # Tagalog
        "lagnat",
        "may lagnat",
        "nilalagnat",
        "nilalagnat ako",
        "mainit ang katawan",
        "mainit katawan",
        "mainit lang ang katawan",
        "mainit ang katawan ko",
        "nanginginig",
        "panginginig",
        "binat",
        "binat ako",
        "binat yata",
        "binat yata ako",
        "sinat",
        "sinat lang",
        "may sinat",
        "trangkaso",
        # Bisaya
        "hilanat",
        "gihilanat",
        "ginahilanat",
        "naay hilanat",
        "kalintura",
        # Bisaya phrasing for "my body feels hot" (common fever description)
        "init akong lawas",
        "init kaayo akong lawas",
        "init kaayo akong lawas ron",
        "init akong lawas ron",
        # Bisaya: feeling hot
        "init akong pamati",
        "init kaayo akong pamati",
    ],
    "BODY_ACHES": [
        # English
        "body aches",
        "body ache",
        "body pain",
        "muscle pain",
        "muscle aches",
        "joint pain",
        "back pain",
        "chills",
        "nilalamig",
        "nilalamig ako",
        "nilalamig ngayon",
        # Tagalog
        "masakit katawan",
        "sakit katawan",
        "katawan ko masakit",
        "sakit ng katawan",
        "masakit ang katawan",
        "katawan lang ang masakit",
        "ngalay",
        "nanlalambot",
        "binugbog",
        "parang binugbog",
        "binugbog yung katawan",
        "binugbog ang katawan",
        "sakit tibuok lawas",
        "mabigat ang katawan",
        "mabigat katawan",
        "mabigat ang pakiramdam",
        # Bisaya
        "sakit lawas",
        "sakit sa lawas",
        "sakit tibuok lawas",
        "luya",
        "kapoy kaayo",
        "panuhot",
        "panuhot sa likod",
        "sakit sa likod",
        "bug-at akong lawas",
        "bug-at ang lawas",
    ],
    "NASAL_CONGESTION": [
        # English
        "nasal congestion",
        "stuffy nose",
        "blocked nose",
        "clogged nose",
        # Tagalog
        "barado ilong",
        "barado ang ilong",
        "sipon na barado",
        # Bisaya
        "barado ilong",
        "bara ang ilong",
        "lisod ginhawa sa ilong",
        "stuffy akong ilong",
    ],
    # Optional: you can add more symptoms later (examples below)
    "SORE_THROAT": [
        "sore throat",
        "throat pain",
        "masakit lalamunan",
        "sakit lalamunan",
        "masakit tutunlan",  # common Bisaya word for throat
        "sakit tutunlan",
        # Bisaya/Tagalog: can't swallow
        "di katulon",
        "di ako katulon",
        "di ko katulon",
        "dili katulon",
        "dili ko katulon",
    ],
    "RUNNY_NOSE": [
        "runny nose",
        "running nose",
        "sipon",
        "may sipon",
        "sisipon",
        "sinisipon",
        "sinasipon",
        "sinisipon me",
        "tumutulo ilong",
        "nagatulo ilong",
        # Bisaya
        "gatusok ang sipon",
        "nagatulo akong ilong",
        "sip-on",
        "gisip-on",
        "gisipon",
        "gi sip-on",
        "naay sip-on",
    ],
    "ALLERGIC_RHINITIS": [
        # English
        "allergy",
        "allergic rhinitis",
        "hay fever",
        "sneezing",
        "sneezing all day",
        "itchy nose",
        "itchy eyes",
        # Tagalog
        "bahing",
        "makati ilong",
        "makati mata",
        "makati ang mata",
        "makati ang ilong",
        "allergy rashes",
        "allergy sa balat",
        "allergy sa panit",
        # Bisaya
        "katol ilong",
        "katol mata",
        # (Keep rhinitis focused on nose/eyes + sneezing)
        # NOTE: 'allergic' alone omitted — triggers false positive with
        # 'allergic ako sa Paracetamol' which means drug allergy, not rhinitis.
    ],
    "RASHES": [
        # English
        "rash",
        "rashes",
        "skin rash",
        "itchy skin",
        "itching skin",
        "my skin is itchy",
        "my skin is red",
        "hives",
        "urticaria",
        # Tagalog / Taglish
        "pantal",
        "pantal pantal",
        "butlig",
        "butlig butlig",
        "namumula balat",
        # Bisaya
        "pantal",
        "butlig",
        "katol akong panit",
        "makati akong panit",
        # Taglish / Cebuano-English mix
        "katol akong skin",
        "makati akong skin",
        "katol skin",
        "makati skin",
        "katol akong lawas",
        "makati akong lawas",
        "pangangati",
        "nagpula akong panit",
        "namula akong panit",
        "pula akong panit",
        "red akong panit",
        "nagpula akong balat",
    ],
    "STOMACH_ACHE_ACID": [
        # English
        "hyperacidity",
        "acid reflux",
        "heartburn",
        "gas pain",
        "bloated stomach",
        "bloating",
        "acidic stomach",
        "acidic",
        # Tagalog
        "mahapdi",
        "mahapdi ang sikmura",
        "mahapdi sikmura",
        "hapdi",
        "hapdi ng sikmura",
        "hapdi ng tiyan",
        "sikmura",
        "masakit sikmura",
        "sakit sikmura",
        "kabag",
        "ang kabag",
        "grabe ang kabag",
        "masama ang pakiramdam ng tiyan",
        "nag-aacid",
        "sakit tiyan",
        "sakit ng tiyan",
        "sakit tiyan ko",
        "masakit ang tiyan",
        "masakit tiyan",
        "masusuka at sakit tiyan",
        "masusuka",
        # Bisaya
        "aslom",
        "aslom kaayo",
        "aslom akong tiyan",
        "gihiluan",
        "mura kog gihiluan",
        "gasela",
        "sakit sa sikmura",
        "hapdi sa tiyan",
        "hilab",
        "sakit akong tiyan",
    ],
    "DIARRHEA": [
        # English
        "diarrhea",
        "loose stool",
        "watery stool",
        "frequent bowel movements",
        # Tagalog
        "pagtatae",
        "nagtatae",
        "lbm",
        "malambot na dumi",
        "basa akong tae",
        "basa tae",
        # Bisaya
        "kalibang",
        "nagkalibang",
        "gikalibang",
        "gikalibanga",
        "laway ang tae",
        "kalibanga",
    ],
    "NAUSEA": [
        # English
        "nausea",
        "nauseous",
        "feeling like vomiting",
        "about to vomit",
        # Tagalog
        "masusuka",
        "naduduwal",
        "nasusuka",
        "parang masusuka",
        "gusto kong sumuka",
        # Bisaya
        "gustong musuka",
        "susukahon",
    ],
    "DIZZINESS": [
        # English
        "dizzy",
        "dizziness",
        "lightheaded",
        "vertigo",
        # Tagalog
        "nahihilo",
        "hilo",
        "hilong-hilo",
        "lumulutang ang paningin",
        # Bisaya
        "nalipong",
        "lipong",
        "nalipong ra ko",
        "ginalipong",
    ],
}


def _is_negated(normalized_text: str, normalized_phrase: str) -> bool:
    """Detect simple negation patterns like 'no fever' / 'walang lagnat'.

    Deterministic rule (easy to explain): if a negation word appears within
    0-2 words BEFORE the symptom phrase, treat it as negated.

    This is intentionally simple and not perfect NLP.
    """

    if not normalized_phrase:
        return False

    neg_words = [
    # --- ENGLISH ---
    "no", "not", "without", "none", "never", "negative",
    "don't", "dont",          # STT might drop the apostrophe
    "doesn't", "doesnt",
    "didn't", "didnt",
    "free from",              # e.g., "pain-free", "free from ubo"
    
    # --- TAGALOG ---
    "wala", "walang",         # Standard "None"
    "hindi", "di",            # Standard "No"
    "de",                     # Shortcut for "hindi" (e.g., "de naman masakit")
    "dehins",                 # Slang for "hindi" (User: "Dehins masakit")
    "la",                     # Shortcut for "wala" (User: "La naman ako lagnat")
    "ayaw",                   # Refusal/Don't want (Context: "Ayaw ko nyan")
    
    # --- BISAYA (Crucial for Speech) ---
    "walay",                  # Standard "None" (e.g., "Walay hilanat")
    "wa",                     # Short for "Wala" (User: "Wa koy ubo")
    "way",                    # Short for "Walay" (User: "Way labad")
    "dili",                   # Standard "No" (e.g., "Dili sakit")
    "di",                     # Short for "Dili"
    
    # --- CONYO / MIXED / SLANG ---
    "wit",                    # Gay lingo/Slang for "Wala/Hindi"
    "wiz",                    # Variation of "wit"
    "minus",                  # Medical/Math slang (e.g., "Minus the fever")
    "absent",                 # e.g., "Absent ang pain"
    "clear",                  # e.g., "Clear naman sa ubo" (Context dependent)
]

    # Build a small regex window: (neg) (optional word) (optional word) phrase
    # Example: "walang" + "masyadong" + "lagnat" -> still counts as negated
    neg = r"(?:" + "|".join(re.escape(w) for w in neg_words) + r")"
    window = rf"\b{neg}\b(?:\s+\w+){{0,2}}\s+{re.escape(normalized_phrase)}\b"
    return re.search(window, normalized_text) is not None


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

    # Dry cough can be implied by an itchy/tickle throat even if the user
    # doesn't explicitly say "ubo/cough".
    if re.search(
        r"\b(itchy|scratchy|tickly|makati|makatol|kati)\b(?:\s+\w+){0,3}\s+\b(throat|lalamunan|tutunlan)\b",
        normalized_text,
    ):
        return ["COUGH_DRY"]
    if re.search(r"\b(throat|lalamunan|tutunlan)\b(?:\s+\w+){0,3}\s+\b(itchy|scratchy|tickly|makati|makatol|kati)\b", normalized_text):
        return ["COUGH_DRY"]
    # Also handle "kati ng lalamunan" pattern  
    if re.search(r"\bkati\b(?:\s+\w+){0,2}\s+\blalamunan\b", normalized_text):
        return ["COUGH_DRY"]

    # Check for plema-only mentions that imply productive cough even without "ubo/cough"
    plema_only = (
        _phrase_in_text(normalized_text, "plema")
        or _phrase_in_text(normalized_text, "phlegm")
        or re.search(r"\bpure\s+phlegm\b", normalized_text) is not None
        or re.search(r"\bpure\s+plema\b", normalized_text) is not None
    )

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
    
    if not cough_present and not plema_only:
        return []

    # If plema is mentioned without cough word, treat as productive cough
    if not cough_present and plema_only:
        # But check for negation of plema first ("walang plema" is NOT productive)
        plema_negated = (
            re.search(r"\b(wala|walang|walay|waley|no|not|without)\b(?:\s+\w+){0,2}\s+\bplema\b", normalized_text) is not None
        )
        if not plema_negated:
            return ["COUGH_PRODUCTIVE"]
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
        "wala plema",
        "wala akong plema",
        "wala po akong plema",
        "wala namang plema",
        "wala naman plema",
        "wala pa plema",
        "tuyong ubo",
        # Bisaya
        "walay plema",
        "waley plema",
        "wala koy plema",
        "wala ko y plema",
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
        "my plema",
        "maraming plema",
        "madaming plema",
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
    # Catch common pattern: "wala (namang) plema" even with extra filler words.
    if not is_dry and re.search(r"\bwala(?:\s+\w+){0,2}\s+plema\b", normalized_text):
        is_dry = True
    if not is_dry and re.search(r"\bwalang(?:\s+\w+){0,2}\s+plema\b", normalized_text):
        is_dry = True
    if not is_dry and re.search(r"\bwaley(?:\s+\w+){0,2}\s+plema\b", normalized_text):
        is_dry = True
    if not is_dry and re.search(r"\bwalay(?:\s+\w+){0,2}\s+plema\b", normalized_text):
        is_dry = True
    
    # Check if "dry cough" is being NEGATED: "not dry cough" / "hindi dry cough"
    dry_negated = (
        re.search(r"\b(not|no|hindi|di|dili|wala|walang)\b(?:\s+\w+){0,1}\s+\bdry\s+cough\b", normalized_text) is not None
        or re.search(r"\b(not|no|hindi|di|dili|wala|walang)\b(?:\s+\w+){0,1}\s+\bdry\b", normalized_text) is not None
        or re.search(r"\b(not|no|hindi|di|dili|wala|walang)\b(?:\s+\w+){0,1}\s+\btuyong?\b", normalized_text) is not None
    )
    if dry_negated:
        is_dry = False
    
    is_wet = any(_phrase_in_text(normalized_text, _normalize(p)) for p in wet_qualifiers)
    
    # Also check for "wet siya" / "basa siya" patterns implying productive
    if not is_wet and re.search(r"\b(wet|basa|basang)\b(?:\s+\w+){0,2}\s*\b(siya|cough|ubo)?\b", normalized_text):
        if re.search(r"\b(wet|basa)\b", normalized_text):
            is_wet = True

    # If dry was explicitly negated, favor wet
    if dry_negated and not is_wet:
        # "not dry cough" without explicit wet qualifier -> assume wet
        is_wet = True

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

    # De-jejemize / leetspeak normalization (deterministic, no training needed)
    # Examples: s@k1t ul0 -> sakit ulo
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


def _levenshtein_within(a: str, b: str, max_dist: int) -> bool:
    """Return True if edit distance(a, b) <= max_dist.

    Used sparingly for common noisy user typos (e.g., ssinisipown -> sinisipon).
    Implements an early-exit DP to stay fast.
    """

    if a == b:
        return True
    if max_dist < 0:
        return False

    la, lb = len(a), len(b)
    if abs(la - lb) > max_dist:
        return False

    # Ensure b is the longer one
    if la > lb:
        a, b = b, a
        la, lb = lb, la

    prev = list(range(lb + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * lb
        row_min = cur[0]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur[j] = min(
                prev[j] + 1,       # deletion
                cur[j - 1] + 1,    # insertion
                prev[j - 1] + cost # substitution
            )
            if cur[j] < row_min:
                row_min = cur[j]
        if row_min > max_dist:
            return False
        prev = cur

    return prev[lb] <= max_dist


def _infer_nasal_label(normalized_text: str, detected: List[str]) -> None:
    """Infer nasal label when the user mentions nose/ilong.

    Based on your definitions:
    - RUNNY_NOSE: dripping / "sipon" / "tumutulo".
    - NASAL_CONGESTION: blocked/stuffy / "barado" / hard to breathe through nose.

    If the user just says something vague about the nose (e.g., "weird akong ilong"),
    we default to NASAL_CONGESTION (stuffy/blocked feeling) rather than RUNNY_NOSE.
    """

    nasal_labels = {"NASAL_CONGESTION", "RUNNY_NOSE", "ALLERGIC_RHINITIS"}
    if any(l in nasal_labels for l in detected):
        return

    if not re.search(r"\b(ilong|nose)\b", normalized_text):
        return

    runny_cues = [
        "sipon",
        "runny",
        "running",
        "tumutulo",
        "nagatulo",
        "drip",
        "dripping",
        "tulo",
    ]
    congestion_cues = [
        "barado",
        "bara",
        "stuffy",
        "blocked",
        "clogged",
        "congestion",
        "lisod ginhawa",
        "hard to breathe",
    ]
    allergy_cues = [
        "makati",
        "katol",
        "bahing",
        "sneeze",
        "sneezing",
        "allergy",
        "allergic",
    ]

    def _has_any(cues: List[str]) -> bool:
        return any(_phrase_in_text(normalized_text, _normalize(c)) for c in cues)

    if _has_any(allergy_cues):
        detected.append("ALLERGIC_RHINITIS")
        return
    if _has_any(runny_cues):
        detected.append("RUNNY_NOSE")
        return
    if _has_any(congestion_cues):
        detected.append("NASAL_CONGESTION")
        return

    detected.append("NASAL_CONGESTION")


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

    # Headache heuristic: allow mixed-language phrasing like "sakit my ulo" or "head is labad".
    # This improves recall without training.
    if "HEADACHE" not in detected:
        tokens = normalized_text.split()

        head_present = re.search(r"\b(head|ulo)\b", normalized_text) is not None
        if not head_present:
            # Typo/jejemon rescue: hed->head, olo->ulo
            head_present = any(
                (len(t) >= 3 and (_levenshtein_within(t, "head", 1) or _levenshtein_within(t, "ulo", 1)))
                for t in tokens
            )

        pain_present = re.search(
            r"\b(sakit|masakit|sumakit|sumasakit|labad|throbbing|pounding|pulsating|kirot|hurt|hurts|hirts|ache|aches)\b",
            normalized_text,
        ) is not None
        if not pain_present:
            # Typo/jejemon rescue: skit->sakit, lbd->labad, hirts->hurts
            pain_present = any(
                (len(t) >= 3 and (
                    _levenshtein_within(t, "sakit", 1)
                    or _levenshtein_within(t, "labad", 2)
                    or _levenshtein_within(t, "hurts", 1)
                ))
                for t in tokens
            )

        headache_explicitly_negated = (
            re.search(r"\b(wala|walang|walay|no|not|without|dili|di)\b(?:\s+\w+){0,3}\s+\b(headache|ulo|head)\b", normalized_text)
            is not None
        )
        if head_present and pain_present and not headache_explicitly_negated:
            detected.append("HEADACHE")

    # Remaining symptoms via dictionary scan (skip cough labels because we already decided them)
    cough_labels = {"COUGH_PRODUCTIVE", "COUGH_DRY", "COUGH_GENERAL"}
    for symptom_label, phrases in SYMPTOM_DICTIONARY.items():
        if symptom_label in cough_labels:
            continue
        for phrase in phrases:
            normalized_phrase = _normalize(phrase)
            if _phrase_in_text(normalized_text, normalized_phrase):
                # Negation handling for key symptoms where users say "no X"
                if symptom_label in {"FEVER", "HEADACHE", "DIARRHEA", "STOMACH_ACHE", "STOMACH_ACHE_ACID", "RUNNY_NOSE"} and _is_negated(normalized_text, normalized_phrase):
                    continue
                detected.append(symptom_label)
                break  # stop checking more phrases for this symptom

    # Merge STOMACH_ACHE_ACID into STOMACH_ACHE for downstream compatibility
    if "STOMACH_ACHE_ACID" in detected:
        detected = [d if d != "STOMACH_ACHE_ACID" else "STOMACH_ACHE" for d in detected]

    _infer_nasal_label(normalized_text, detected)

    # Fuzzy rescue for fever typos: e.g., "my lgnat" -> FEVER
    if "FEVER" not in detected:
        tokens = normalized_text.split()
        if any(
            (len(t) >= 4 and (_levenshtein_within(t, "lagnat", 1) or _levenshtein_within(t, "fever", 1) or _levenshtein_within(t, "hilanat", 1)))
            for t in tokens
        ):
            detected.append("FEVER")

    # Fuzzy rescue for common Tagalog runny-nose variants/misspellings.
    # Example: "ssinisipown" -> RUNNY_NOSE
    if "RUNNY_NOSE" not in detected:
        tokens = normalized_text.split()
        sipon_targets = ["sinisipon", "sinasipon", "sisipon"]
        for tok in tokens:
            if len(tok) < 5:
                continue
            if any(_levenshtein_within(tok, target, max_dist=2) for target in sipon_targets):
                detected.append("RUNNY_NOSE")
                break

    # Strong negation override: if user explicitly says they have NO fever,
    # remove FEVER even if earlier words mention lagnat/feverish.
    if "FEVER" in detected:
        fever_negated = (
            _is_negated(normalized_text, _normalize("fever"))
            or _is_negated(normalized_text, _normalize("lagnat"))
            or re.search(r"\b(wala|walang|walay|no|not|without|dili|di)\b(?:\s+\w+){0,2}\s+\bfever\b", normalized_text)
            or re.search(r"\b(wala|walang|walay|no|not|without|dili|di)\b(?:\s+\w+){0,2}\s+\blagnat\b", normalized_text)
        )
        if fever_negated:
            detected = [d for d in detected if d != "FEVER"]

    # Cough negation: \"wala akong ubo\" / \"no cough\" / \"dili ubo\"
    # But NOT "not dry cough" (that negates "dry", not "cough")
    for cough_label in ["COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"]:
        if cough_label in detected:
            # Only negate cough if it's a standalone negation of cough itself
            # e.g., "wala akong ubo" / "no cough" but NOT "not dry cough"
            cough_negated_ubo = _is_negated(normalized_text, _normalize("ubo"))
            cough_negated_eng = (
                re.search(r"\b(no|not|without|wala|walang|walay|dili|di)\b\s+\bcough\b", normalized_text) is not None
                and not re.search(r"\b(no|not|without)\b\s+\b(dry|wet|productive)\b\s+\bcough\b", normalized_text)
            )
            if cough_negated_ubo or cough_negated_eng:
                detected = [d for d in detected if d not in {"COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"}]
                break

    # Sipon/runny nose negation: "walang sipon"
    if "RUNNY_NOSE" in detected:
        sipon_negated = (
            _is_negated(normalized_text, _normalize("sipon"))
            or _is_negated(normalized_text, _normalize("runny nose"))
            or _is_negated(normalized_text, _normalize("sip-on"))
            or re.search(r"\b(wala|walang|walay|no|not|without|dili|di)\b(?:\s+\w+){0,2}\s+\bsipon\b", normalized_text)
        )
        if sipon_negated:
            detected = [d for d in detected if d != "RUNNY_NOSE"]

    # Stomach negation: "dili sakit akong tiyan" / "walang sakit tiyan"
    if "STOMACH_ACHE" in detected:
        stomach_negated = (
            _is_negated(normalized_text, _normalize("tiyan"))
            or _is_negated(normalized_text, _normalize("sikmura"))
            or _is_negated(normalized_text, _normalize("stomach"))
            or re.search(r"\b(wala|walang|walay|dili|di|no|not)\b(?:\s+\w+){0,3}\s+\b(tiyan|sikmura|stomach)\b", normalized_text)
        )
        if stomach_negated:
            detected = [d for d in detected if d != "STOMACH_ACHE"]

    # Headache negation override
    if "HEADACHE" in detected:
        headache_negated = (
            re.search(r"\b(wala|walang|walay|no|not|without|dili|di)\b(?:\s+\w+){0,3}\s+\b(headache|ulo|head|sakit\s+ulo|masakit\s+ulo)\b", normalized_text)
            is not None
            or _is_negated(normalized_text, _normalize("ulo"))
            or re.search(r"\b(di|dili)\s+(naman\s+)?masakit\s+ulo\b", normalized_text) is not None
        )
        if headache_negated:
            detected = [d for d in detected if d != "HEADACHE"]

    # ── Drug-Mention Inference ──
    # When user mentions a brand name but no explicit symptom, infer the symptom
    # from the drug's known use. This handles cases like:
    #   "Buntis ako, pwede ba uminom ng Advil?" -> HEADACHE/pain implied
    #   "Highblood ako, bawal ako sa Neozep diba?" -> NASAL_CONGESTION/cold implied
    if not detected:
        drug_symptom_map = {
            "advil":     "HEADACHE",
            "ibuprofen": "HEADACHE",
            "biogesic":  "HEADACHE",
            "mefenamic": "HEADACHE",
            "neozep":    "NASAL_CONGESTION",
            "decolgen":  "NASAL_CONGESTION",
            "sinutab":   "NASAL_CONGESTION",
            "bioflu":    "FEVER",
            "solmux":    "COUGH_PRODUCTIVE",
            "ascof":     "COUGH_PRODUCTIVE",
            "tuseran":   "COUGH_DRY",
            "sinecod":   "COUGH_DRY",
            "kremil":    "STOMACH_ACHE",
            "diatabs":   "DIARRHEA",
            "loperamide":"DIARRHEA",
            "cetirizine":"ALLERGIC_RHINITIS",
            "claritin":  "ALLERGIC_RHINITIS",
            "allerta":   "ALLERGIC_RHINITIS",
            "benadryl":  "ALLERGIC_RHINITIS",
        }
        for drug, symptom in drug_symptom_map.items():
            if re.search(rf"\b{re.escape(drug)}\b", normalized_text):
                detected.append(symptom)
                break  # one drug inference is enough

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
