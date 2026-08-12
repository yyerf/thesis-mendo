"""headache_intake.py

Deterministic free-text headache-type intake.

Lets a typed symptom description ("sinus", "sinusitis", "deep constant
pressure behind my cheeks and forehead", "squeezing dull ache from stress",
"high blood") route straight to one of the 14 clinical headache types in
headache_locations.py — the same types the kiosk's clickable head-map
already exposes (danger zone, prefer/avoid categories, safety notes).

Design (precision-first, mirrors the rest of Mendo):
  - Layer 1: exact multilingual tag matching (strong vs weak). Strong tags
    are diagnostic; weak tags only confirm a strong match or resolve on
    their own when the choice is unambiguous.
  - Red-zone resolution: any matched red-zone type (thunderclap, hypertension,
    spinal, post-traumatic, exertion) dominates and is returned immediately —
    free text can thus auto-trigger the emergency/referral path.
  - No ML, no model load. Runs in microseconds. A closed-set semantic
    classifier over the 14 descriptions can be fitted later if desired.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

from .headache_locations import HEADACHE_TYPES, get_location

# Red-zone types; earlier entry wins when several match at once.
RED_PRIORITY: List[str] = [
    "thunderclap",
    "hypertension",
    "spinal",
    "post_traumatic",
    "exertion",
]


def _normalize(text: str) -> str:
    """Lowercase, de-leetspeak, strip punctuation (mirrors step3._normalize)."""
    text = (text or "").lower().strip()
    text = text.translate(
        str.maketrans(
            {
                "@": "a", "0": "o", "1": "i", "3": "e", "4": "a",
                "5": "s", "7": "t", "8": "b", "$": "s", "!": "i", "|": "i",
            }
        )
    )
    text = re.sub(r"[^a-z0-9ñ\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


class _Tag:
    __slots__ = ("key", "strong", "phrase")

    def __init__(self, key: str, strong: bool, phrase: str) -> None:
        self.key = key
        self.strong = strong
        self.phrase = phrase


_INDEX: List[_Tag] = []
_ORDER: Dict[str, int] = {}


def _build_index() -> None:
    global _INDEX, _ORDER
    if _INDEX:
        return
    for idx, ht in enumerate(HEADACHE_TYPES):
        _ORDER[ht.key] = idx
        for phrase in ht.tags_strong:
            if phrase:
                _INDEX.append(_Tag(ht.key, True, _normalize(phrase)))
        for phrase in ht.tags_weak:
            if phrase:
                _INDEX.append(_Tag(ht.key, False, _normalize(phrase)))


_build_index()


def _matches(phrase: str, nt: str) -> bool:
    if " " in phrase:
        return phrase in nt
    return re.search(rf"\b{re.escape(phrase)}\b", nt) is not None


_NEGATION_WORDS = (
    "wala", "walang", "walay", "no", "not", "without",
    "dili", "di", "hindi", "hnd",
)


def has_negation_cue(user_input: str) -> bool:
    """True if the text contains a negation word anywhere."""
    nt = _normalize(user_input)
    return bool(re.search(rf"\b({'|'.join(_NEGATION_WORDS)})\b", nt))


def promote_bare_headache_cue(user_input: str) -> Optional[Dict[str, object]]:
    """Promote a bare headache-type cue to a headache consult.

    Handles inputs like "sinus", "sinusitis", "tension", "high blood",
    "cluster" — a type word with no accompanying symptom word at all.
    Only strong-tag or red-zone types qualify (weak-only cues like "stress"
    are too ambiguous), and negated statements are never promoted.
    Returns the intake dict, or None when there is nothing to promote.
    """
    if has_negation_cue(user_input):
        return None
    probe = classify_headache_text(user_input)
    if not probe.get("matched"):
        return None
    if probe.get("resolution") not in ("strong_match", "red_zone"):
        return None
    return probe


def classify_headache_text(
    user_input: str,
    user_age: Optional[int] = None,
) -> Dict[str, object]:
    """Classify a free-text headache description into a headache type.

    Args:
        user_input: the raw user sentence.
        user_age: optional patient age (reserved for future rules).

    Returns a dict:
        {
          "matched": bool,          # True iff a type was inferred
          "key": str | None,        # headache type key
          "danger": str | None,     # "safe" | "caution" | "red_flag" | None
          "resolution": str,        # "red_zone" | "strong_match" | "weak_match"
                                    #   | "ambiguous" | "none"
          "matched_strong": [...],  # strong tag phrases that hit
          "matched_weak": [...],    # weak tag phrases that hit
          "candidates": [...],      # every matched type w/ its tags + danger
        }
    """
    nt = _normalize(user_input)
    none_result = {
        "matched": False,
        "key": None,
        "danger": None,
        "resolution": "none",
        "matched_strong": [],
        "matched_weak": [],
        "candidates": [],
    }
    if not nt:
        return none_result

    candidates: Dict[str, Dict[str, object]] = {}
    for tag in _INDEX:
        if not _matches(tag.phrase, nt):
            continue
        bucket = candidates.setdefault(
            tag.key, {"strong": [], "weak": [], "danger": get_location(tag.key).danger}
        )
        bucket["strong" if tag.strong else "weak"].append(tag.phrase)  # type: ignore[index]

    if not candidates:
        return none_result

    def _result(winner: str, resolution: str) -> Dict[str, object]:
        win = candidates[winner]
        return {
            "matched": True,
            "key": winner,
            "danger": win["danger"],
            "resolution": resolution,
            "matched_strong": list(win["strong"]),
            "matched_weak": list(win["weak"]),
            "candidates": [
                {
                    "key": key,
                    "strong": list(data["strong"]),
                    "weak": list(data["weak"]),
                    "danger": data["danger"],
                }
                for key, data in candidates.items()
            ],
        }

    # Red-zone dominates regardless of how it was matched.
    reds = [key for key in candidates if get_location(key).danger == "red_flag"]
    if reds:
        reds.sort(key=lambda k: RED_PRIORITY.index(k) if k in RED_PRIORITY else 99)
        return _result(reds[0], "red_zone")

    # Strong matches first: pick best by (strong_count, weak_count, type order).
    strong_keys = [k for k, v in candidates.items() if v["strong"]]
    if strong_keys:
        strong_keys.sort(
            key=lambda k: (
                len(candidates[k]["strong"]),
                len(candidates[k]["weak"]),
                -_ORDER[k],
            ),
            reverse=True,
        )
        return _result(strong_keys[0], "strong_match")

    # Weak-only: predicate is a single unique candidate.
    if len(candidates) == 1:
        key = next(iter(candidates))
        return _result(key, "weak_match")

    return {
        "matched": False,
        "key": None,
        "danger": None,
        "resolution": "ambiguous",
        "matched_strong": [],
        "matched_weak": [],
        "candidates": [
            {
                "key": key,
                "strong": list(data["strong"]),
                "weak": list(data["weak"]),
                "danger": data["danger"],
            }
            for key, data in candidates.items()
        ],
    }


if __name__ == "__main__":
    import doctest

    print("self-check: loading tags from", len(HEADACHE_TYPES), "types,", len(_INDEX), "tags")
    doctest.testmod()