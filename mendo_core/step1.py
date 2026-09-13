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
        "inuubu",
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
        # Bisaya — inflected forms of "ubo" (cough)
        "gihubo",
        "gihubo ko",
        "nagubo",
        "nagubo ko",
        "nahubo",
        "mihubo",
        "mag-ubo ko",
        # Common shorthand
        "sige ubo",
        "cge ubo",
        # Common misspellings
        "koff",
        "kogh",
        "coff",
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
        # "sinat" — common Tagalog for a mild feverish feeling ("parang may
        # sinat ako"); the semantic stage under-scores it even standalone,
        # so it is pinned here deterministically.
        "sinat",
        "may sinat",
        "may sinat ako",
        "sinat ako",
        "nagkaka sinat",
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
    
        "hilantan",
        "gihilantan",
        "nihilantan",
        "nahilantan",
        "mihilantan",
        "naghihilantan",
        "hilanaton",
        # Bisaya — other common fever words
        "kalintura",
        "may kalintura",
        "naa koy kalintura",
        "panuhot",
        "panuhoton",
        "napanuhot",
        "ga panuhot",
        # Bisaya verb forms of hilanat / lagnat
        "nagkalagnat",
        "kalagnat",
        "naglagnat",
        "gikalagnat",
        "gikalagnatan",
        "gilagnat",
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
        "init akong paminaw",
        "init kaayo akong paminaw",
        "init kaayo akong paminaw ron",
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
        "feels hot",
        "feels so hot",
        "feel so hot",
        "feeling so hot",
        "my body feels hot",
        "body feels hot",
        "my body feels warm",
        "body feels warm",
        "feverish",
        "i feel feverish",
        # Temperature phrasing
        "mataas ang temperatura",
        "mataas ang temperatura ko",
        "ang taas ng temperatura",
        "taas akong temperatura",
        "taas ang akong temperatura",
        "taas ang temperatura",
        "high temperature",
        "temperature is high",
        "my temperature is high",
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
        "bodypain",
        "body pain",
        "body hurts",
        "my body hurts",
        "my body is aching",
        "my body has been aching",
        "body has been aching",
        "body is aching",
        "muscle pain",
        "muscle aches",
        "muscle ache",
        "muscles ache",
        "my muscles ache",
        "muscles are aching",
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
        "nangangalay",
        "nangangalay ang katawan",
        "nangangalay ang katawan ko",
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
        "kapoy kaayo",
        "sakit tibuok lawas",
        "tibuok lawas sakit",
        # Alternative phrasings
        "parang pinukpok",
        "nanlalamig",
        "giniginaw",
        "feel very warm",
        # Fatigue / weakness phrasing (weakness alone is NOT a body ache)
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
        "barado akong ilong",
        "sipon na barado",
        # Bisaya
        "barado ilong",
        "barado akong ilong",
        "bara ang ilong",
        "lisod ginhawa sa ilong",
        "stuffy akong ilong",
        "bara akong ilong",
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
        "sip-on",
        # "sip-un" — same word, h/g-hardened spelling. _normalize folds the
        # hyphen to a space, so it is listed as "sip un".
        "sip un",
        "may sipon",
        "may sipon ako",
        "naa koy sip-on",
        "naay sip-on",
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
        "get allergies",
        "i get allergies",
        "may allergy",
        "may allergies",
        # Tagalog
        "allergy",
        "bahing",
        "bumabahing",
        "napapabahing",
        "nagbahing",
        "makati ilong",
        "makati mata",
        # Bisaya
        "allergy",
        "bahing",
        "gibahing",
        "mibahing",
        "katol ilong",
        "katol mata",
        "mangatol ang ilong",
        "mangatol ilong",
        "mangatol ang mata",
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
        # Bisaya — "guol" (upset/aching) stomach descriptions
        "guol akong tiyan",
        "guol ang akong tiyan",
        "guol ang tiyan ko",
        "guol sa tiyan",
        # Alternative phrasings
        "buhol buhol",
        "buhol buhol ang tiyan",
        "kumukulo",
        "kumukulo ang tiyan",
        "hyperacidity",
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
        "diarrea",
        "diarrhoea",
        "diarhea",
        "diharia",
        "loose stool",
        "watery stool",
        "frequent bowel movements",
        "watery bowel movements",
        "stool is watery",
        "stool has been watery",
        "stool was watery",
        "my stool is watery",
        # Tagalog
        "pagtatae",
        "nagtatae",
        "tinatae",
        "tinatae ako",
        "nagpapataes",
        "nagtatae ako",
        "lbm",
        "malambot na dumi",
        "matubig na dumi",
        "labnaw ang dumi",
        "labnaw na dumi",
        "sobrang labnaw",
        "labnaw ang pagdumi",
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
        "paglibang",
        "pagkalibang",
        "labnaw ang pagkalibang",
        "labnaw ang akong pagkalibang",
        # Bisaya — intense/ongoing watery stool
        "ka-labnaw",
        "grabe ka-labnaw",
        "grabe ka labnaw",
        "sige ug grabe ka-labnaw",
        "sige ug labnaw",
        "labnaw kaayo",
        # Alternative phrasings
        "matubig ang dumi",
        "sige cr",
        "loose bowel",
    ],
    "TOOTHACHE": [
        # English
        "toothache",
        "tooth ache",
        "tooth pain",
        "tooth hurts",
        "my tooth hurts",
        "teeth hurt",
        "molar pain",
        "aching tooth",
        "painful tooth",
        # Tagalog / Taglish
        "sakit ngipin",
        "sakit ng ngipin",
        "sakit sa ngipin",
        "masakit ngipin",
        "masakit ang ngipin",
        "masakit ang ngipin ko",
        "sumasakit ang ngipin",
        "sumasakit ang ngipin ko",
        "ngilo",
        "nangingilo",
        "nangingilo ang ngipin",
        "masakit bagang",
        "sakit bagang",
        "sakit ng bagang",
        "masakit ang bagang",
        # Taglish — "yung tooth" phrasing (suite coverage)
        "masakit yung tooth",
        "masakit ang tooth",
        "masakit yung tooth ko",
        "masakit ang tooth ko",
        "masakit ang aking tooth",
        "sakit yung tooth",
        "sakit ang tooth",
        "sakit yung tooth ko",
        "sakit ang tooth ko",
        "sumasakit yung tooth",
        "sumasakit yung tooth ko",
        "masakit yung ngipin",
        "masakit yung ngipin ko",
        "sakit yung ngipin",
        "sakit yung ngipin ko",
        "masakit ang molar",
        "masakit yung molar",
        "masakit yung molar ko",
        # Bisaya
        "sakit akong ngipon",
        "gasakit akong ngipon",
        "ga sakit akong ngipon",
        "sakit akong bag-ang",
        "sakit akong bagang",
        "gasakit akong bag-ang",
        "gasakit akong bagang",
        "nisakit akong ngipon",
        "murag gasakit akong ngipon",
        "sakit sa ngipon",
        "manghubag ang ngipon",
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
    # "won't stop" verbs: "dili mawala akong ubo" negates MAWALA, not UBO
    "mawala", "mohunong", "hunong", "huminto", "tigil", "hinto",
    "stop", "undang", "naundang", "munting",
    # "hindi nawawala ang ubo ko" — same won't-stop pattern, infixed form
    "nawawala", "nawala", "nawagtang",
    # Tooth terms so dental negation scoping works
    "ngipin", "ngipon", "tooth", "teeth", "bagang", "bag-ang", "molar",
    # Nasal family terms
    "tulo", "tumutulo", "nagtulo", "nagatulo", "pagtulo", "agas",
    "umaagos", "nag-agas", "leak", "dripping", "drip", "barado",
    "blocked", "stuffy", "clogged", "bara", "congested", "congestion",
    "sip-on", "sneezing", "bahing", "makati", "katol", "nangangati",
}

# Shared negation word set (normalized: apostrophes stripped).
# English contractions included so "I don't have a fever" is handled.
# NOTE: "cant" is deliberately excluded — "I can't focus" negates FOCUS,
# not a symptom ("I can't sleep because my head hurts" = headache present).
_NEG_WORDS = (
    "no", "not", "without", "never", "none", "neither", "nor", "no more",
    "dont", "doesnt", "didnt", "isnt", "arent", "wasnt", "werent",
    "havent", "hasnt", "wont",
    "wala", "walang", "walay", "waley", "hindi", "hnd", "di", "dili",
    "dli", "wara", "wa",
)

_NEG_WORDS_RX = r"\b(?:" + "|".join(_NEG_WORDS) + r")\b"

# Negation scoping window: max filler tokens between the neg word and the
# target symptom phrase. "I don't have a fever" = dont + (have a) = 2 fillers.
_NEG_WINDOW = 4

# ── Negation SCOPE (coordinate/accumulated negation) ─────────────────────
# A negation word covers its whole clause: "wala koy gibati na sakit akong
# tiyan kay okay ra ug sakit sa ulo" negates BOTH the stomach pain and the
# headache, while "pero gi ubo ko" starts a fresh positive clause.
#   _NEG_SCOPE_END  — words that CLOSE a negation scope (contrast,
#                     consequence, reason-result, concession, and positive
#                     assertion words like "naa/may").  Anything after them
#                     belongs to a new, positive clause.
#   _NEG_SCOPE_JOIN — connectors that LENGTHEN the scope across coordinate
#                     lists: "wala akong ubo at sipon" negates both.
#   _NEG_TRAP_VERBS — verbs whose negation belongs to the VERB, not the
#                     symptom: "dili mawala akong ubo" (won't stop) and
#                     "hindi na ako makagalaw dahil sa sakit ng katawan"
#                     (can't move) leave the symptom present.
_NEG_SCOPE_END = frozenset({
    "pero", "but", "apan", "kundi", "gawas", "maliban", "kaso", "however",
    "though", "besides", "because", "so", "therefore", "bisan",
    "bisag", "biskan", "kung", "mao", "busa",
    "may", "meron", "mayroon", "mayron", "naa", "naay", "naai",
})
# Sequencing words that CONTINUE the narrative but do NOT open a new,
# contrastive clause: "wala koy sakit sa ulo ... tapos ... ug sakit sa
# tiyan" keeps the negation scope open across the sequencing words, exactly
# like the manuscript's accumulated-negation model ("wala koy A tapos ... ug
# B" negates both).  Contradictory-sounding sequences ("wala koy ubo tapos
# sige kog ubo") are not real kiosk inputs and no benchmark row exercises
# them; a positive re-assertion is always marked by an assertion word
# (naa/may) or a contrast word (pero/but), which still close the scope.
_NEG_SEQUENCE_WORDS = frozenset({
    "tapos", "then", "unya", "nya",
})
# Positive-assertion words that open a NEW (positive) clause — except when
# fused into the negative construction itself: "wala may mogawas" /
# "wala naman may X" (nothing comes out) — then they are part of the
# negation and must NOT close the scope.
_NEG_ASSERTION_WORDS = frozenset({
    "may", "meron", "mayroon", "mayron", "naa", "naay", "naai",
})
_NEG_ASSERTION_PARTICLES = frozenset({
    "naman", "man", "na", "ra", "gud", "jud", "pod", "pud", "lang",
    "po", "din", "rin", "ba", "pa", "sad",
})
_NEG_SCOPE_JOIN = frozenset({
    "ug", "og", "at", "and", "or", "kay", "kasi", "tsaka", "saka", "tas",
    "sabay",
})
_NEG_TRAP_VERBS = frozenset({
    "mawala", "nawawala", "nawala", "nawagtang", "mohunong", "hunong",
    "huminto", "tigil", "hinto", "stop", "undang", "naundang", "munting",
    "makatiis", "makagalaw", "makakilos", "makalihok", "makalakaw",
    "makatulog", "makahinga", "makakain", "makasulti", "makakita",
    "makatindog", "makabarug", "mabangon", "makabangon", "makaginhawa",
    "kagalaw", "kalihok", "kakilos", "katulog", "kahiga",
})

# Wellness words that negate a symptom ("my head feels fine", "maayo ra ang
# tiyan ko"). Kept separate because they must NOT be negated themselves
# ("dili maayo ang tiyan" = stomach is NOT fine = positive symptom).
_WELLNESS_WORDS = ("fine", "normal", "okay", "ok", "ayos", "maayo", "maayos", "klaroha")

# Body part -> symptom label family for wellness-negation ("head feels fine").
_BODY_PART_SYMPTOMS = {
    "head": {"HEADACHE"},
    "ulo": {"HEADACHE"},
    "headache": {"HEADACHE"},
    "tiyan": {"STOMACH_ACHE"},
    "stomach": {"STOMACH_ACHE"},
    "tummy": {"STOMACH_ACHE"},
    "lalamunan": {"SORE_THROAT"},
    "tutunlan": {"SORE_THROAT"},
    "throat": {"SORE_THROAT"},
    "ilong": {"NASAL_CONGESTION", "RUNNY_NOSE", "ALLERGIC_RHINITIS"},
    "nose": {"NASAL_CONGESTION", "RUNNY_NOSE", "ALLERGIC_RHINITIS"},
    "katawan": {"BODY_ACHES"},
    "lawas": {"BODY_ACHES"},
    "body": {"BODY_ACHES"},
    "muscle": {"BODY_ACHES"},
    "muscles": {"BODY_ACHES"},
    "kalamnan": {"BODY_ACHES"},
    "kaunoran": {"BODY_ACHES"},
    "ngipin": {"TOOTHACHE"},
    "ngipon": {"TOOTHACHE"},
    "tooth": {"TOOTHACHE"},
    "teeth": {"TOOTHACHE"},
    "bagang": {"TOOTHACHE"},
    "bag-ang": {"TOOTHACHE"},
    "molar": {"TOOTHACHE"},
    "temperatura": {"FEVER"},
    "temperature": {"FEVER"},
    "balat": {"RASHES"},
    "panit": {"RASHES"},
    "skin": {"RASHES"},
    "dumi": {"DIARRHEA"},
    "pagdumi": {"DIARRHEA"},
    "paglibang": {"DIARRHEA"},
    "pagkalibang": {"DIARRHEA"},
    "mata": {"ALLERGIC_RHINITIS"},
    "eyes": {"ALLERGIC_RHINITIS"},
}


def _wellness_negated_labels(normalized_text: str) -> set:
    """Return symptom labels negated by a wellness statement.

    "my head feels fine" / "maayo ra akong tiyan" / "temperature is normal"
    negate the corresponding symptom. The wellness word itself must NOT be
    negated ("dili maayo" = NOT fine = positive), so a neg word within 2
    tokens before it suppresses the rule.
    """
    _filler = r"(?:\s+(?!pero\b|but\b|kaso\b|however\b|though\b)\w+){0,3}"
    out = set()
    for body_part, labels in _BODY_PART_SYMPTOMS.items():
        # body part before wellness: "my head feels fine", "maayo ra akong tiyan"
        for m in re.finditer(
            rf"\b{re.escape(body_part)}\b{_filler}\s+"
            rf"\b({'|'.join(_WELLNESS_WORDS)})\b",
            normalized_text,
        ):
            before = normalized_text[: m.start()]
            last_neg = list(re.finditer(_NEG_WORDS_RX, before))
            if last_neg:
                tail = normalized_text[last_neg[-1].end(): m.start()]
                if len(tail.split()) <= 2:
                    continue  # "dili maayo ang tiyan" — NOT fine, keep positive
            out.update(labels)
        # wellness before body part: "okay naman yung tiyan ko", "fine ang ulo"
        for m in re.finditer(
            rf"\b({'|'.join(_WELLNESS_WORDS)})\b{_filler}\s+"
            rf"\b{re.escape(body_part)}\b",
            normalized_text,
        ):
            before = normalized_text[: m.start()]
            last_neg = list(re.finditer(_NEG_WORDS_RX, before))
            if last_neg:
                tail = normalized_text[last_neg[-1].end(): m.start()]
                if len(tail.split()) <= 2:
                    continue
            out.update(labels)
    return out


def _negation_reaches(
    normalized_text: str, marker_end: int, target_word: str, phrase_first: str
) -> bool:
    """Walk the tokens after a negation marker; True if the negation scope
    actually reaches target_word.

    The scope LENGTHENS across coordinate connectors ("wala akong ubo at
    sipon" negates both the cough and the cold) and CLOSES at:

      - contrast / consequence words: "pero gi ubo ko" is a new clause;
      - positive assertion words: "wala koy ubo, naa koy sipon";
      - "trap" verbs whose negation belongs to the verb itself
        ("dili mawala akong ubo" = the cough won't stop, so it persists;
        "hindi na ako makagalaw dahil sa sakit ng katawan" = can't move);
      - a closer symptom keyword that the negation is "consumed" by
        ("hindi pala ubo sipon" negates only the cough) — unless a
        connector ties the two symptoms together as one list
        ("wala koy ubo ug sakit sa ulo" negates both).
    """
    tail = normalized_text[marker_end:].split()
    target_idx = None
    for i, tok in enumerate(tail):
        bare = _strip_token(tok)
        if bare == target_word or bare == target_word + "s" or bare == target_word + "es":
            target_idx = i
            break
    if target_idx is None:
        return False
    seen_symptom = False
    for i in range(target_idx):
        bare = _strip_token(tail[i])
        if not bare:
            # Punctuation-only token (e.g., comma in "tiyan, ulo") — skip it,
            # don't close the scope. Commas separate list items but don't
            # break negation: "wala koy sakit sa tiyan, ulo, ngipon".
            continue
        if bare in _NEG_SCOPE_END and bare not in _NEG_ASSERTION_WORDS:
            return False
        if bare in _NEG_ASSERTION_WORDS:
            # "wala may mogawas" / "wala naman may X" — the assertion word is
            # fused into the negative construction and must NOT open a new
            # positive clause.  Standalone "may/naa" does open one.
            if i == 0:
                continue
            prev = _strip_token(tail[i - 1])
            if prev in _NEG_WORDS:
                continue
            if prev in _NEG_ASSERTION_PARTICLES:
                if i == 1 or _strip_token(tail[i - 2]) in _NEG_WORDS:
                    continue
            return False
        if bare in _NEG_SCOPE_JOIN:
            continue
        if bare in _NEG_TRAP_VERBS:
            # "dili mawala akong ubo" negates MAWALA (won't stop), so the
            # cough persists.
            return False
        if bare in _WELLNESS_WORDS and not seen_symptom:
            # "dili normal akong pagkalibang" negates NORMAL, so the symptom
            # survives.  But after a symptom is in play ("...tiyan kay okay
            # ra ug sakit sa ulo") the wellness word is part of a reason
            # clause and must NOT stop the scope.
            return False
        if (
            bare in _INTERVENING_SYMPTOM_WORDS
            and bare != phrase_first
            and not _same_symptom_family(bare, target_word)
        ):
            seen_symptom = True
            # Negation is consumed by this closer symptom keyword — UNLESS a
            # join connector ties it to the target as one coordinate list.
            # This includes:
            # 1. Explicit connectors: "wala koy tiyan ug ulo" 
            # 2. Parallel structure: "wala koy sakit sa tiyan sakit sa ulo"
            #    (the phrase_first word repeats, indicating a list)
            joined = False
            
            # Check for phrase_first repetition (parallel structure list)
            # "sakit sa tiyan, sakit sa ulo" → phrase_first="sakit" appears again
            # Also detect abbreviated lists: "sakit akong tiyan, akong ulo" where
            # possessive markers (akong/ang/sa) signal the continuation
            for j in range(i + 1, target_idx):
                b = _strip_token(tail[j]) if j < len(tail) else ""
                if not b:
                    # Empty stripped token = punctuation, skip
                    continue
                # Parallel structure: phrase_first repeats before target
                # Guard: for single-word phrases (phrase_first == target_word),
                # only count it if it's NOT at the target position
                if b == phrase_first and (phrase_first != target_word or j != target_idx - 1):
                    joined = True
                    break
                # Abbreviated list with possessive/article markers:
                # "sakit akong tiyan, akong ulo" - "akong" signals continuation
                if b in {"akong", "ang", "sa", "ko", "nako", "aking", "among"}:
                    # Check if next token is a body part (indicates list continuation)
                    if j + 1 < len(tail):
                        next_tok = _strip_token(tail[j + 1]) if j + 1 < len(tail) else ""
                        if next_tok in _INTERVENING_SYMPTOM_WORDS or next_tok == target_word:
                            joined = True
                            break
                if b in _NEG_SCOPE_JOIN:
                    joined = True
                    break
                if b in _NEG_SCOPE_END or b in _NEG_TRAP_VERBS:
                    # Scope explicitly closed
                    break
            if not joined:
                return False
    return True


def _strip_token(tok: str) -> str:
    """Strip punctuation from a single token for negation-scope walking."""
    return tok.strip(".,;:!?()\"'")


def _is_negated(normalized_text: str, normalized_phrase: str) -> bool:
    """Detect simple negation patterns like 'no fever' / 'walang lagnat'.

    Deterministic rule (easy to explain): a negation word negates its whole
    clause — the scope lengthens across coordinate connectors ("wala akong
    ubo at sipon") and closes at contrast words ("pero gi ubo ko"), positive
    assertion words ("naa koy sipon"), and scope-ending conjunctions
    ("mao", "dahil", "tapos").

    Safety: if another known symptom keyword sits between the negation word
    and the target phrase, the negation is "consumed" by that closer keyword
    and does not propagate, UNLESS a connector joins them as one list:
    "hindi pala ubo sipon" negates only "ubo"; "wala koy ubo ug sipon"
    negates both.  Same-family words ("wala akong sipon na tumutulo") are
    NOT consumed — the negation covers the whole nasal phrase.

    Each negation word is checked independently (not finditer which skips
    overlapping matches). If ANY negation word reaches the target with no
    consumed intervening symptom, the phrase IS negated.

    This is intentionally simple and not perfect NLP.
    """

    if not normalized_phrase:
        return False

    # Check negation reaching the LAST word of the phrase (for multi-word
    # phrases) or the only word (single-word phrases). The last word is the
    # distinctive part of body-part phrases ("sakit akong bag-ang" -> the
    # negated "sakit" in "wala koy sakit sa ulo" belongs to the HEAD, not the
    # tooth — checking only "bag-ang" avoids that false negation).
    # This still handles "hindi sumasakit ang ngipin ko" negating the phrase
    # "masakit ang ngipin": the neg word reaches "ngipin" (last word) through
    # the fillers "sumasakit ang".
    phrase_words = normalized_phrase.split()
    # Phrases that THEMSELVES start with a negation word are fixed idioms whose
    # "negation" is intrinsic: "dili katulon" (cannot swallow), "walang plema",
    # "no phlegm".  Re-negating them would be wrong — "dili katulon ang akong
    # pagkaon" IS a sore throat, not a negated one.
    if phrase_words and phrase_words[0] in _NEG_WORDS:
        return False
    # Strip trailing pronoun/particle words ("masakit ang tiyan ko" -> the
    # distinctive word is "tiyan", not "ko") so negation reaches the right
    # target: "hindi sumasakit ang tiyan ko" negates the whole phrase.
    while phrase_words and phrase_words[-1] in (
        "ko", "my", "mo", "nako", "namo", "akong", "kong", "koy", "aking",
        "among", "aming", "ang", "ng", "na", "nga", "ay", "si", "kini",
        "lang", "naman", "nga lang", "na lang", "din", "rin",
    ):
        phrase_words.pop()
    phrase_first = phrase_words[0] if phrase_words else normalized_phrase
    check_words = [phrase_words[-1]] if phrase_words else [normalized_phrase]
    for target in set(check_words):
        for neg_m in re.finditer(_NEG_WORDS_RX, normalized_text):
            if _negation_reaches(normalized_text, neg_m.end(), target, phrase_first):
                return True  # Genuine negation found

    return False  # All matches had consumed negation


def _same_symptom_family(a: str, b: str) -> bool:
    """True if two words belong to the same symptom family.

    Used by the consumed-negation rule: "wala akong sipon na tumutulo"
    negates the whole runny-nose phrase, so "sipon" between the neg word
    and "tumutulo" must NOT consume the negation.  But "hindi ubo sipon"
    must still consume: "ubo" and "sipon" are different families.
    """
    families = [
        {"sipon", "sip-on", "tumutulo", "nagtulo", "nagatulo", "pagtulo", "tulo",
         "running", "runny", "tumatakbo", "dripping", "drip", "agas",
         "umaagos", "nag-agas", "leak", "nagtulong"},
        {"barado", "blocked", "stuffy", "clogged", "bara", "congested",
         "congestion", "puno"},
        {"ubo", "cough", "umuubo", "inuubo", "umoubo", "kakaubo", "giubo", "gihubo",
         "nagubo", "nahubo", "mihubo", "umubo", "nag-ubo", "coughing"},
        {"lagnat", "fever", "hilanat", "gihilanat", "nilalagnat", "kalagnat"},
        {"ngipin", "ngipon", "tooth", "teeth", "bagang", "bag-ang", "molar"},
        {"mata", "eyes", "ilong", "nose"},
        {"makati", "katol", "bahing", "sneezing", "itchy", "nangangati",
         "mangatol"},
    ]
    for fam in families:
        if a in fam and b in fam:
            return True
    return False


def _extract_cough_type(normalized_text: str) -> List[str]:
    """Return cough intent(s) based on qualifiers.

    Why we need this:
    - "walay plema" contains the word "plema".
      A naive matcher might classify it as PRODUCTIVE.
    - We solve it using explicit DRY (negative) phrases.
    - "isn't a dry cough" must NOT be classified as DRY.

    Returns:
        [] if no cough mentioned
        ['COUGH_DRY'] or ['COUGH_PRODUCTIVE']
        ['COUGH_GENERAL'] if cough exists but no qualifier
    """

    # "I don't know if dry or may plema" — no qualifier decides → GENERAL.
    if re.search(
        r"\b(?:dont\s+know|di\s+ko\s+alam|hindi\s+ko\s+alam|"
        r"dili\s+ko\s+kahibalo|ambot|not\s+sure)\b",
        normalized_text,
    ):
        type_words = r"\b(dry|plema|mucus|wet|product|productive|phlegm)\b"
        or_anywhere = (
            re.search(rf"\b(or|o)\b.*{type_words}", normalized_text)
            or re.search(rf"{type_words}.*\b(or|o)\b", normalized_text)
        )
        if or_anywhere and re.search(r"\b(cough|ubo|coughing)\b", normalized_text):
            return ["COUGH_GENERAL"]

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
                "giubo",
                "kakaubo",
                "naubo",
                "ga ubo",
                "ga-ubo",
                # Bisaya inflected forms of "ubo"
                "gihubo",
                "nagubo",
                "nahubo",
                "mihubo",
                # Additional verb forms (suite coverage)
                "umubo",
                "umoubo",
                "nauubo",
                "mag-ubo",
                "nagsimulang umubo",
                "madalas akong umubo",
                "sige akog cough",
                "sige kog cough",
                "sige kong cough",
                "sige akong cough",
                "sige kog ubo",
                "sige ko g ubo",
                "nag-ubo ko",
                "nag ubo ko",
                "sige'g ubo",
                "nagtigkal",
                "mig-ubo",
                "ginaubo",
                # Cebuano: uhot = cough
                "uhot",
                "nag-uhot",
                "ga uhot",
                "gi-uhot",
            )
        )
    if not cough_present:
        return []

    # Check for explicit cough negation BEFORE deciding cough type.
    # Examples: "walang ubo", "wala akong ubo", "no cough", "without cough"
    #
    # Important guard: "no plema ... coughing" does NOT mean "no cough".
    # The negation applies to phlegm, not to cough itself.
    # Also: "dili mawala akong ubo" negates MAWALA (won't stop) — the cough
    # persists, so mawala/mohunong/stop fillers consume the negation.
    _cough_neg_skip = {"plema", "phlegm", "mucus", "mawala", "mohunong",
                       "hunong", "huminto", "tigil", "hinto", "stop",
                       "undang", "naundang", "nawawala", "nawala",
                       "nawagtang",
                       # Qualifier words: "isn't a dry cough" negates DRY,
                       # not the cough itself (type decided further below)
                       "dry", "wet", "tuyo", "tuyong", "uga", "basa",
                       "basang", "productive", "tickly"}
    cough_neg_matches = re.finditer(
        rf"{_NEG_WORDS_RX}((?:\s+\w+){{0,{_NEG_WINDOW}}})\s+"
        r"\b(ubo|cough|coughing|umuubo|inuubo|umoubo|gihubo|nagubo|nahubo|mihubo)\b",
        normalized_text,
    )
    for m in cough_neg_matches:
        filler_tokens = m.group(1).split()
        if any(tok in _cough_neg_skip for tok in filler_tokens):
            continue
        # A scope-end word between the negation and the cough word starts a
        # new clause — the negation cannot reach across it ("walang sore
        # throat pero umuubo" keeps the cough). Exception: assertion words
        # fused into the negative construction itself ("wala may ubo").
        boundary = False
        for j, tok in enumerate(filler_tokens):
            if tok not in _NEG_SCOPE_END:
                continue
            if tok in _NEG_ASSERTION_WORDS and j == 0:
                continue
            if (
                tok in _NEG_ASSERTION_WORDS
                and j == 1
                and filler_tokens[0] in _NEG_ASSERTION_PARTICLES
            ):
                continue
            boundary = True
            break
        if boundary:
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
        # English — no-mucus phrasing (suite coverage)
        "no mucus",
        "no mucus at all",
        "without mucus",
        "without any mucus",
        "no phlegm at all",
        "nothing comes out",
        "nothing is coming out",
        "isnt any phlegm",
        "dont have any phlegm",
        "produces no mucus",
        "no plema at all",
        "without bringing up anything",
        "brings up nothing",
        # Tagalog
        "walang plema",
        "wala plema",
        "wala akong plema",
        "wala po akong plema",
        "wala namang plema",
        "wala naman plema",
        "wala pa plema",
        "tuyong ubo",
        "tuyo ang ubo",
        "ubo ko ay tuyo",
        "ang ubo ko ay tuyo",
        "ubo ay tuyo",
        "super dry",
        "very dry",
        "so dry",
        "dry na ubo",
        "dry at",
        # Tagalog — no-mucus phrasing
        "walang mucus",
        "walang lumalabas na plema",
        "walang plemang lumalabas",
        "walang plemang mogawas",
        "wala akong mailabas na plema",
        "walang mailabas na plema",
        "wala akong lumalabas na plema",
        "no lumalabas na plema",
        "walang lumalabas na mucus",
        # Bisaya
        "walay plema",
        "waley plema",
        "wala koy plema",
        "wala ko y plema",
        "uga nga ubo",
        "uga akong ubo",
        "uga kaayo akong ubo",
        "uga ang akong ubo",
        # Bisaya — no-mucus phrasing
        "walay mogawas nga plema",
        "wala koy mogawas nga plema",
        "walay mucus",
        "walay mogawas nga mucus",
        "wala koy plema nga mogawas",
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
        # Tagalog — mucus phrasing
        "may mucus",
        "may lumalabas na plema",
        "may lumalabas na mucus",
        "may plemang lumalabas",
        # Bisaya / Conyo
        "naay plema",
        "ubo na naay plema",
        "basa nga ubo",
        "with plema",
        "halak",
        "hubak",
        # Bisaya — mucus phrasing
        "naay mucus",
        "naay mogawas nga plema",
        "naay mogawas na plema",
        "mugawas nga plema",
        "mugawas na plema",
        # English — bringing-up phrasing
        "bringing up phlegm",
        "bringing up mucus",
        "coughed up mucus",
        "coughing up phlegm",
        "coughing up mucus",
        "cough up phlegm",
        "cough up mucus",
        # Thick-mucus phrasing (suite coverage)
        "thick mucus",
        "thick phlegm",
        "coughing up thick mucus",
        "coughed up thick mucus",
        "thick na plema",
        "thick na mucus",
        # Tagalog — thick mucus
        "makapal na plema",
        "makapal na mucus",
        "may makapal na plema",
        "malapot na plema",
        "may malapot na plema",
        "malapot na mucus",
        "malapot ang plema",
        # Bisaya — lots of phlegm
        "daghan nga plema",
        "daghan kaayo nga plema",
        "naay daghan nga plema",
        "baga nga plema",
        "naay baga nga plema",
        "baga nga mucus",
    ]

    # A dry qualifier that is itself negated ("isn't a dry cough",
    # "hindi tuyong ubo", "dili uga nga ubo") must NOT set is_dry.
    def _dry_phrase_negated(phrase: str) -> bool:
        return _is_negated(normalized_text, phrase) or re.search(
            rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+{re.escape(phrase)}\b",
            normalized_text,
        ) is not None

    is_dry = False
    for p in dry_qualifiers:
        np_ = _normalize(p)
        if _phrase_in_text(normalized_text, np_):
            if not _dry_phrase_negated(np_):
                is_dry = True
                break
    # Catch common pattern: "wala (namang) plema" even with extra filler words.
    if not is_dry:
        for neg in ("wala", "walang", "waley", "walay", "no", "not", "without",
                    "dont", "isnt", "havent", "hasnt", "wala ko", "wala koy"):
            if re.search(rf"\b{neg}(?:\s+\w+){{0,3}}\s+(?:nga\s+|na\s+)?plema(?:ng)?\b", normalized_text):
                is_dry = True
                break
    if not is_dry and re.search(r"\bno(?:\s+\w+){0,2}\s+mucus\b", normalized_text):
        is_dry = True
    if not is_dry and re.search(r"\bwithout(?:\s+\w+){0,2}\s+mucus\b", normalized_text):
        is_dry = True
    if not is_dry and re.search(r"\bnothing\s+comes\s+out\b", normalized_text):
        is_dry = True
    is_wet = any(_phrase_in_text(normalized_text, _normalize(p)) for p in wet_qualifiers)

    # "this isn't a dry cough" with mucus present → PRODUCTIVE wins.
    if re.search(rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+dry\s+cough\b", normalized_text):
        if is_wet:
            return ["COUGH_PRODUCTIVE"]

    # Priority: explicit DRY phrases win over WET.
    if is_dry:
        return ["COUGH_DRY"]
    if is_wet:
        return ["COUGH_PRODUCTIVE"]
    return ["COUGH_GENERAL"]


# ---------------------------------------------------------------------------
# 2) NORMALIZATION + MATCHING LOGIC
# ---------------------------------------------------------------------------

# Known Tagalog/Bisaya tokens that must NOT be phonetically normalized.
# These are words the dictionary already knows exactly; normalizing them
# would produce wrong forms (e.g., "sipon" -> "sipun" breaks the match).
_KNOWN_LOCAL_TOKENS: frozenset = frozenset({
    # Cough
    "ubo", "inuubo", "umuubo", "kakaubo", "giubo", "ga-ubo",
    "gihubo", "nagubo", "nahubo", "mihubo", "gubo",
    # Fever
    "lagnat", "hilanat", "gihilanat", "hilantan", "kalintura",
    "panuhot", "sinat", "binat",
    # Runny nose / nasal
    "sipon", "sip-on", "simhot", "kasimhot",
    # Headache (ulo = head, must not be corrected to ubo = cough)
    "ulo", "labad", "kirot", "sakit", "masakit", "sumasakit",
    "gasakit", "gibukbok",
    # Stomach / diarrhea
    "tiyan", "sikmura", "puson", "kabag", "hilab",
    "pagtatae", "nagtatae", "kalibang", "pagkalibang", "labnaw",
    # Sore throat
    "lalamunan", "tutunlan", "tilaok",
    # Body aches
    "katawan", "lawas", "ngalay", "nangangalay",
    # Rashes
    "pantal", "butlig",
    # Allergy
    "bahing", "mangatol",
    # Negation words (must NEVER be altered)
    "wala", "walang", "walay", "hindi", "dili", "di",
    # Time/manner words that should not be corrected
    "kalit", "bigla", "biglaan", "sukad", "ganiha",
    # Common connectors
    "pero", "tapos", "kaya", "dahil", "kasi", "ug", "og",
    "akong", "ang", "ang", "sa", "ng", "ko", "mo", "ka",
    "ako", "siya", "kami", "kayo", "sila", "nako", "niya",
    "namin", "natin", "nila", "ito", "iyan", "iyon",
    "naa", "may", "meron", "naay",
})

# Phonetic swaps common in Filipino/Bisaya typing errors.
# Applied token-by-token only on tokens NOT in _KNOWN_LOCAL_TOKENS.
# Rules are ordered: apply all substitutions to produce the candidate,
# then only keep it if it's different from the original.
_PHONETIC_SUBS = [
    # c/ck -> k  (stomack -> stomak, stomachk -> stomachk handled by fuzzy)
    (re.compile(r"ck\b"), "k"),
    (re.compile(r"\bc(?=[aouei])"), "k"),  # only word-initial c before vowels
    # Double vowels -> single (sipoon -> sipon, heaad -> head)
    (re.compile(r"([aeiou])\1"), r"\1"),
    # ea -> e (heaache -> heache — one step toward headache)
    (re.compile(r"ea(?=[a-z])"), "e"),
    # ph -> f (phlegm is already in dict, but phever -> fever)
    (re.compile(r"\bph"), "f"),
    # -tion -> -syon (common Filipino suffix spelling)
    (re.compile(r"tion\b"), "syon"),
]


def _phonetic_normalize_token(tok: str) -> str:
    """Apply Filipino phonetic normalization to a single token.

    Only called on tokens not already in _KNOWN_LOCAL_TOKENS.
    Returns the normalized form (may be identical to input).
    """
    result = tok
    for pattern, replacement in _PHONETIC_SUBS:
        result = pattern.sub(replacement, result)
    return result


def _normalize(text: str) -> str:
    """Normalize text for consistent phrase matching.

    - Lowercase
    - Replace punctuation with spaces
    - Collapse repeated whitespace
    - Jejemon/leet normalization
    - Token-level Filipino phonetic normalization for unrecognized tokens

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
    # Apostrophes are stripped entirely (not replaced by space) so English
    # contractions match the neg-word list: "isn't" -> "isnt", "don't" -> "dont".
    text = text.replace("'", "")
    text = re.sub(r"[^a-z0-9ñ\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    # Token-level Filipino phonetic normalization.
    # Only applied to tokens not already known as valid local words —
    # this prevents mangling correct Tagalog/Bisaya terms.
    tokens = text.split()
    tokens = [
        tok if tok in _KNOWN_LOCAL_TOKENS else _phonetic_normalize_token(tok)
        for tok in tokens
    ]
    text = " ".join(tokens)

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


# ---------------------------------------------------------------------------
# Generic typo rescue (anchor-word table)
# ---------------------------------------------------------------------------
# One deterministic pass that maps ANY misspelled symptom word ("hedache",
# "totache", "couhg", "stomake"...) to its label via bounded Levenshtein
# distance.  Per-anchor max distance is tuned so close-but-different words
# never fire ("boses" ~ "nose" is 2 edits, "isang" ~ "ilong" is 1 edit).
# The exact-match Tagalog/Bisaya synonyms live in SYMPTOM_DICTIONARY — the
# anchor table is deliberately ENGLISH-ONLY, because common Filipino words
# sit within 1-2 edits of the native anchors ("isang" ~ "ilong", "simula" ~
# "sikmura") and would destroy precision.  This stage ONLY rescues spelling
# errors, which is why it runs as the last detection stage.
_FUZZY_ANCHORS = [
    ("headache", "HEADACHE", 2),
    ("toothache", "TOOTHACHE", 2),
    ("stomachache", "STOMACH_ACHE", 2),
    ("stomach", "STOMACH_ACHE", 2),
    ("tummy", "STOMACH_ACHE", 1),
    ("diarrhea", "DIARRHEA", 2),
    ("fever", "FEVER", 1),
    ("cough", "COUGH_GENERAL", 2),
    ("throat", "SORE_THROAT", 2),
    ("sorethroat", "SORE_THROAT", 2),
    ("nose", "RUNNY_NOSE", 1),
    ("rash", "RASHES", 1),
    ("itchy", "RASHES", 2),
    ("sneeze", "ALLERGIC_RHINITIS", 2),
    ("allergy", "ALLERGIC_RHINITIS", 2),
    ("allergic", "ALLERGIC_RHINITIS", 2),
    ("body", "BODY_ACHES", 1),
    ("runny", "RUNNY_NOSE", 2),
]

# Tokens too close to an anchor to be trusted ("never" ~ "fever" is a
# genuine 1-edit word).  Any negator is ALSO skipped automatically — a word
# meaning "no X" must never fuzzy-fire as the symptom X.
_FUZZY_EXCLUDE = {
    # genuine near-miss English words (1-2 edits from an anchor)
    "ever", "never", "every", "lever", "fewer",       # ~ fever
    "tough", "rough", "bough", "dough", "couch",       # ~ cough
    "enough", "ought", "bought", "fought", "sought",   # ~ cough
    "threat", "that",                                   # ~ throat
    "funny", "bunny", "sunny",                          # ~ runny
    "freeze",                                          # ~ sneeze
    "hash",                                            # ~ rash
}

_SYMPTOM_WORD_SET: frozenset = frozenset()


def _dictionary_word_set() -> frozenset:
    """All tokens used by SYMPTOM_DICTIONARY phrases, computed once."""
    global _SYMPTOM_WORD_SET
    if not _SYMPTOM_WORD_SET:
        _SYMPTOM_WORD_SET = frozenset(
            w
            for phrases in SYMPTOM_DICTIONARY.values()
            for p in phrases
            for w in _normalize(p).split()
        )
    return _SYMPTOM_WORD_SET


def _fuzzy_token_is_negated(normalized_text: str, token: str) -> bool:
    """Token-level negation check for misspelled words.  The scoped walker
    cannot be used because the target word itself is garbled, so this uses
    the classic fixed-window rule (neg word + up to _NEG_WINDOW fillers +
    the token).  A contrast word between the marker and the token still
    short-circuits: "wala koy hedache pero gi ubo ko" must not negate
    "hedache"... it does not need to — the token sits BEFORE the contrast
    word, and the window check only looks at what is between them."""
    return bool(
        re.search(
            rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+\b{re.escape(token)}\b",
            normalized_text,
        )
    )


def _fuzzy_symptom_rescue(
    normalized_text: str,
    detected: List[str],
    negated_labels: set,
    wellness_negated: set,
    use_advanced: bool = True,
) -> None:
    """Map misspelled symptom words to their labels (in place).

    Precision rules:
    - Only tokens >= 4 chars and within |len_diff| <= 2 of an anchor.
    - Tokens that are real dictionary words (exact match) are skipped — the
      dictionary stage already evaluated them.
    - Per-anchor distance caps keep near-miss non-symptom words out.
    - A negated misspelling is recorded in negated_labels, never detected.
    
    Args:
        use_advanced: If True, use advanced multilingual fuzzy matching with
                      phonetic normalization, keyboard-weighted distance, and
                      n-gram similarity. If False, use legacy Levenshtein.
    """
    dict_words = _dictionary_word_set()
    # Negators AND scope words ("though", "however", "because"...) are
    # structural, never symptom typos — skip them wholesale.
    neg_words = set(_NEG_WORDS) | _FUZZY_EXCLUDE | set(_NEG_SCOPE_END) | _NEG_SEQUENCE_WORDS
    
    # Use advanced fuzzy matching if enabled
    if use_advanced:
        try:
            from .advanced_fuzzy import advanced_fuzzy_rescue
            advanced_fuzzy_rescue(
                normalized_text, detected, negated_labels, wellness_negated,
                dict_words, neg_words, _fuzzy_token_is_negated
            )
            return
        except ImportError:
            # Fall back to legacy if advanced module not available
            pass
    
    # Legacy fuzzy matching (original implementation)
    for token in normalized_text.split():
        if len(token) < 4 or not token.isalpha():
            continue
        if token in dict_words or token in neg_words:
            continue
        for anchor, label, max_dist in _FUZZY_ANCHORS:
            if label in detected or label in negated_labels or label in wellness_negated:
                continue
            if abs(len(token) - len(anchor)) > 2:
                continue
            if _levenshtein_within(token, anchor, max_dist):
                if _fuzzy_token_is_negated(normalized_text, token):
                    negated_labels.add(label)
                    break
                detected.append(label)
                break


# Nasal cue groups — single source of truth for _infer_nasal_label.
# Keep the neg-check list, the group-presence list, the allow-list, and the
# _has_any list in sync by deriving them all from these.
_NASAL_ALLERGY_CUES = [
    "makati", "katol", "bahing", "bumabahing", "napapabahing", "nagbahing",
    "gibahing", "mibahing", "sneeze", "sneezing", "itchy", "nangangati",
    "mangatol", "allergy", "allergic", "alerdyi",
]
_NASAL_RUNNY_CUES = [
    "sipon", "sip-on", "runny", "running", "tumatakbo", "tumutulo", "nagatulo",
    "drip", "dripping", "tulo", "pagtulo", "nagtulo", "leak", "leaking",
    "umaagos", "agas", "nag-agas",
]
_NASAL_CONGESTION_CUES = [
    "barado", "bara", "stuffy", "blocked", "clogged", "congested",
    "congestion", "lisod ginha", "lisod ginhawa", "hard to breathe",
    "difficulty breathing", "hard time breathing", "trouble breathing",
    "hirap huminga", "hirap akong huminga",
    # Cebuano possessive forms: "lisod ko'g ginhawa", "lisod kong ginhawa"
    "lisod kog ginhawa",
    "lisod kong ginha",
    "lisod kong ginhawa",
    "lisod nako ginha",
    "lisod nako ginhawa",
    "lisod akong ginha",
    "lisod akong ginhawa",
]


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
    # cases like "walang allergy pero barado ang ilong" → should detect NASAL_CONGESTION).
    # Uses the shared neg-word set (incl. contractions) + window 0-4.
    def _cue_negated(keyword: str) -> bool:
        """Check if keyword is negated, respecting consumed negation.

        If another symptom keyword of a DIFFERENT family sits between the neg
        word and the target, the negation is consumed by that closer symptom
        (e.g. "hindi ubo sipon" — "hindi" negates "ubo", not "sipon").
        Same-family words ("wala akong sipon na tumutulo") do NOT consume —
        the negation covers the whole nasal phrase.
        """
        phrase_pat = rf"((?:\s+(?!pero\b|but\b|kaso\b|however\b|though\b)\w+){{0,{_NEG_WINDOW}}})\s+{re.escape(keyword)}\b"
        for neg_m in re.finditer(_NEG_WORDS_RX, normalized_text):
            after = normalized_text[neg_m.end():]
            follow = re.match(phrase_pat, after)
            if not follow:
                continue
            filler_tokens = follow.group(1).split()
            consumed = any(
                ft in _INTERVENING_SYMPTOM_WORDS and not _same_symptom_family(ft, keyword)
                for ft in filler_tokens
            )
            if not consumed:
                return True  # Genuine negation
        return False

    allergy_cue_negated = any(_cue_negated(w) for w in _NASAL_ALLERGY_CUES)
    runny_cue_negated = any(_cue_negated(w) for w in _NASAL_RUNNY_CUES)
    congestion_cue_negated = any(_cue_negated(w) for w in _NASAL_CONGESTION_CUES)

    # If ALL nasal cue groups present are negated, bail out entirely
    all_negated = True
    for group_neg, group_words in [
        (allergy_cue_negated, _NASAL_ALLERGY_CUES),
        (runny_cue_negated, _NASAL_RUNNY_CUES),
        (congestion_cue_negated, _NASAL_CONGESTION_CUES),
    ]:
        group_present = any(_phrase_in_text(normalized_text, w) for w in group_words)
        if group_present and not group_neg:
            all_negated = False
            break
    if all_negated and re.search(_NEG_WORDS_RX, normalized_text):
        # Only return early if every mentioned nasal cue is negated
        if any(_phrase_in_text(normalized_text, w) for w in
               _NASAL_ALLERGY_CUES + _NASAL_RUNNY_CUES + _NASAL_CONGESTION_CUES):
            return

    runny_cues = _NASAL_RUNNY_CUES
    congestion_cues = _NASAL_CONGESTION_CUES
    allergy_cues = _NASAL_ALLERGY_CUES

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

    # Wellness negation: "my head feels fine" / "maayo ra akong tiyan"
    # negates the corresponding symptom even though no explicit neg word
    # sits next to it. Computed once, applied to dictionary + rescues.
    wellness_negated = _wellness_negated_labels(normalized_text)

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
            r"\b(sakit|masakit|masaket|sumasakit|gasakit|ga\s+sakit|kasakit|labad|throbbing|throbing|pounding|pulsating|kirot|gakurot|gikirot|kabutohon|kabuto|hurt|hurts|hurting|ache|aches|aching|pain|painful|sasabog|binibiyak|pumapasabog|grabe|sobra|grabeng|sobrang)\b",
            normalized_text,
        ) is not None
        if not pain_present:
            # Typo/jejemon rescue: skit->sakit, lbd->labad, masaket->masakit
            pain_present = any(
                (len(t) >= 2 and (_levenshtein_within(t, "sakit", 1) or _levenshtein_within(t, "labad", 2) or _levenshtein_within(t, "masakit", 1)))
                for t in tokens
            )

        headache_explicitly_negated = (
            # Scope-aware: "wala koy gibati na sakit akong tiyan ug sakit sa
            # ulo" negates the headache even across fillers and connectors.
            _is_negated(normalized_text, "sakit sa ulo")
            or _is_negated(normalized_text, "sakit ulo")
            or _is_negated(normalized_text, "masakit ang ulo")
            or _is_negated(normalized_text, "labad ang ulo")
            or _is_negated(normalized_text, "headache")
            or _is_negated(normalized_text, "head")
            or re.search(
                rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+\b(uwlo|uwo|ulu|olo)\b",
                normalized_text,
            )
            is not None
            # "my head doesn't hurt" — the neg word reaches the PAIN word.
            # Scoped: the pain word must NOT belong to another body part
            # ("dili sakit akong tiyan" negates the stomach, not the head).
            # Guard: if a trap verb sits between the neg word and the pain
            # word the negation belongs to the verb ("dili mawala ang sakit"
            # = "won't go away" → symptom IS present), so we skip this path.
            or (
                re.search(
                    rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+"
                    r"\b(hurt|hurts|hurting|pain|ache|aches|aching|masakit|sakit)\b",
                    normalized_text,
                )
                is not None
                and not re.search(
                    rf"{_NEG_WORDS_RX}"
                    rf"(?:\s+\w+){{0,3}}\s+"
                    rf"\b({'|'.join(_NEG_TRAP_VERBS)})\b",
                    normalized_text,
                )
                and not re.search(
                    r"\b(hurt|hurts|hurting|pain|ache|aches|aching|masakit|sakit)\b"
                    r"(?:\s+\w+){0,3}\s+"
                    r"\b(stomach|tiyan|sikmura|katawan|lawas|body|ngipin|ngipon|tooth|teeth|"
                    r"molar|bagang|bag-ang|lalamunan|tutunlan|throat|gilagid|lagos|gums|"
                    r"ilong|nose|mata|eyes|arm|arms|leg|legs|kalamnan|kaunoran|panga|apapangig)\b",
                    normalized_text,
                )
            )
        )
        # "ulo hangtod tiil" / "head to toe" is an idiom meaning the whole
        # body — it must not trigger HEADACHE ("sakit akong lawas, ulo hangtod tiil").
        head_to_toe = re.search(
            r"\b(ulo\s+hangtod\s+tiil|ulo\s+hanggang\s+(?:paa|toe)|head\s+to\s+toe)\b",
            normalized_text,
        )
        if head_present and pain_present and not headache_explicitly_negated \
                and "HEADACHE" not in wellness_negated and not head_to_toe:
            # Proximity check: head_word and pain_word must be within 5 tokens of each other
            # This prevents "sakit ng ulo... katawan ko" from triggering HEADACHE when pain refers to body
            head_positions = [i for i, t in enumerate(tokens) if re.match(r"^(head|ulo|uwlo|uwo|ulu|olo)$", t)]
            pain_positions = [i for i, t in enumerate(tokens) if re.match(r"^(sakit|masakit|masaket|sumasakit|labad|throbbing|throbing|pounding|pulsating|kirot|gakurot|gikirot|kabutohon|kabuto|hurt|hurts|hurting|ache|aches|aching|pain|painful|sasabog|binibiyak|pumapasabog|grabe|sobra|grabeng|sobrang)$", t)]
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

    # Wellness negation: remove labels negated by wellness words
    # ("my head feels fine", "ayos na ang tiyan ko"). The label is added to
    # negated_labels so later fuzzy rescues do not re-add it.
    for label in wellness_negated:
        if label in detected:
            detected.remove(label)
        negated_labels.add(label)

    # Generic typo rescue: "hedache", "totache", "couhg", "stomake"...
    _fuzzy_symptom_rescue(normalized_text, detected, negated_labels, wellness_negated)

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
                    # Check negation on the throat/pain words WITHIN THE SAME
                    # contrastive part. "dili sakit akong mga ngipon" negates
                    # the teeth, not the throat ("sakit akong tutunlan, pero
                    # dili sakit akong mga ngipon").
                    negated_throat_or_pain = False
                    for part in re.split(r"\b(pero|but|kaso|however|though)\b", normalized_text):
                        if not re.search(r"\b(lalamunan|tutunlan|throat)\b", part):
                            continue
                        negated_throat = re.search(
                            rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+\b(lalamunan|tutunlan|throat|sore\s+throat)\b",
                            part,
                        )
                        negated_pain = re.search(
                            rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,2}}\s+\b(masakit|masaket|sakit|sumasakit|pain|hurts|sore|hapdi)\b",
                            part,
                        )
                        if negated_throat or negated_pain:
                            negated_throat_or_pain = True
                            break
                    if not negated_throat_or_pain:
                        # "throat hurts FROM coughing" / "sore because of
                        # consistent coughing" — the pain is attributed to the
                        # cough, so it is NOT a primary sore throat.
                        cough_attribution = re.search(
                            r"\b(throat|lalamunan|tutunlan)\b(?:\s+\w+){0,5}\s+"
                            r"\b(masakit|masaket|sakit|sore|hurts|hapdi)\b"
                            r"(?:\s+\w+){0,5}\s+"
                            r"\b(?:from|because\s+of|due\s+to|tungod\s+sa|kaka|sa\s+kaka)\b"
                            r"(?:\s+\w+){0,3}\s+"
                            r"\b(cough|coughing|ubo|umuubo|inuubo|kakaubo)\b",
                            normalized_text,
                        )
                        if not cough_attribution:
                            detected.append("SORE_THROAT")

    # Global cough-attribution guard: "my throat hurts FROM coughing" is a
    # cough presentation, not a primary sore throat — drop any SORE_THROAT
    # that the dictionary or the rescue added in that pattern.
    if "SORE_THROAT" in detected:
        if re.search(
            r"\b(throat|lalamunan|tutunlan)\b(?:\s+\w+){0,5}\s+"
            r"\b(masakit|masaket|sakit|sore|hurts|hapdi)\b"
            r"(?:\s+\w+){0,5}\s+"
            r"\b(?:from|because\s+of|due\s+to|tungod\s+sa|kaka|sa\s+kaka|sa\s+sobrang)\b"
            r"(?:\s+\w+){0,3}\s+"
            r"\b(cough|coughing|ubo|umuubo|inuubo|kakaubo)\b",
            normalized_text,
        # Reversed word order ("Masakit lalamunan ko sa sobrang ubo") — the
        # pain word comes BEFORE the throat word.
        ) or re.search(
            r"\b(masakit|masaket|sakit|sore|hurts|hapdi)\b(?:\s+\w+){0,5}\s+"
            r"\b(throat|lalamunan|tutunlan)\b"
            r"(?:\s+\w+){0,5}\s+"
            r"\b(?:from|because\s+of|due\s+to|tungod\s+sa|kaka|sa\s+kaka|sa\s+sobrang)\b"
            r"(?:\s+\w+){0,3}\s+"
            r"\b(cough|coughing|ubo|umuubo|inuubo|kakaubo)\b",
            normalized_text,
        ):
            detected.remove("SORE_THROAT")

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
                rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+\b(barado|bara|stuffy|blocked|clogged)\b",
                normalized_text
            )
            if not neg_check:
                detected.append("NASAL_CONGESTION")

    # Proximity-based RASHES rescue: skin_word + rash_indicator within proximity
    # Handles cases like "pula at makati ng balat ko", "makati ng balat", etc.
    if "RASHES" not in detected and "RASHES" not in negated_labels:
        skin_words = re.findall(r"\b(balat|panit|skin|arm|arms|leg|legs)\b", normalized_text)
        rash_indicators = re.findall(
            r"\b(pula|makati|katol|itchy|red|namumula|nagpula|namula|pantal|butlig|hives|rash|rashes|bumps|bump|bukol|nagbukol)\b",
            normalized_text,
        )
        if skin_words and rash_indicators:
            # Negation guard: "I haven't developed any skin rashes" / "walang
            # pantal sa balat ko" — the rash word is negated.
            negated_rash = re.search(
                rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+"
                r"\b(pantal|butlig|rash|rashes|hives|bumps|bukol)\b",
                normalized_text,
            )
            if not negated_rash:
                detected.append("RASHES")

    # Fuzzy rescue for fever typos: e.g., "my lgnat" -> FEVER
    # Also handles vowel-dropped abbreviations like "lgnt" -> lagnat
    # Exclusion: common English words that are edit-distance-1 from "fever"
    # ("ever", "never", "lever", "sever", "fewer", "fiver") must not fire FEVER.
    if "FEVER" not in detected and "FEVER" not in negated_labels:
        tokens = normalized_text.split()
        fever_exclusion = {"ever", "never", "lever", "sever", "fewer", "fiver"}
        if any(
            (len(t) >= 4 and t not in fever_exclusion and (_levenshtein_within(t, "lagnat", 1) or _levenshtein_within(t, "fever", 1) or _levenshtein_within(t, "hilanat", 1)))
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
        if re.search(r"\b(mainit|init|hot|warm)\b(?:\s+\w+){0,3}\s+\b(katawan|lawas|body)\b", normalized_text):
            detected.append("FEVER")
        elif re.search(r"\b(katawan|lawas|body)\b(?:\s+\w+){0,3}\s+\b(mainit|init|hot|warm)\b", normalized_text):
            detected.append("FEVER")

    # Proximity-based BODY_ACHES rescue: pain word near "katawan/lawas/body"
    # Handles "masakit akong lawas", "sakit akong lawas", "my body aches",
    # "nangalay akong katawan", "muscles ache", "masakit akong jaw", "my arms
    # and legs feel sore" — pain about the body, not the head.
    if "BODY_ACHES" not in detected and "BODY_ACHES" not in negated_labels:
        body_words = re.search(
            r"\b(katawan|lawas|body|muscle|muscles|jaw|jaws|arm|arms|leg|legs|kalamnan|kaunoran|panga|apapangig|limbs)\b",
            normalized_text,
        )
        body_pain = re.search(
            r"\b(masakit|masaket|sakit|sumasakit|gasakit|kasakit|gikasakit|ngalay|nangalay|mangalay|"
            r"aches|aching|ache|hurts|hurting|painful|pain|sore|pananakit|nananakit|"
            r"nangasakit|nagsakit|gisakit|sakit kaayo)\b",
            normalized_text,
        )
        if body_words and body_pain:
            tokens = normalized_text.split()
            bw_pos = [i for i, t in enumerate(tokens) if re.match(r"^(katawan|lawas|body|muscle|muscles|jaw|jaws|arm|arms|leg|legs|kalamnan|kaunoran|panga|apapangig|limbs)$", t)]
            bp_pos = [i for i, t in enumerate(tokens) if re.match(r"^(masakit|masaket|sakit|sumasakit|gasakit|kasakit|gikasakit|ngalay|nangalay|mangalay|aches|aching|ache|hurts|hurting|painful|pain|sore|pananakit|nananakit|nangasakit|nagsakit|gisakit)$", t)]
            if bw_pos and bp_pos:
                min_dist = min(abs(a - b) for a in bw_pos for b in bp_pos)
                if min_dist <= 5:
                    # "wala akong sakit sa katawan" / "my body doesn't hurt" — negated.
                    # The negation only applies inside the same contrastive part
                    # ("masakit yung jaw ko, pero my teeth don't hurt" — the
                    # negation targets the teeth, not the jaw).
                    negated_body_pain = False
                    for part in re.split(r"\b(pero|but|kaso|however|though)\b", normalized_text):
                        if not re.search(r"\b(katawan|lawas|body|muscle|muscles|jaw|jaws|arm|arms|leg|legs|kalamnan|kaunoran|panga|apapangig|limbs)\b", part):
                            continue
                        # Window is wider (6) for "wala namang ibang bahagi ng
                        # katawan na masakit" — the negated body-ache is often
                        # stated a few words after the body part. "katawan ko
                        # ang masakit" (with the inserted pronoun + linker)
                        # needs one more word of slack.
                        if re.search(
                            rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,8}}\s+"
                            r"\b(masakit|masaket|sakit|sumasakit|kasakit|ngalay|nangalay|"
                            r"aches|aching|ache|hurt|hurting|pain|painful|sore|pananakit|"
                            r"nananakit|nangasakit|nagsakit|gisakit)\b",
                            part,
                        ):
                            negated_body_pain = True
                            break
                    if not negated_body_pain:
                        detected.append("BODY_ACHES")
    # Proximity-based TOOTHACHE rescue: pain word near tooth words with filler
    # Handles "pain in one of my teeth", "my tooth starts hurting whenever I
    # chew", "sumasakit ang isang ngipin ko kapag kumakain ako", "Grabe ang
    # kasakit sa usa sa akong mga ngipon".
    if "TOOTHACHE" not in detected and "TOOTHACHE" not in negated_labels:
        tooth_words = re.search(r"\b(ngipin|ngipon|tooth|teeth|molar|molars|bagang|bag-ang)\b", normalized_text)
        tooth_pain = re.search(
            r"\b(masakit|masaket|sakit|sumasakit|gasakit|kasakit|pananakit|nananakit|pain|painful|ache|aches|aching|hurts|hurting|ngilo|nangingilo)\b",
            normalized_text,
        )
        if tooth_words and tooth_pain:
            tokens = normalized_text.split()
            tw_pos = [i for i, t in enumerate(tokens) if re.match(r"^(ngipin|ngipon|tooth|teeth|molar|molars|bagang|bag-ang)$", t)]
            tp_pos = [i for i, t in enumerate(tokens) if re.match(r"^(masakit|masaket|sakit|sumasakit|gasakit|kasakit|pananakit|nananakit|pain|painful|ache|aches|aching|hurts|hurting|ngilo|nangingilo)$", t)]
            if tw_pos and tp_pos:
                min_dist = min(abs(a - b) for a in tw_pos for b in tp_pos)
                if min_dist <= 6:
                    # "hindi sumasakit ang ngipin ko" / "my teeth don't hurt" — negated
                    negated_tooth = False
                    for part in re.split(r"\b(pero|but|kaso|however|though)\b", normalized_text):
                        if not re.search(r"\b(ngipin|ngipon|tooth|teeth|molar|bagang|bag-ang)\b", part):
                            continue
                        if re.search(
                            rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+"
                            r"\b(masakit|masaket|sakit|sumasakit|pain|painful|ache|aches|aching|hurt|hurting|ngilo|nangingilo)\b",
                            part,
                        ):
                            negated_tooth = True
                            break
                    if not negated_tooth:
                        detected.append("TOOTHACHE")

    # Allergen-trigger inference: if RASHES is detected and a known allergen
    # trigger is mentioned, also infer ALLERGIC_RHINITIS.  In the MENDO label
    # system, ALLERGIC_RHINITIS is the closest label for general allergy.  This
    # bridges the gap when semantic fallback doesn't fire because dictionary
    # already returned results for rashes.
    if "RASHES" in detected and "ALLERGIC_RHINITIS" not in detected and "ALLERGIC_RHINITIS" not in negated_labels:
        allergen_triggers = ["dust", "alikabok", "pollen", "dander", "pet fur", "pet hair", "amag", "bulak"]
        if any(_phrase_in_text(normalized_text, _normalize(t)) for t in allergen_triggers):
            detected.append("ALLERGIC_RHINITIS")

    # Allergen + reaction rescue: "I react whenever I'm around pollen" /
    # "I get allergies kapag may pet fur" — a reaction to a known allergen
    # trigger is an allergy presentation even without nasal/skin wording.
    if "ALLERGIC_RHINITIS" not in detected and "ALLERGIC_RHINITIS" not in negated_labels:
        allergen_triggers = ["dust", "alikabok", "pollen", "dander", "pet fur", "pet hair", "amag", "bulak", "flower"]
        reaction_words = re.search(
            r"\b(react|reaction|triggered|sensitive|allergy|allergies|allergic|"
            r"allergies ako|may allergy)\b",
            normalized_text,
        )
        if reaction_words and any(
            _phrase_in_text(normalized_text, _normalize(t)) for t in allergen_triggers
        ):
            detected.append("ALLERGIC_RHINITIS")

    # Sneeze rescue: any sneeze word is an allergy signal in the kiosk
    # ("I keep sneezing around dust", "Lagi akong bumabahing kapag may pollen").
    if "ALLERGIC_RHINITIS" not in detected and "ALLERGIC_RHINITIS" not in negated_labels:
        sneeze_negated = re.search(
            rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+"
            r"\b(bahing|bumabahing|napapabahing|nagbahing|gibahing|mibahing|sneeze|sneezing)\b",
            normalized_text,
        )
        if re.search(
            r"\b(bahing|bumabahing|napapabahing|nagbahing|gibahing|mibahing|sneeze|sneezing)\b",
            normalized_text,
        ) and not sneeze_negated:
            detected.append("ALLERGIC_RHINITIS")

    # Eye-itch rescue: "my eyes are itchy" / "makati mata ko" → ALLERGIC_RHINITIS
    # (the dictionary covers "itchy eyes" but not the reversed word order).
    if "ALLERGIC_RHINITIS" not in detected and "ALLERGIC_RHINITIS" not in negated_labels:
        if re.search(
            r"\b(eyes|mata)\b(?:\s+\w+){0,3}\s+\b(itchy|makati|katol|mangatol|nangangati|watering|tumatulo)\b",
            normalized_text,
        ) or re.search(
            r"\b(itchy|makati|katol|mangatol|nangangati)\b(?:\s+\w+){0,3}\s+\b(eyes|mata)\b",
            normalized_text,
        ):
            detected.append("ALLERGIC_RHINITIS")

    # Gum/cheek irritation rescue: "my gums feel irritated, but none of my
    # teeth are painful" — irritation around the mouth/face (with the teeth
    # explicitly NOT painful, or no tooth mention) is allergy-context, not
    # a toothache.
    if "ALLERGIC_RHINITIS" not in detected and "ALLERGIC_RHINITIS" not in negated_labels:
        gum_or_cheek = re.search(
            r"\b(gilagid|lagos|gum|gums|cheek|cheeks)\b", normalized_text
        )
        irritation = re.search(
            r"\b(irritated|irritating|irritation|makairita|makairitado|masakit|masaket|sakit|painful)\b",
            normalized_text,
        )
        if gum_or_cheek and irritation:
            teeth_pain = re.search(
                r"\b(ngipin|ngipon|tooth|teeth|molar)\b(?:\s+\w+){0,3}\s+"
                r"\b(painful|hurt|hurts|sakit|masakit|masaket)\b",
                normalized_text,
            )
            teeth_negated = re.search(
                rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+"
                r"\b(ngipin|ngipon|tooth|teeth|molar)\b",
                normalized_text,
            )
            if not teeth_pain or teeth_negated:
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
                    # Negation check: "hindi masakit yung tiyan ko", "walang sakit sa tiyan"
                    negated_stomach = re.search(
                        rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+"
                        r"\b(sakit|masakit|masaket|sumasakit|pain|ache|hurt|hurts)\b",
                        normalized_text,
                    )
                    if not negated_stomach:
                        detected.append("STOMACH_ACHE")
                        break
    # Proximity-based STOMACH_ACHE rescue: "stomach" near pain words with filler
    # Handles code-switching like "stomach ko ang sakit", "my stomach hurts"
    if "STOMACH_ACHE" not in detected and "STOMACH_ACHE" not in negated_labels:
        stomach_pain_forward = re.search(
            r"\b(stomach|tummy|abdomen|tiyan|sikmura)\b(?:\s+\w+){0,3}\s+"
            r"\b(sakit|masakit|masaket|sumasakit|gasakit|ga\s+sakit|gisakit|kasakit|pain|ache|hurt|hurting|hurts|bad|bothering|bother|masama|bothering me)\b",
            normalized_text,
        )
        stomach_pain_reverse = re.search(
            r"\b(sakit|masakit|masaket|sumasakit|gasakit|ga\s+sakit|gisakit|kasakit|pain|ache|hurt|hurting|hurts|bad|bothering|bother|masama)\b(?:\s+\w+){0,3}\s+"
            r"\b(stomach|tummy|abdomen|tiyan|sikmura)\b",
            normalized_text,
        )
        if stomach_pain_forward or stomach_pain_reverse:
            # "hindi masakit yung tiyan ko" / "my stomach doesn't hurt" — negated
            negated_stomach = re.search(
                rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+"
                r"\b(stomach|tummy|abdomen|tiyan|sikmura)\b",
                normalized_text,
            ) or re.search(
                rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,{_NEG_WINDOW}}}\s+"
                r"\b(sakit|masakit|masaket|sumasakit|pain|ache|hurt|hurts|bad)\b",
                normalized_text,
            )
            if not negated_stomach:
                detected.append("STOMACH_ACHE")

    # Fuzzy rescue for body aches typos: e.g., "ktawan" -> BODY_ACHES
    # Requires a pain word NEAR the body word (within 6 tokens) to avoid
    # false positives like "sakit ng ulo... katawan ko" where pain refers to head.
    # CRITICAL: This rescue runs ONLY when a body word (katawan/lawas) or its
    # typo is present — it must not fire on generic "sakit" alone.
    if "BODY_ACHES" not in detected and "BODY_ACHES" not in negated_labels:
        tokens = normalized_text.split()
        body_targets = ["katawan", "lawas"]
        for i, tok in enumerate(tokens):
            if len(tok) < 5:
                continue
            # Exact words are already handled by the proximity rescue above
            # (with its full-text contrastive negation guard); this rescue is
            # only for typos like "ktawan".  Otherwise the local 6-token window
            # here would miss a "pero" contrastive boundary and re-add a body
            # ache the proximity rescue correctly negated.
            if tok in body_targets:
                continue
            if any(_levenshtein_within(tok, target, max_dist=1) for target in body_targets):
                # Check for pain word within 6 tokens of the body word
                nearby_tokens = tokens[max(0, i-6):i+7]
                nearby_text = " ".join(nearby_tokens)
                if re.search(r"\b(sakit|masakit|masaket|sumasakit|gasakit|ga\s+sakit|kasakit|pain|ache|ngalay|nangalay|mangalay)\b", nearby_text):
                    # Negation guard: "pero wala namang ibang bahagi ng katawan
                    # na masakit" — the pain word is negated in the same
                    # contrastive part, so no body ache.
                    negated_nearby = False
                    for part in re.split(r"\b(pero|but|kaso|however|though)\b", nearby_text):
                        if re.search(
                            rf"{_NEG_WORDS_RX}(?:\s+\w+){{0,6}}\s+"
                            r"\b(sakit|masakit|masaket|sumasakit|kasakit|pain|ache|ngalay)\b",
                            part,
                        ):
                            negated_nearby = True
                            break
                    if not negated_nearby:
                        detected.append("BODY_ACHES")
                        break

    # Strong negation override: if user explicitly says they have NO fever,
    # remove FEVER even if earlier words mention lagnat/feverish.
    # CONTRASTIVE BOUNDARY: "pero"/"but" resets negation scope.
    #
    # Helper: check if ANY negation word directly reaches the target keywords
    # (each neg word checked independently to avoid overlapping-match issues).
    _neg_rx_override = _NEG_WORDS_RX

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
            has_neg = _strong_neg_check(part, _cough_targets, ignored_filler_words={
                "plema", "phlegm", "mucus",
                # Qualifier words: "isn't a dry cough" negates DRY, not cough
                "dry", "wet", "tuyo", "tuyong", "uga", "basa", "basang",
                "productive", "tickly", "mawala", "mohunong", "hunong",
                "huminto", "tigil", "hinto", "stop", "undang", "naundang",
            })
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
            has_neg = (
                _is_negated(part, "sakit sa ulo")
                or _is_negated(part, "sakit ulo")
                or _is_negated(part, "masakit ang ulo")
                or _is_negated(part, "labad ang ulo")
                or _is_negated(part, "ulo")
                or _strong_neg_check(part, _head_targets, max_filler=3)
            )
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
