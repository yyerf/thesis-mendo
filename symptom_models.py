"""Symptom spotting models + shared utilities.

This module is intentionally lightweight so you can benchmark multiple approaches
without changing the dataset or evaluation code.

Model contract: given a text input, return a set of canonical symptom labels.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Set


def normalize_text(text: str) -> str:
    text = (text or "").strip().lower()
    # keep apostrophes for contractions, remove most punctuation
    text = re.sub(r"[^a-z0-9\s'ñ]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


# Canonical symptom -> regex patterns (English + Filipino + common slang)
SYMPTOM_PATTERNS: Dict[str, List[str]] = {
    "cough": [
        r"\bcough\b",
        r"\bcoughing\b",
        r"\bubo\b",
        r"\binuubo\b",
        r"\bu-?bo\b",
    ],
    "headache": [
        r"\bheadache\b",
        r"\bhead ache\b",
        r"\bmasakit ulo\b",
        r"\bsakit ulo\b",
        r"\bsumasakit ulo\b",
        r"\bkirot ulo\b",
    ],
    "fever": [
        r"\bfever\b",
        r"\blagnat\b",
        r"\bmay lagnat\b",
        r"\bmainit\b",
        r"\bininit\b",
    ],
    "sore_throat": [
        r"\bsore throat\b",
        r"\bthroat pain\b",
        r"\bmasakit lalamunan\b",
        r"\bsakit lalamunan\b",
        r"\bmakati lalamunan\b",
    ],
    "runny_nose": [
        r"\brunny nose\b",
        r"\bsipon\b",
        r"\bmay sipon\b",
        r"\btumutulo ilong\b",
    ],
    "stuffy_nose": [
        r"\bstuffy nose\b",
        r"\bnasal congestion\b",
        r"\bbarado ilong\b",
        r"\bbarado ang ilong\b",
    ],
    "dizziness": [
        r"\bdizzy\b",
        r"\bdizziness\b",
        r"\bhilo\b",
        r"\bnahihilo\b",
        r"\bhilong-hilo\b",
    ],
    "nausea": [
        r"\bnausea\b",
        r"\bnauseous\b",
        r"\bnaduduwal\b",
        r"\bduduwal\b",
        r"\bnasusuka\b",
    ],
    "vomiting": [
        r"\bvomit\b",
        r"\bvomiting\b",
        r"\bpagsusuka\b",
        r"\bsuka\b",
        r"\bsumusuka\b",
    ],
    "diarrhea": [
        r"\bdiarrhea\b",
        r"\bloose stool\b",
        r"\bnagtatae\b",
        r"\btae\b",
        r"\bnaliligo sa cr\b",
    ],
    "fatigue": [
        r"\bfatigue\b",
        r"\btired\b",
        r"\bpagod\b",
        r"\bkapoy\b",
        r"\bhina\b",
    ],
    "body_aches": [
        r"\bbody ache\b",
        r"\bbody aches\b",
        r"\bmuscle pain\b",
        r"\bmasakit katawan\b",
        r"\bsakit katawan\b",
        r"\bngalay\b",
    ],
    "shortness_of_breath": [
        r"\bshortness of breath\b",
        r"\bshort of breath\b",
        r"\bhirap huminga\b",
        r"\bhingal\b",
        r"\bnahihirapan huminga\b",
    ],
    "chest_pain": [
        r"\bchest pain\b",
        r"\bsakit dibdib\b",
        r"\bmasakit dibdib\b",
    ],
    "stomach_ache": [
        r"\bstomach ache\b",
        r"\bstomach pain\b",
        r"\bmasakit tiyan\b",
        r"\bsakit tiyan\b",
        r"\btiyan\b",
    ],
}

SYMPTOM_LABELS: List[str] = sorted(SYMPTOM_PATTERNS.keys())


@dataclass(frozen=True)
class SymptomHit:
    symptom: str
    matches: List[str]


class SymptomModel(Protocol):
    name: str

    def predict(self, text: str) -> Set[str]:
        """Return a set of canonical symptom labels."""


class RuleRegexModel:
    """Language-agnostic-ish rules via regex patterns."""

    def __init__(self, patterns: Optional[Mapping[str, Sequence[str]]] = None, name: str = "rules") -> None:
        self.name = name
        self._patterns: Mapping[str, Sequence[str]] = patterns or SYMPTOM_PATTERNS

    def spot(self, text: str) -> List[SymptomHit]:
        normalized = normalize_text(text)
        hits: List[SymptomHit] = []

        for symptom, patterns in self._patterns.items():
            matches: List[str] = []
            for pat in patterns:
                if re.search(pat, normalized):
                    matches.append(pat)
            if matches:
                hits.append(SymptomHit(symptom=symptom, matches=matches))

        return hits

    def predict(self, text: str) -> Set[str]:
        return {h.symptom for h in self.spot(text)}


class EnglishOnlyRegexModel(RuleRegexModel):
    """Baseline: only English patterns, for comparison."""

    def __init__(self) -> None:
        english_only: Dict[str, List[str]] = {
            "cough": [r"\\bcough\\b", r"\\bcoughing\\b"],
            "headache": [r"\\bheadache\\b", r"\\bhead ache\\b"],
            "fever": [r"\\bfever\\b"],
            "sore_throat": [r"\\bsore throat\\b", r"\\bthroat pain\\b"],
            "runny_nose": [r"\\brunny nose\\b"],
            "stuffy_nose": [r"\\bstuffy nose\\b", r"\\bnasal congestion\\b"],
            "dizziness": [r"\\bdizzy\\b", r"\\bdizziness\\b"],
            "nausea": [r"\\bnausea\\b", r"\\bnauseous\\b"],
            "vomiting": [r"\\bvomit\\b", r"\\bvomiting\\b"],
            "diarrhea": [r"\\bdiarrhea\\b", r"\\bloose stool\\b"],
            "fatigue": [r"\\bfatigue\\b", r"\\btired\\b"],
            "body_aches": [r"\\bbody ache\\b", r"\\bbody aches\\b", r"\\bmuscle pain\\b"],
            "shortness_of_breath": [r"\\bshortness of breath\\b", r"\\bshort of breath\\b"],
            "chest_pain": [r"\\bchest pain\\b"],
            "stomach_ache": [r"\\bstomach ache\\b", r"\\bstomach pain\\b"],
        }
        super().__init__(patterns=english_only, name="english_rules")


def available_models() -> List[str]:
    return ["rules", "english_rules"]


def get_model(model_id: str) -> SymptomModel:
    model_id = (model_id or "").strip().lower()
    if model_id in {"rules", "regex", "rule", "default"}:
        return RuleRegexModel()
    if model_id in {"english_rules", "english", "en"}:
        return EnglishOnlyRegexModel()

    raise ValueError(f"Unknown model '{model_id}'. Available: {', '.join(available_models())}")
