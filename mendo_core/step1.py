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
        "splitting headache",
        # Tagalog / Taglish
        "sakit ulo",
        "masakit ulo",
        "masakit ang ulo",
        "sumasakit ulo",
        "labad ulo",
        "kirot ulo",
        "masakit head",
        "sakit head",
        "binibiyak",
        "binibiyak ang ulo",
        "binibiyak ang ulo ko",
        "sasabog ang ulo",
        "sasabog ulo",
        "parang sasabog ulo",
        "parang sasabog ang ulo",
        "pumapasabog ulo",
        # Bisaya
        "labad akong ulo",
        "sakit akong ulo",
        "sakit ako'g ulo",
        # Common Bisaya typo/shorthand: uwo = ulo, labd = labad
        "labad akong uwo",
        "labd akong ulo",
        "labd akong uwo",
        "sakit akong uwo",
        "gasakit akong ulo",
        "ga sakit akong ulo",
        "murag gasakit akong ulo",
        "murag sakit akong ulo",
        "gibukbok",
        "gibukbok akong ulo",
        # Alternative phrasings
        "tumitibok",
        "tumitibok ang ulo",
        "kumikislot",
        "kumikislot ang ulo",
        "migraine",
        "humahapdi ang ulo",
        "sumasakit ang ulo",
        "sumasakit ang ulo ko",
        "sumasakit ulo",
        "pinupukpok ang bumbunan",
        "sumasakit ang bumbunan",
        "bumbunan ko",
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
        "kumakalansing sa dibdib",
        "kumakalansing ang dibdib",
        "may kumakalansing sa dibdib",
        "rattling in the chest",
        "chest rattling",
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
        # Bisaya
        "uga nga ubo",
        "walay plema",
        "makatol ang tutunlan",
        "makatol akong tutunlan",
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
        "umuubo",
        "umuubo ako",
        # Bisaya
        "gi ubo",
        "gi-ubo",
        "g-ubo",
        "gubo",
        "ubo ko",
        "giubo",
        "ga ubo",
        "ga-ubo",
        "naubo",
        "nag-ubo ko",
        "kakaubo",
        "kakaubo ko",
        # Common shorthand
        "sige ubo",
        "cge ubo",
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
        "nililagnat",
        "nililagnat ako",
        "mainit ang katawan",
        "mainit katawan",
        "nag iinit ang katawan",
        "nag-iinit ang katawan",
        "nag iinit ung katawan",
        "uminit ang katawan",
        "uminit ung katawan",
        "init ang katawan",
        "init ung katawan",
        "nanginginig",
        "panginginig",
        "binat",
        "binat ako",
        "binat yata",
        "binat yata ako",
        # Bisaya
        "hilanat",
        "gihilanat",
        "murag gihilanat ko",
        "murag nilalagnat ko",
        "murag ga init akong lawas",
        "gi hilanat",
        "gihinlantan",
        "gi hilantan",
        "ginahilanat",
        "naay hilanat",
        # Bisaya phrasing for "my body feels hot" (common fever description)
        "init akong lawas",
        "init kaayo akong lawas",
        "init kaayo akong lawas ron",
        "init akong lawas ron",
        "init ang lawas",
        "init ang katawan",
        # Bisaya: feeling hot
        "init akong pamati",
        "init kaayo akong pamati",
        # Alternative phrasings
        "ang init ng katawan",
        "ang init ng katawan ko",
        # Forehead-based fever description
        "init ng noo",
        "init ang noo",
        "init ang noo ko",
        "mainit ang noo",
        "mainit ang noo ko",
        "mainit noo",
        "ang init ng noo",
        "ang init ng noo ko",
        # "Feel hot" English phrasing
        "feel hot",
        "feeling hot",
        "i feel hot",
        "feverish",
        "i feel feverish",
        # Bisaya: general heat phrasing
        "nag init",
        "nag-init",
        "ga init",
        "ga-init",
    ],
    "BODY_ACHES": [
        # English
        "body aches",
        "body ache",
        "body pain",
        "body hurts",
        "my body hurts",
        "my body is aching",
        "body is aching",
        "muscle pain",
        "muscle aches",
        "joint pain",
        "chills",
        "nilalamig",
        "nilalamig ako",
        "nilalamig ngayon",
        "aching all over",
        "whole body aches",
        "entire body aches",
        # Tagalog
        "masakit katawan",
        "sakit katawan",
        "katawan ko masakit",
        "sumasakit ang katawan",
        "sumasakit katawan",
        "sumasakit ang katawan ko",
        "ngalay",
        "nanlalambot",
        "binugbog",
        "parang binugbog",
        "binugbog yung katawan",
        "binugbog ang katawan",
        "masakit ang katawan",
        "sakit ng katawan",
        "lahat ng katawan",
        "lahat ng katawan ko masakit",
        "buong katawan",
        "buong katawan ko masakit",
        # Bisaya
        "sakit lawas",
        "gasakit akong lawas",
        "ga sakit akong lawas",
        "murag gasakit akong lawas",
        "bug at akong lawas",
        "bug at kaayo akong lawas",
        "tibuok lawas nako bug at",
        "tibuok lawas bug at",
        "luya",
        "kapoy kaayo",
        "sakit tibuok lawas",
        "tibuok lawas sakit",
        # Alternative phrasings
        "parang pinukpok",
        "nanlalamig",
        "giniginaw",
        "feel very warm",
        # Fatigue / weakness phrasing
        "nanghihina",
        "nanghihina ako",
        "nanghina",
        "mahina ang katawan",
        "pagod",
        "pagod na pagod",
        "pagod na pagod ako",
        "pagod kaayo",
        # Dizziness as body symptom
        "nahihilo",
        "nahihilo ako",
        "nahilo",
        "dizzy",
        "hilo",
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
        "masakit ang lalamunan ko",
        "masakit ang lalamunan",
        "masakit na ang lalamunan",
        "masakit lalamunan",
        "sumasakit ang lalamunan ko",
        "sumasakit ang lalamunan",
        "sumasakit lalamunan",
        "masakit ang tutunlan",
        "masakit tutunlan",
        "sakit ng lalamunan",
        "sakit sa lalamunan",
        "sakit ng tutunlan",
        "sakit sa tutunlan",
        # Bisaya/Tagalog: can't swallow
        "di katulon",
        "di ako katulon",
        "di ko katulon",
        "dili katulon",
        "dili ko katulon",
        "gasakit akong tutunlan",
        "ga sakit akong tutunlan",
        "murag gasakit akong tutunlan",
        "garas akong tilaok",
        "garas ang tilaok",
        "tilaok",
        # Additional
        "swollen throat",
        "sakit sa liog",
        "pangangati ng lalamunan",
        "makati sa lalamunan",
        # Alternative phrasings
        "paos",
        "mahapdi ang lalamunan",
        "mahapdi lalamunan",
        "my throat hurts",
        "throat hurts",
        # Creative/metaphorical
        "parang may bola sa lalamunan",
        "parang may tinik sa lalamunan",
    ],
    "RUNNY_NOSE": [
        "runny nose",
        "sipon",
        "may sipon",
        "may sipon ako",
        "sisipon",
        "sinisipon",
        "sinasipon",
        "tumutulo ilong",
        "nagatulo ilong",
        "nag sipon",
        "nag-sipon",
        "nag sipon ako",
        # Bisaya
        "gatusok ang sipon",
        "nagatulo akong ilong",
        "nag tulo akong ilong",
        "ga tulo akong ilong",
        "tulo akong ilong",
        "kasimhot",
        "simhot",
        "nagsisimhot",
        "ga simhot",
    ],
    "ALLERGIC_RHINITIS": [
        # English
        "allergy",
        "allergic",
        "allergic rhinitis",
        "hay fever",
        "sneezing",
        "itchy nose",
        "itchy eyes",
        # Tagalog
        "allergy",
        "bahing",
        "makati ilong",
        "makati mata",
        # Bisaya
        "allergy",
        "bahing",
        "katol ilong",
        "katol mata",
        # Alternative phrasings
        "nag aalerdyi",
        "alerdyi",
        # (Keep rhinitis focused on nose/eyes + sneezing)
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
        # Alternative phrasings
        "namumula ang balat",
        "makati ang balat",
    ],
    "STOMACH_ACHE": [
        # English
        "stomach ache",
        "stomach pain",
        "stomachache",
        "tummy ache",
        "abdominal pain",
        "stomach hurts",
        "my stomach hurts",
        "stomach cramps",
        "indigestion",
        "bloated",
        "bloating",
        "my stomach is bloated",
        # Tagalog
        "sakit tiyan",
        "sakit ng tiyan",
        "sakit sa tiyan",
        "masakit tiyan",
        "masakit ang tiyan",
        "masakit ang tiyan ko",
        "sumasakit ang tiyan",
        "sumasakit ang tiyan ko",
        "sakit stomach",
        "sakit sa stomach",
        "masakit stomach",
        "kabag",
        "hilab",
        "hilab ng tiyan",
        "sakit sa sikmura",
        "masakit sikmura",
        # Bisaya
        "sakit akong tiyan",
        "gasakit akong tiyan",
        "ga sakit akong tiyan",
        "gisakit akong tiyan",
        "murag gasakit akong tiyan",
        "murag sakit akong tiyan",
        "murag sakit sa tiyan",
        "nisakit akong tiyan",
        "murag nisakit akong tiyan",
        "sakit sa tiyan",
        "sakit tiyan nako",
        # Alternative phrasings
        "buhol buhol",
        "buhol buhol ang tiyan",
        "kumukulo",
        "kumukulo ang tiyan",
        "hyperacidity",
        # Nausea / vomiting expressions
        "nauseous",
        "nausea",
        "nasusuka",
        "nasusuka ako",
        "gustong magsuka",
        "gusto ko magsuka",
        "gusto kong magsuka",
        "parang gusto ko magsuka",
        "nagsusuka",
        "nagsusuka ako",
        # Lower abdomen
        "sakit puson",
        "sakit sa puson",
        "masakit puson",
        "masakit ang puson",
        "masakit ang puson ko",
        "sakit akong puson",
        # Acidic/gastric
        "acidic",
        "maasim",
        "maasim ang tiyan",
        "gastric",
        "heartburn",
        # Creative/metaphorical
        "kinakain ang tiyan",
        "kinakain ang tiyan ko",
        "parang kinakain ang tiyan",
        "kumukurot sa tiyan",
        "kinukurot ang tiyan",
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
        "tinatae",
        "tinatae ako",
        "nagpapataes",
        "nagtatae ako",
        "lbm",
        "malambot na dumi",
        # Bisaya
        "kalibang",
        "nagkalibang",
        "nagkalibanga",
        "kalibanga",
        "nag loose ko",
        "laway ang tae",
        "gi kalibang",
        "gi-kalibang",
        "gikalibang",
        # Alternative phrasings
        "matubig ang dumi",
        "sige cr",
        "loose bowel",
    ],
}

# Condition entities that should be carried into recommendation safety checks.
CONDITION_LABELS: Dict[str, List[str]] = {
    "HYPERTENSION": [
        "hypertension",
        "hypertensive",
        "high blood",
        "highblood",
        "high blood pressure",
        "hbp",
        "alta presyon",
        "mataas na presyon",
        "taas ug presyon",
        "taas ang presyon",
        "taas ug bp",
        "high bp",
        "bp high",
    ],
    "PREGNANCY": [
        "pregnant",
        "pregnancy",
        "buntis",
        "nagbubuntis",
        "nagdadalang tao",
        "dadalang tao",
        "expecting",
        "with child",
    ],
}

# Symptom keywords used to detect "consumed negation":
# If one of these sits between a neg word and a target symptom,
# the negation is consumed by the closer symptom keyword and
# does NOT propagate to the target.
_INTERVENING_SYMPTOM_WORDS = {
    "ubo", "cough", "lagnat", "fever", "sipon", "ulo", "headache",
    "tiyan", "stomach", "katawan", "diarrhea", "pagtatae", "nagtatae",
    "tinatae", "kalibang",
    "rashes", "pantal", "lalamunan", "throat", "balat", "ilong",
    "hilanat", "umuubo", "inuubo", "kakaubo", "nilalagnat", "nililagnat",
    "tutunlan", "butlig", "ngalay", "lawas",
    "nauseous", "nausea", "nasusuka", "nahihilo", "kasimhot", "simhot",
}


def _is_negated(normalized_text: str, normalized_phrase: str) -> bool:
    """Detect simple negation patterns like 'no fever' / 'walang lagnat'.

    Deterministic rule (easy to explain): if a negation word appears within
    0-2 words BEFORE the symptom phrase, treat it as negated.

    Safety: if another known symptom keyword sits between the negation word
    and the target phrase, the negation is "consumed" by that closer keyword
    and does not propagate.  E.g. "hindi pala ubo sipon" — "hindi" negates
    "ubo", not "sipon".

    Each negation word is checked independently (not finditer which skips
    overlapping matches). If ANY negation word reaches the target with no
    consumed intervening symptom, the phrase IS negated.

    This is intentionally simple and not perfect NLP.
    """

    if not normalized_phrase:
        return False

    neg_words = ["no", "not", "without", "wala", "walang", "walay", "waley", "dili", "di", "hindi", "hnd"]

    # Find every negation word position independently
    neg = r"\b(?:" + "|".join(re.escape(w) for w in neg_words) + r")\b"
    phrase_pat = rf"((?:\s+\w+){{0,2}})\s+{re.escape(normalized_phrase)}\b"
    for neg_m in re.finditer(neg, normalized_text):
        after = normalized_text[neg_m.end():]
        follow = re.match(phrase_pat, after)
        if not follow:
            continue
        filler_tokens = follow.group(1).split()
        consumed = any(ft in _INTERVENING_SYMPTOM_WORDS and ft != normalized_phrase
                       for ft in filler_tokens)
        if not consumed:
            return True  # Genuine negation found

    return False  # All matches had consumed negation


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
        r"\b(itchy|scratchy|tickly|makati|makatol)\b(?:\s+\w+){0,3}\s+\b(throat|lalamunan|tutunlan)\b",
        normalized_text,
    ):
        return ["COUGH_DRY"]
    if re.search(r"\b(throat|lalamunan|tutunlan)\b(?:\s+\w+){0,3}\s+\b(itchy|scratchy|tickly|makati|makatol)\b", normalized_text):
        return ["COUGH_DRY"]

    # Chest-congestion/rattle phrases that directly imply productive cough
    # even without the word "ubo/cough".  These are strong enough to stand
    # alone as productive-cough indicators (e.g., "kumakalansing sa dibdib").
    chest_productive_phrases = [
        "kumakalansing sa dibdib",
        "kumakalansing ang dibdib",
        "rattling in the chest",
        "chest rattling",
        "chest congestion",
    ]
    if any(_phrase_in_text(normalized_text, _normalize(p)) for p in chest_productive_phrases):
        return ["COUGH_PRODUCTIVE"]

    cough_present = _phrase_in_text(normalized_text, "cough") or _phrase_in_text(normalized_text, "ubo")
    if not cough_present:
        # Also handle common cough verbs without the literal 'cough'
        cough_present = any(
            _phrase_in_text(normalized_text, _normalize(p))
            for p in (
                "coughing",
                "inuubo",
                "umuubo",
                "gi ubo",
                "gi-ubo",
                "kakaubo",
                "naubo",
                "ga ubo",
                "ga-ubo",
            )
        )
    if not cough_present:
        return []

    # Check for explicit cough negation BEFORE deciding cough type.
    # Examples: "walang ubo", "wala akong ubo", "no cough", "without cough"
    #
    # Important guard: "no plema ... coughing" does NOT mean "no cough".
    # The negation applies to phlegm, not to cough itself.
    cough_neg_matches = re.finditer(
        r"\b(wala|walang|walay|no|not|without|dili|di|hindi|hnd)\b((?:\s+\w+){0,2})\s+\b(ubo|cough|coughing|umuubo|inuubo)\b",
        normalized_text,
    )
    for m in cough_neg_matches:
        filler_tokens = m.group(2).split()
        if any(tok in {"plema", "phlegm", "mucus"} for tok in filler_tokens):
            continue
        return []

    # Guard: "nonproductive" cough should be classified as DRY, not WET.
    # Without this check, the substring "productive cough" inside
    # "nonproductive cough" triggers a false WET classification.
    if re.search(r"\bnon[- ]?productive\b", normalized_text):
        return ["COUGH_DRY"]

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
        "coughing with phlegm",
        "cough with mucus",
        "coughing with mucus",
        "with phlegm",
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
    # Catch common pattern: "wala (namang) plema" even with extra filler words.
    if not is_dry and re.search(r"\bwala(?:\s+\w+){0,2}\s+plema\b", normalized_text):
        is_dry = True
    if not is_dry and re.search(r"\bwalang(?:\s+\w+){0,2}\s+plema\b", normalized_text):
        is_dry = True
    if not is_dry and re.search(r"\bwaley(?:\s+\w+){0,2}\s+plema\b", normalized_text):
        is_dry = True
    if not is_dry and re.search(r"\bwalay(?:\s+\w+){0,2}\s+plema\b", normalized_text):
        is_dry = True
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


def _extract_conditions_from_normalized(normalized_text: str) -> List[str]:
    """Extract condition entities (e.g., hypertension, pregnancy).

    Conditions are independent from symptom labels and are intended for
    contraindication checks in the recommendation stage.
    """

    detected_conditions: List[str] = []
    for condition_label, phrases in CONDITION_LABELS.items():
        for phrase in phrases:
            normalized_phrase = _normalize(phrase)
            if not _phrase_in_text(normalized_text, normalized_phrase):
                continue
            if _is_negated(normalized_text, normalized_phrase):
                continue
            detected_conditions.append(condition_label)
            break

    return list(dict.fromkeys(detected_conditions))


def extract_conditions(user_input: str) -> List[str]:
    """Public helper for Stage 1 condition extraction."""

    normalized_text = _normalize(user_input)
    return _extract_conditions_from_normalized(normalized_text)


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


def _infer_nasal_label(normalized_text: str, detected: List[str], negated_labels: set = None) -> None:
    """Infer nasal label when the user mentions nose/ilong.

    Based on your definitions:
    - RUNNY_NOSE: dripping / "sipon" / "tumutulo".
    - NASAL_CONGESTION: blocked/stuffy / "barado" / hard to breathe through nose.

    If the user just says something vague about the nose (e.g., "weird akong ilong"),
    we default to NASAL_CONGESTION (stuffy/blocked feeling) rather than RUNNY_NOSE.
    
    IMPORTANT: RUNNY_NOSE and NASAL_CONGESTION can co-exist (e.g., "sipon tapos barado ilong").
    Only ALLERGIC_RHINITIS is exclusive with other nasal labels.
    """
    if negated_labels is None:
        negated_labels = set()

    # If ALLERGIC_RHINITIS is already detected, skip
    if "ALLERGIC_RHINITIS" in detected:
        return

    if not re.search(r"\b(ilong|nose)\b", normalized_text):
        return

    # Guard: nosebleed / blood-on-nose should NOT be mapped to colds or congestion.
    # If blood/bleeding is mentioned near the nose, bail out and let higher-level
    # safety / rephrase handling take over rather than recommending cold medicines.
    if (
        re.search(r"\b(blood|dugo|bleed|bleeding)\b", normalized_text)
        and re.search(r"\b(ilong|nose)\b", normalized_text)
    ):
        return

    # Per-cue-group negation detection (avoids blanket early-return which missed
    # cases like "walang allergy pero barado ang ilong" → should detect NASAL_CONGESTION)
    _neg_rx = r"\b(?:wala|walang|walay|waley|no|not|without|dili|di|hindi|hnd)\b"

    def _cue_negated(keyword: str) -> bool:
        """Check if keyword is negated, respecting consumed negation.

        If another symptom keyword sits between the neg word and the target,
        the negation is consumed by that closer symptom (e.g. "hindi ubo sipon"
        — "hindi" negates "ubo", not "sipon").
        Each neg word is checked independently to avoid overlapping-match issues.
        """
        # Check each negation word position independently
        phrase_pat = rf"((?:\s+(?!pero\b|but\b|kaso\b|however\b|though\b)\w+){{0,2}})\s+{re.escape(keyword)}\b"
        for neg_m in re.finditer(_neg_rx, normalized_text):
            after = normalized_text[neg_m.end():]
            follow = re.match(phrase_pat, after)
            if not follow:
                continue
            filler_tokens = follow.group(1).split()
            consumed = any(ft in _INTERVENING_SYMPTOM_WORDS for ft in filler_tokens
                           if ft != keyword)
            if not consumed:
                return True  # Genuine negation
        return False

    allergy_cue_negated = any(_cue_negated(w) for w in ["allergy", "allergic", "bahing", "makati", "katol"])
    runny_cue_negated   = any(_cue_negated(w) for w in ["sipon", "runny", "tumutulo"])
    congestion_cue_negated = any(_cue_negated(w) for w in ["barado", "stuffy", "blocked", "clogged"])

    # If ALL nasal cue groups present are negated, bail out entirely
    all_negated = True
    for group_neg, group_words in [
        (allergy_cue_negated,   ["allergy", "allergic", "bahing", "makati", "katol"]),
        (runny_cue_negated,     ["sipon", "runny", "tumutulo"]),
        (congestion_cue_negated, ["barado", "stuffy", "blocked", "clogged"]),
    ]:
        group_present = any(_phrase_in_text(normalized_text, w) for w in group_words)
        if group_present and not group_neg:
            all_negated = False
            break
    if all_negated and re.search(_neg_rx, normalized_text):
        # Only return early if every mentioned nasal cue is negated
        if any(_phrase_in_text(normalized_text, w) for w in
               ["allergy","allergic","bahing","makati","katol","sipon","runny","tumutulo","barado","stuffy","blocked","clogged"]):
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

    if _has_any(allergy_cues) and not allergy_cue_negated:
        if "ALLERGIC_RHINITIS" not in detected and "ALLERGIC_RHINITIS" not in negated_labels:
            detected.append("ALLERGIC_RHINITIS")
        return  # User is discussing allergy context — don't default to congestion
    
    # Allow RUNNY_NOSE and NASAL_CONGESTION to co-exist
    if _has_any(runny_cues) and not runny_cue_negated and "RUNNY_NOSE" not in detected and "RUNNY_NOSE" not in negated_labels:
        detected.append("RUNNY_NOSE")
    if _has_any(congestion_cues) and not congestion_cue_negated and "NASAL_CONGESTION" not in detected and "NASAL_CONGESTION" not in negated_labels:
        detected.append("NASAL_CONGESTION")
    
    # If neither was detected and nose/ilong was mentioned, default to congestion
    nasal_labels = {"NASAL_CONGESTION", "RUNNY_NOSE", "ALLERGIC_RHINITIS"}
    if not any(l in nasal_labels for l in detected):
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

        head_present = re.search(r"\b(head|ulo|uwlo|uwo|ulu|olo)\b", normalized_text) is not None
        if not head_present:
            # Typo/jejemon rescue: hed->head, olo->ulo, uo->ulo
            head_present = any(
                (len(t) >= 2 and (_levenshtein_within(t, "head", 1) or _levenshtein_within(t, "ulo", 1)))
                for t in tokens
            )

        pain_present = re.search(
            r"\b(sakit|masakit|masaket|sumasakit|gasakit|ga\s+sakit|kasakit|labad|throbbing|pounding|pulsating|kirot|gakurot|gikirot|kabutohon|kabuto|hurt|hurts|ache|aches|sasabog|binibiyak|pumapasabog|grabe|sobra|grabeng|sobrang)\b",
            normalized_text,
        ) is not None
        if not pain_present:
            # Typo/jejemon rescue: skit->sakit, lbd->labad, masaket->masakit
            pain_present = any(
                (len(t) >= 2 and (_levenshtein_within(t, "sakit", 1) or _levenshtein_within(t, "labad", 2) or _levenshtein_within(t, "masakit", 1)))
                for t in tokens
            )

        headache_explicitly_negated = (
            re.search(r"\b(wala|walang|walay|no|not|without|dili|di|hindi|hnd)\b(?:\s+\w+){0,3}\s+\b(headache|ulo|uwlo|uwo|ulu|olo|head)\b", normalized_text)
            is not None
        )
        if head_present and pain_present and not headache_explicitly_negated:
            # Proximity check: head_word and pain_word must be within 5 tokens of each other
            # This prevents "sakit ng ulo... katawan ko" from triggering HEADACHE when pain refers to body
            head_positions = [i for i, t in enumerate(tokens) if re.match(r"^(head|ulo|uwlo|uwo|ulu|olo)$", t)]
            pain_positions = [i for i, t in enumerate(tokens) if re.match(r"^(sakit|masakit|masaket|sumasakit|labad|throbbing|pounding|pulsating|kirot|gakurot|gikirot|kabutohon|kabuto|hurt|hurts|ache|aches|sasabog|binibiyak|pumapasabog|grabe|sobra|grabeng|sobrang)$", t)]
            # Also check for fuzzy-matched head/pain tokens
            for i, t in enumerate(tokens):
                if len(t) >= 2:
                    if i not in [p for p in head_positions]:
                        if _levenshtein_within(t, "head", 1) or _levenshtein_within(t, "ulo", 1):
                            if t not in {"ubo", "ubi", "uno", "uso"}:  # exclude cough and other common words
                                head_positions.append(i)
                    if i not in [p for p in pain_positions]:
                        if _levenshtein_within(t, "sakit", 1) or _levenshtein_within(t, "masakit", 1) or _levenshtein_within(t, "labad", 2):
                            pain_positions.append(i)
            
            if head_positions and pain_positions:
                min_distance = min(abs(h - p) for h in head_positions for p in pain_positions)
                if min_distance <= 5:
                    detected.append("HEADACHE")

    # Remaining symptoms via dictionary scan (skip cough labels because we already decided them)
    cough_labels = {"COUGH_PRODUCTIVE", "COUGH_DRY", "COUGH_GENERAL"}
    negated_labels: set = set()  # Track negated symptoms to prevent fuzzy rescue re-adding
    for symptom_label, phrases in SYMPTOM_DICTIONARY.items():
        if symptom_label in cough_labels:
            continue
        negated_this = False
        matched = False
        for phrase in phrases:
            normalized_phrase = _normalize(phrase)
            if _phrase_in_text(normalized_text, normalized_phrase):
                # Negation handling for ALL symptoms where users say "no X"
                if _is_negated(normalized_text, normalized_phrase):
                    negated_this = True
                    continue
                detected.append(symptom_label)
                matched = True
                break  # stop checking more phrases for this symptom
        if negated_this and not matched:
            negated_labels.add(symptom_label)

    _infer_nasal_label(normalized_text, detected, negated_labels)

    # Proximity-based SORE_THROAT rescue: throat_word near pain_word (reversed word order)
    # Handles "lalamunan ko ang masakit", "tutunlan ko sakit"
    if "SORE_THROAT" not in detected and "SORE_THROAT" not in negated_labels:
        throat_words = re.search(r"\b(lalamunan|tutunlan|throat)\b", normalized_text)
        throat_pain = re.search(r"\b(masakit|masaket|sakit|sumasakit|pain|hurts|sore|hapdi|mahapdi)\b", normalized_text)
        if throat_words and throat_pain:
            # Proximity check: within 5 tokens
            tokens = normalized_text.split()
            tw_pos = [i for i, t in enumerate(tokens) if re.match(r"^(lalamunan|tutunlan|throat)$", t)]
            tp_pos = [i for i, t in enumerate(tokens) if re.match(r"^(masakit|masaket|sakit|sumasakit|pain|hurts|sore|hapdi|mahapdi)$", t)]
            if tw_pos and tp_pos:
                min_dist = min(abs(a - b) for a in tw_pos for b in tp_pos)
                if min_dist <= 5:
                    # Check negation on both throat word AND pain word
                    neg = r"\b(wala|walang|walay|no|not|without|dili|di|hindi|hnd)\b"
                    negated_throat = re.search(
                        rf"{neg}(?:\s+\w+){{0,3}}\s+\b(lalamunan|tutunlan|throat|sore\s+throat)\b",
                        normalized_text
                    )
                    negated_pain = re.search(
                        rf"{neg}(?:\s+\w+){{0,2}}\s+\b(masakit|masaket|sakit|sumasakit|pain|hurts|sore|hapdi)\b",
                        normalized_text
                    )
                    if not negated_throat and not negated_pain:
                        detected.append("SORE_THROAT")

    # Proximity-based NASAL_CONGESTION rescue: "barado" near "ilong/nose" with filler words
    # Handles cases like "barado na rin ilong", "barado pa yung ilong", "barado na ilong"
    if "NASAL_CONGESTION" not in detected and "NASAL_CONGESTION" not in negated_labels:
        congestion_match = (
            re.search(r"\b(barado|bara|stuffy|blocked|clogged)\b(?:\s+\w+){0,3}\s+\b(ilong|nose|nostrils?)\b", normalized_text)
            or re.search(r"\b(ilong|nose|nostrils?)\b(?:\s+\w+){0,3}\s+\b(barado|bara|stuffy|blocked|clogged)\b", normalized_text)
        )
        if congestion_match:
            # Check negation: "walang barado", "wala akong barado"
            neg_check = re.search(
                r"\b(wala|walang|walay|waley|no|not|without|dili|di|hindi|hnd)\b(?:\s+\w+){0,2}\s+\b(barado|bara|stuffy|blocked|clogged)\b",
                normalized_text
            )
            if not neg_check:
                detected.append("NASAL_CONGESTION")

    # Proximity-based RASHES rescue: skin_word + rash_indicator within proximity
    # Handles cases like "pula at makati ng balat ko", "makati ng balat", etc.
    if "RASHES" not in detected and "RASHES" not in negated_labels:
        skin_words = re.findall(r"\b(balat|panit|skin)\b", normalized_text)
        rash_indicators = re.findall(r"\b(pula|makati|katol|itchy|red|namumula|nagpula|namula|pantal|butlig|hives|rash|rashes)\b", normalized_text)
        if skin_words and rash_indicators:
            detected.append("RASHES")

    # Fuzzy rescue for fever typos: e.g., "my lgnat" -> FEVER
    # Also handles vowel-dropped abbreviations like "lgnt" -> lagnat
    if "FEVER" not in detected and "FEVER" not in negated_labels:
        tokens = normalized_text.split()
        if any(
            (len(t) >= 4 and (_levenshtein_within(t, "lagnat", 1) or _levenshtein_within(t, "fever", 1) or _levenshtein_within(t, "hilanat", 1)))
            for t in tokens
        ):
            detected.append("FEVER")
    # Abbreviation rescue for fever: "lgnt" is a common Filipino texting abbreviation
    if "FEVER" not in detected and "FEVER" not in negated_labels:
        tokens = normalized_text.split()
        if any(t in {"lgnt", "lgnat", "lagnt"} for t in tokens):
            detected.append("FEVER")
    # Proximity-based FEVER rescue: "mainit" near "katawan/lawas/body"
    if "FEVER" not in detected and "FEVER" not in negated_labels:
        if re.search(r"\b(mainit|init)\b(?:\s+\w+){0,3}\s+\b(katawan|lawas|body)\b", normalized_text):
            detected.append("FEVER")
        elif re.search(r"\b(katawan|lawas|body)\b(?:\s+\w+){0,3}\s+\b(mainit|init)\b", normalized_text):
            detected.append("FEVER")

    # Allergen-trigger inference: if RASHES is detected and a known allergen
    # trigger is mentioned, also infer ALLERGIC_RHINITIS.  In the MENDO label
    # system, ALLERGIC_RHINITIS is the closest label for general allergy.  This
    # bridges the gap when semantic fallback doesn't fire because dictionary
    # already returned results for rashes.
    if "RASHES" in detected and "ALLERGIC_RHINITIS" not in detected and "ALLERGIC_RHINITIS" not in negated_labels:
        allergen_triggers = ["dust", "alikabok", "pollen", "dander", "pet fur", "pet hair", "amag", "bulak"]
        if any(_phrase_in_text(normalized_text, _normalize(t)) for t in allergen_triggers):
            detected.append("ALLERGIC_RHINITIS")

    # Fuzzy rescue for common Tagalog runny-nose variants/misspellings.
    # Example: "ssinisipown" -> RUNNY_NOSE, "sepun" -> RUNNY_NOSE
    if "RUNNY_NOSE" not in detected and "RUNNY_NOSE" not in negated_labels:
        tokens = normalized_text.split()
        sipon_exclusion = {"ngipon", "ipin", "tooth", "dental", "ngilo", "bag-ang", "pangil"}
        sipon_targets = ["sinisipon", "sinasipon", "sisipon", "sipon"]
        for tok in tokens:
            if len(tok) < 4:
                continue
            if tok in sipon_exclusion:
                continue
            if any(_levenshtein_within(tok, target, max_dist=2) for target in sipon_targets):
                detected.append("RUNNY_NOSE")
                break

    # Fuzzy rescue for cough typos: e.g., "umoubo" -> COUGH
    # Exclusion: "ulo" is Levenshtein-1 from "ubo", so skip it.
    cough_labels_present = {"COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"}
    if not (cough_labels_present & set(detected)):
        tokens = normalized_text.split()
        ulo_exclusion = {"ulo", "ulu", "ole", "olo", "tubo", "ubos", "ubi", "ube", "tuba", "ubod", "uwo", "uwu"}
        for tok in tokens:
            if tok in ulo_exclusion:
                continue
            if len(tok) >= 3 and _levenshtein_within(tok, "ubo", 1):
                detected.extend(_extract_cough_type(normalized_text))
                if not (cough_labels_present & set(detected)):
                    detected.append("COUGH_GENERAL")
                break

    # Fuzzy rescue for diarrhea typos: e.g., "pagtate" -> DIARRHEA
    # Exclusion: "kaninang" contains "kanina" which is close to "kalibang".
    if "DIARRHEA" not in detected and "DIARRHEA" not in negated_labels:
        tokens = normalized_text.split()
        diarrhea_exclusion = {"kaninang", "kanina", "kaninag", "pagmata", "pagmamata"}
        diarrhea_targets = [
            "pagtatae",
            "nagtatae",
            "kalibang",
            "diarrhea",
            "diarreha",
            "diarhea",
            "diarrea",
        ]
        for tok in tokens:
            if tok in diarrhea_exclusion:
                continue
            if len(tok) < 5:
                continue
            if any(_levenshtein_within(tok, target, max_dist=2) for target in diarrhea_targets):
                detected.append("DIARRHEA")
                break

    # Fuzzy rescue for rashes typos: e.g., "pantl" -> RASHES
    if "RASHES" not in detected and "RASHES" not in negated_labels:
        tokens = normalized_text.split()
        rash_targets = ["pantal", "butlig"]
        rash_exclusion = {"ipantal", "pantalon", "pantalan"}  # verbs/unrelated words
        for tok in tokens:
            if tok in rash_exclusion:
                continue
            if len(tok) < 4:
                continue
            if any(_levenshtein_within(tok, target, max_dist=1) for target in rash_targets):
                detected.append("RASHES")
                break

    # Fuzzy rescue for stomach ache typos: e.g., "tyan" -> STOMACH_ACHE
    # Also handles proximity matching: "stomach" near "sakit/masakit/pain/hurts"
    if "STOMACH_ACHE" not in detected and "STOMACH_ACHE" not in negated_labels:
        tokens = normalized_text.split()
        stomach_targets = ["tiyan", "sikmura"]
        for i, tok in enumerate(tokens):
            if len(tok) < 4:
                continue
            if any(_levenshtein_within(tok, target, max_dist=1) for target in stomach_targets):
                # Check if there is a pain word nearby (including common misspelling "masaket")
                if re.search(r"\b(sakit|masakit|masaket|sumasakit|gasakit|ga\s+sakit|gisakit|kasakit|pain|ache|hilab|kabag)\b", normalized_text):
                    detected.append("STOMACH_ACHE")
                    break
    # Proximity-based STOMACH_ACHE rescue: "stomach" near pain words with filler
    # Handles code-switching like "stomach ko ang sakit", "my stomach hurts"
    if "STOMACH_ACHE" not in detected and "STOMACH_ACHE" not in negated_labels:
        if re.search(r"\b(stomach|tummy|abdomen|tiyan|sikmura)\b(?:\s+\w+){0,3}\s+\b(sakit|masakit|masaket|sumasakit|gasakit|ga\s+sakit|gisakit|kasakit|pain|ache|hurt|hurts)\b", normalized_text):
            detected.append("STOMACH_ACHE")
        elif re.search(r"\b(sakit|masakit|masaket|sumasakit|gasakit|ga\s+sakit|gisakit|kasakit|pain|ache|hurt|hurts)\b(?:\s+\w+){0,3}\s+\b(stomach|tummy|abdomen|tiyan|sikmura)\b", normalized_text):
            detected.append("STOMACH_ACHE")

    # Fuzzy rescue for body aches typos: e.g., "ktawan" -> BODY_ACHES
    # Requires a pain word NEAR the body word (within 6 tokens) to avoid
    # false positives like "sakit ng ulo... katawan ko" where pain refers to head
    if "BODY_ACHES" not in detected and "BODY_ACHES" not in negated_labels:
        tokens = normalized_text.split()
        body_targets = ["katawan", "lawas"]
        for i, tok in enumerate(tokens):
            if len(tok) < 5:
                continue
            if any(_levenshtein_within(tok, target, max_dist=1) for target in body_targets):
                # Check for pain word within 6 tokens of the body word
                nearby_tokens = tokens[max(0, i-6):i+7]
                nearby_text = " ".join(nearby_tokens)
                if re.search(r"\b(sakit|masakit|masaket|sumasakit|gasakit|ga\s+sakit|kasakit|pain|ache|ngalay)\b", nearby_text):
                    detected.append("BODY_ACHES")
                    break

    # Strong negation override: if user explicitly says they have NO fever,
    # remove FEVER even if earlier words mention lagnat/feverish.
    # CONTRASTIVE BOUNDARY: "pero"/"but" resets negation scope.
    #
    # Helper: check if ANY negation word directly reaches the target keywords
    # (each neg word checked independently to avoid overlapping-match issues).
    _neg_rx_override = r"\b(?:wala|walang|walay|no|not|without|dili|di|hindi|hnd)\b"

    def _strong_neg_check(part: str, target_words: set, max_filler: int = 2, ignored_filler_words: set | None = None) -> bool:
        """Return True if any target word is genuinely negated in this text part."""
        ignored_filler_words = ignored_filler_words or set()
        target_alt = "|".join(re.escape(w) for w in target_words)
        phrase_pat = rf"((?:\s+\w+){{{0},{max_filler}}})\s+\b(?:{target_alt})\b"
        for neg_m in re.finditer(_neg_rx_override, part):
            after = part[neg_m.end():]
            follow = re.match(phrase_pat, after)
            if not follow:
                continue
            filler_tokens = follow.group(1).split()
            if any(ft in ignored_filler_words for ft in filler_tokens):
                continue
            consumed = any(ft in _INTERVENING_SYMPTOM_WORDS for ft in filler_tokens
                           if ft not in target_words)
            if not consumed:
                return True
        return False

    if "FEVER" in detected:
        parts = re.split(r"\b(pero|but|kaso|however|though)\b", normalized_text)
        fever_negated = False
        _fever_targets = {"fever", "lagnat", "hilanat"}
        for i, part in enumerate(parts):
            has_fever_word = bool(re.search(r"\b(fever|lagnat|hilanat|nilalagnat|nililagnat|hilantan)\b", part))
            has_neg = _strong_neg_check(part, _fever_targets)
            if has_neg and has_fever_word:
                fever_negated = True
            elif has_fever_word and not has_neg:
                fever_negated = False
        if fever_negated:
            detected = [d for d in detected if d != "FEVER"]

    # Strong negation override for COUGH with contrastive boundary
    if any(s in detected for s in cough_labels_present):
        parts = re.split(r"\b(pero|but|kaso|however|though)\b", normalized_text)
        cough_negated = False
        _cough_targets = {"ubo", "cough", "coughing", "umuubo", "inuubo"}
        for i, part in enumerate(parts):
            has_cough_word = bool(re.search(r"\b(ubo|cough|coughing|umuubo|inuubo)\b", part))
            has_neg = _strong_neg_check(part, _cough_targets, ignored_filler_words={"plema", "phlegm", "mucus"})
            if has_neg and has_cough_word:
                cough_negated = True
            elif has_cough_word and not has_neg:
                cough_negated = False
        if cough_negated:
            detected = [d for d in detected if d not in cough_labels_present]

    # Strong negation override for HEADACHE with contrastive boundary
    if "HEADACHE" in detected:
        parts = re.split(r"\b(pero|but|kaso|however|though)\b", normalized_text)
        head_negated = False
        _head_targets = {"headache", "ulo", "head"}
        for i, part in enumerate(parts):
            has_head_word = bool(re.search(r"\b(headache|ulo|head|sakit\s+ulo|labad)\b", part))
            has_neg = _strong_neg_check(part, _head_targets, max_filler=3)
            if has_neg and has_head_word:
                head_negated = True
            elif has_head_word and not has_neg:
                head_negated = False
        if head_negated:
            detected = [d for d in detected if d != "HEADACHE"]

    # Strong negation override for RUNNY_NOSE with contrastive boundary
    if "RUNNY_NOSE" in detected:
        parts = re.split(r"\b(pero|but|kaso|however|though)\b", normalized_text)
        nose_negated = False
        _nose_targets = {"sipon", "runny", "nose"}
        for i, part in enumerate(parts):
            has_nose_word = bool(re.search(r"\b(sipon|runny|nose)\b", part))
            has_neg = _strong_neg_check(part, _nose_targets)
            if has_neg and has_nose_word:
                nose_negated = True
            elif has_nose_word and not has_neg:
                nose_negated = False
        if nose_negated:
            detected = [d for d in detected if d != "RUNNY_NOSE"]

    # Strong negation override for BODY_ACHES with contrastive boundary
    if "BODY_ACHES" in detected:
        parts = re.split(r"\b(pero|but|kaso|however|though)\b", normalized_text)
        body_negated = False
        for i, part in enumerate(parts):
            has_body_word = bool(re.search(r"\b(katawan|body|lawas|muscle)\b", part))
            has_neg = bool(
                re.search(r"\b(wala|walang|walay|no|not|without|dili|di|hindi|hnd)\b(?:\s+\w+){0,2}\s+\b(sakit|masakit|pain|ache)\b(?:\s+\w+){0,2}\s+\b(katawan|body|lawas)\b", part)
            )
            if not has_neg:
                has_neg = bool(
                    re.search(r"\b(wala|walang|walay|no|not|without|dili|di|hindi|hnd)\b(?:\s+\w+){0,3}\s+\b(body\s*ache|katawan|lawas)\b", part)
                )
            if has_neg and has_body_word:
                body_negated = True
            elif has_body_word and not has_neg:
                body_negated = False
        if body_negated:
            detected = [d for d in detected if d != "BODY_ACHES"]

    # Safety cleanup: nosebleed / blood-on-nose must not be interpreted as a cold.
    if (
        re.search(r"\b(blood|dugo|bleed|bleeding)\b", normalized_text)
        and re.search(r"\b(ilong|nose)\b", normalized_text)
    ):
        detected = [
            d for d in detected
            if d not in {"RUNNY_NOSE", "NASAL_CONGESTION", "ALLERGIC_RHINITIS"}
        ]

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
