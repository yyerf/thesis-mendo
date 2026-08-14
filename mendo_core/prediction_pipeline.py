"""Single, versioned symptom-prediction service used by web and benchmarks.

The service is intentionally descriptive: Mendo is a deterministic expert
system assisted by a pretrained sentence-embedding model. Similarity scores
are cosine similarities, not calibrated probabilities.
"""

from __future__ import annotations

from copy import deepcopy
import os
import re
from typing import Any, Dict, Optional

from .medicine_catalog import MEDICINE_CATALOG_VERSION
from .step2 import SYMPTOM_ANCHORS
from .step3_hybrid import extract_symptoms_hybrid_report

ENGINE_ID = "mendo-expert-minilm-v3.2"
TRACE_SCHEMA_VERSION = 2
SEMANTIC_MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SEMANTIC_THRESHOLD = 0.65
SEMANTIC_TOP_MARGIN = 0.08
SEMANTIC_MAX_SYMPTOMS = 2
DICTIONARY_CORROBORATION_THRESHOLD = 0.40


def _semantic_backend_info() -> Dict[str, str]:
    """Engine metadata for the audit trace — mirrors _get_semantic_extractor()."""
    backend = os.getenv("MENDO_SEMANTIC_BACKEND", "minilm").strip().lower()
    if backend == "minilm":
        return {
            "engine_id": ENGINE_ID,
            "semantic_model_id": SEMANTIC_MODEL_ID,
            "semantic_score_type": "cosine_similarity",
        }
    return {
        "engine_id": "mendo-expert-sailor2-v1",
        "semantic_model_id": os.getenv("MENDO_LLM_MODEL", "sailor2:1b"),
        "semantic_score_type": "constrained_decode_emission",
    }


def predict_symptoms(user_input: str) -> Dict[str, Any]:
    """Return deployed symptom predictions and an auditable decision trace."""
    report = extract_symptoms_hybrid_report(
        user_input,
        semantic_threshold=SEMANTIC_THRESHOLD,
        semantic_top_margin=SEMANTIC_TOP_MARGIN,
        semantic_max_symptoms=SEMANTIC_MAX_SYMPTOMS,
        enable_semantic_fallback=True,
    )
    _apply_expert_disambiguation(user_input, report)
    trace = deepcopy(report)
    trace["trace_version"] = TRACE_SCHEMA_VERSION
    backend = _semantic_backend_info()
    trace["engine"] = {
        "engine_id": backend["engine_id"],
        "medicine_catalog_version": MEDICINE_CATALOG_VERSION,
        "architecture": "knowledge_based_expert_system_with_pretrained_semantic_component",
        "semantic_model_id": backend["semantic_model_id"],
        "semantic_score_type": backend["semantic_score_type"],
        "semantic_threshold": SEMANTIC_THRESHOLD,
        "dictionary_corroboration_threshold": DICTIONARY_CORROBORATION_THRESHOLD,
        "semantic_top_margin": SEMANTIC_TOP_MARGIN,
        "semantic_max_symptoms": SEMANTIC_MAX_SYMPTOMS,
        "automatically_trained_on_logs": False,
    }

    selected = set(trace.get("final", {}).get("symptoms", []))
    for stage in trace.get("stages", []):
        if stage.get("stage") == "dictionary":
            detected = set(stage.get("detected", []))
            for detail in stage.get("details", []):
                symptom = detail.get("symptom")
                if symptom in detected:
                    detail["decision"] = (
                        "selected" if symptom in selected else "suppressed_by_hybrid_corroboration"
                    )
                else:
                    detail["decision"] = "matched_but_negated_or_safety_suppressed"
        elif stage.get("stage") == "semantic":
            threshold = float(stage.get("threshold", SEMANTIC_THRESHOLD))
            selected_semantic = set(stage.get("detected_selected", []))
            for row in stage.get("scores", []):
                row["score_type"] = backend["semantic_score_type"]
                row["threshold"] = threshold
                if row.get("vetoed"):
                    row["decision"] = row.get("veto_reason", "lexically_vetoed")
                else:
                    row["decision"] = (
                        "selected"
                        if row.get("symptom") in selected_semantic
                        else "below_threshold_or_safety_suppressed"
                    )

    trace["final"]["decisions"] = [
        {
            "symptom": symptom,
            "decision": "selected",
            "reason": _selection_reason(symptom, trace.get("stages", [])),
        }
        for symptom in trace.get("final", {}).get("symptoms", [])
    ]

    _attach_semantic_summary(trace, backend)
    return trace


def _attach_semantic_summary(trace: Dict[str, Any], backend: Optional[Dict[str, str]] = None) -> None:
    """Attach a compact top-level `semantic` block for the audit trail.

    Honesty rules:
    - The block says `used: False` when the semantic stage did NOT run:
      backend unavailable, or precision-first gating skipped it on a
      dictionary hit (with the skip reason attached).
    - score_type/engine metadata reflect the ACTIVE backend, not a legacy
      MiniLM default.
    """
    backend = backend or _semantic_backend_info()
    semantic_stage = next(
        (s for s in trace.get("stages", []) if s.get("stage") == "semantic"),
        None,
    )
    if not semantic_stage:
        trace["semantic"] = {"used": False}
        return
    if not semantic_stage.get("available"):
        trace["semantic"] = {"used": False, "reason": "backend_unavailable"}
        return
    if not semantic_stage.get("used"):
        trace["semantic"] = {
            "used": False,
            "reason": semantic_stage.get("skipped_reason", "skipped"),
        }
        return

    scores = semantic_stage.get("scores", []) or []
    threshold = float(semantic_stage.get("threshold", SEMANTIC_THRESHOLD))
    selected_names = set(semantic_stage.get("detected_selected", []) or [])
    selected = [
        row
        for row in scores
        if row.get("symptom") in selected_names
    ]
    near_miss = sorted(
        (
            row
            for row in scores
            if row.get("symptom") not in selected_names
            and not row.get("vetoed")
            and float(row.get("score", 0) or 0) > 0
        ),
        key=lambda r: float(r.get("score", 0) or 0),
        reverse=True,
    )[:5]
    vetoed = sorted(
        (row for row in scores if row.get("vetoed")),
        key=lambda r: float(r.get("score", 0) or 0),
        reverse=True,
    )[:5]

    is_minilm = backend["engine_id"] == ENGINE_ID
    trace["semantic"] = {
        "used": True,
        "score_type": backend["semantic_score_type"],
        "comparison": (
            "user_input_embedding_vs_symptom_anchor_sentences"
            if is_minilm
            else "constrained_local_llm_decode_over_13_label_vocabulary"
        ),
        "threshold": threshold,
        "max_symptoms": int(semantic_stage.get("max_symptoms", SEMANTIC_MAX_SYMPTOMS)),
        "anchor_sentences_total": (
            sum(len(phrases) for phrases in SYMPTOM_ANCHORS.values())
            if is_minilm
            else None
        ),
        "anchor_sentences_per_symptom": (
            {symptom: len(phrases) for symptom, phrases in SYMPTOM_ANCHORS.items()}
            if is_minilm
            else None
        ),
        "selected": [
            {
                "symptom": row.get("symptom"),
                "score": float(row.get("score", 0) or 0),
                "threshold": float(row.get("threshold", threshold)),
                "best_anchor": row.get("best_anchor"),
                "decision": row.get("decision", "selected"),
            }
            for row in selected
        ],
        "near_miss_rejected": [
            {
                "symptom": row.get("symptom"),
                "score": float(row.get("score", 0) or 0),
                "threshold": float(row.get("threshold", threshold)),
                "best_anchor": row.get("best_anchor"),
                "decision": row.get("decision", "below_threshold_or_safety_suppressed"),
            }
            for row in near_miss
        ],
        "lexical_guard_vetoed": [
            {
                "symptom": row.get("symptom"),
                "score": float(row.get("score", 0) or 0),
                "threshold": float(row.get("threshold", threshold)),
                "best_anchor": row.get("best_anchor"),
                "veto_reason": row.get("veto_reason", "lexically_vetoed"),
            }
            for row in vetoed
        ],
    }


def _apply_expert_disambiguation(user_input: str, report: Dict[str, Any]) -> None:
    """Resolve known semantic overlaps without conflating distinct labels."""
    # Apostrophes are stripped (not blanked): "isn't" -> "isnt" so that
    # contraction-based negation patterns ("isnt any phlegm") can match.
    text = (user_input or "").lower().replace("'", "")
    text = re.sub(r"[^a-z0-9ñ\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    symptoms = list(report.setdefault("final", {}).get("symptoms", []))
    transformations = report.setdefault("transformations", [])

    def remove(label: str, rule: str) -> None:
        if label in symptoms:
            symptoms.remove(label)
            transformations.append(
                {"rule": rule, "input": label, "output": None, "reason": "expert_disambiguation"}
            )

    def add(label: str, rule: str) -> None:
        if label not in symptoms:
            symptoms.append(label)
            transformations.append(
                {"rule": rule, "input": "explicit_positive_cue", "output": label}
            )

    def positive_in_last_clause(pattern: str) -> bool:
        decisions = []
        for clause in re.split(r"\b(?:pero|but|kaso|however|though)\b", text):
            if not re.search(pattern, clause):
                continue
            negated = re.search(
                rf"\b(wala|walang|walay|no|not|without|dili|di|hindi|hnd)\b"
                rf"(?:\s+\w+){{0,3}}\s+{pattern}",
                clause,
            )
            decisions.append(not bool(negated))
        return decisions[-1] if decisions else False

    # Full cue sets — kept in sync with step1._NASAL_*_CUES so the pipeline
    # never vetoes a label step1 detected on cues this rule doesn't know.
    # "running a fever" is NOT a runny nose.
    _runny_re = (r"\b(sipon|sip on|sip-on|runny|tumatakbo|tumutulo|"
                 r"nagatulo|drip|dripping|tulo|pagtulo|nagtulo|leak|leaking|"
                 r"umaagos|agas|nag-agas|running(?!\s+(?:a|the)\s+fever))\b")
    _blocked_re = (r"\b(barado|bara|stuffy|blocked|clogged|congested|congestion|"
                   r"lisod ginha|lisod ginhawa|lisod kog ginha|lisod kog ginhawa|"
                   r"lisod ko'g ginha|lisod ko'g ginhawa|hard to breathe|difficulty breathing|"
                   r"hard time breathing|trouble breathing|hirap huminga|"
                   r"hirap akong huminga)\b")
    has_runny = bool(re.search(_runny_re, text))
    has_blocked = bool(re.search(_blocked_re, text))
    positive_runny = positive_in_last_clause(_runny_re)
    positive_blocked = positive_in_last_clause(_blocked_re)
    # Bare breathing-difficulty phrases ("hirap huminga", "difficulty
    # breathing") are a TRIAGE red flag, not a nasal symptom — they only
    # count as congestion when anchored to the nose ("hirap huminga sa
    # ilong", "barado ang ilong ko kaya hirap huminga").  The kiosk UI
    # routes bare breathing trouble to emergency triage instead.
    _breathing_only_re = (r"\b(lisod ginha|lisod ginha|lisod kog ginha|lisod kog ginha|"
                          r"lisod ko'g ginha|lisod ko'g ginha|hard to breathe|"
                          r"difficulty breathing|hard time breathing|trouble breathing|"
                          r"hirap huminga|hirap akong huminga)\b")
    _nasal_anchor_re = (r"\b(ilong|nose|barado|bara|stuffy|blocked|clogged|"
                        r"congested|congestion)\b")
    if (
        re.search(_breathing_only_re, text)
        and not re.search(_nasal_anchor_re, text)
    ):
        has_blocked = False
        positive_blocked = False
    # Throat-obstruction context ("ang lalamunan ko ay tila may nakabara na
    # bara") is a SORE_THROAT presentation, not nasal congestion — the
    # blocked-cue rules need a nose word to fire there.
    if (
        has_blocked
        and re.search(r"\b(throat|lalamunan|tutunlan)\b", text)
        and not re.search(_nasal_anchor_re, text)
    ):
        has_blocked = False
        positive_blocked = False

    if has_runny and not has_blocked:
        remove("NASAL_CONGESTION", "runny_cue_does_not_imply_congestion")
        if positive_runny:
            add("RUNNY_NOSE", "explicit_runny_nose_after_contrast")
    if has_blocked and not has_runny:
        remove("RUNNY_NOSE", "congestion_cue_does_not_imply_runny_nose")
        if positive_blocked:
            add("NASAL_CONGESTION", "explicit_congestion_after_contrast")
    # Throat obstruction with NO nose mention is SORE_THROAT territory, not
    # nasal congestion — veto a nasal label the semantic stage guessed on
    # "nakabara na bara" / "blocked throat" phrasing.
    if (
        re.search(r"\b(throat|lalamunan|tutunlan)\b", text)
        and not re.search(r"\b(ilong|nose)\b", text)
    ):
        remove("NASAL_CONGESTION", "throat_context_without_nose_is_not_congestion")

    allergy_explicit = bool(
        re.search(
            r"\b(allergy|allergies|allergic|rhinitis|alerdyi|aalerdyi|react|reacts|reaction)\b",
            text,
        )
    )
    # Sneezing/bahing anywhere is a strong allergy signal in a symptom kiosk
    # ("I keep sneezing around dust", "Lagi akong bumabahing"). Itchy nose/eyes
    # counts too, in either word order ("my nose gets itchy", "itchy yung mata ko").
    allergy_nasal_pattern = bool(
        re.search(r"\b(bahing|bumabahing|napapabahing|nagbahing|gibahing|"
                  r"mibahing|sneeze|sneezing)\b", text)
        or re.search(
            r"\b(makati|katol|itchy|nangangati|mangatol)\b(?:\s+\w+){0,3}\s+\b(ilong|nose|mata|eyes)\b",
            text,
        )
        or re.search(
            r"\b(ilong|nose|mata|eyes)\b(?:\s+\w+){0,3}\s+\b(makati|katol|itchy|nangangati|mangatol)\b",
            text,
        )
        # Irritated gums/cheeks with the teeth explicitly NOT painful is an
        # allergy-context presentation ("my gums feel irritated, but none of
        # my teeth are painful") — step1 labels it ALLERGIC_RHINITIS.
        or (
            re.search(r"\b(gilagid|lagos|gum|gums|cheek|cheeks)\b", text)
            and re.search(
                r"\b(irritated|irritating|irritation|makairita|makairitado|"
                r"masakit|masaket|sakit|painful)\b",
                text,
            )
        )
    )
    if not (allergy_explicit or allergy_nasal_pattern):
        remove("ALLERGIC_RHINITIS", "allergy_requires_explicit_or_nasal_allergy_context")

    # Skin mention counts only when it is a POSITIVE rash mention — "there are
    # no visible rashes" / "walang pantal" is an explicit negation and must not
    # make the allergy context look like a skin presentation.
    negated_rash_mention = bool(
        re.search(
            r"\b(?:no|not|without|never|none|wala|walang|walay|waley|hindi|hnd|di|dili|dli|wara|wa)\b"
            r"(?:\s+\w+){0,3}\s+\b(pantal|rash|rashes|hives|butlig)\b",
            text,
        )
    )
    skin_context = bool(
        re.search(r"\b(pantal|rash|rashes|hives|butlig|balat|panit|braso|skin)\b", text)
    ) and not negated_rash_mention
    nasal_context = bool(
        re.search(
            r"\b(ilong|nose|bahing|bumabahing|napapabahing|nagbahing|gibahing|"
            r"mibahing|sneeze|sneezing|mata|eyes)\b",
            text,
        )
        or re.search(
            r"\b(itchy|makati|katol|nangangati|mangatol)\b(?:\s+\w+){0,3}\s+\b(mata|eyes)\b",
            text,
        )
    )
    if nasal_context and not skin_context:
        remove("RASHES", "nasal_itch_does_not_imply_skin_rash")
    if skin_context and not nasal_context and not allergy_explicit:
        remove("ALLERGIC_RHINITIS", "skin_itch_does_not_imply_allergic_rhinitis")

    pain_context = bool(
        re.search(
            r"\b(masakit|sakit|nanakit|sumasakit|pain|ache|aches|aching|ngalay|"
            r"binugbog|pinukpok|bugat|mabigat|nanghihina|weak|chills)\b",
            text,
        )
    )
    heat_body_context = bool(
        re.search(r"\b(init|mainit|hot|warm)\b(?:\s+\w+){0,3}\s+\b(katawan|lawas|body)\b", text)
    )
    if heat_body_context and not pain_context:
        remove("BODY_ACHES", "body_word_in_temperature_context_is_not_body_ache")

    red_flag_names = {row.get("flag") for row in report.get("red_flags", [])}
    if "blood_vomit" in red_flag_names:
        remove("STOMACH_ACHE", "blood_vomit_is_triage_not_stomach_ache")
    if "severe_allergic_reaction" in red_flag_names:
        remove("SORE_THROAT", "swollen_throat_is_triage_not_sore_throat")

    cough_labels = {"COUGH_GENERAL", "COUGH_DRY", "COUGH_PRODUCTIVE"}
    if cough_labels & set(symptoms):
        # "I don't know if dry or may plema" — the user hasn't decided the
        # cough type; keep the unspecific classification as-is.
        dont_know_cough_type = bool(
            re.search(
                r"\b(?:dont\s+know|di\s+ko\s+alam|hindi\s+ko\s+alam|"
                r"dili\s+ko\s+kahibalo|ambot|not\s+sure)\b",
                text,
            )
            and re.search(r"\b(or|o)\b.*\b(dry|plema|mucus|wet|phlegm|productive)\b", text)
        )
        _cough_neg = r"(wala|walang|walay|waley|no|not|without|dont|doesnt|didnt|isnt|arent|wasnt|havent|hasnt|cant|wont|dili|di|hindi|hnd)"
        if not dont_know_cough_type:
            # "isn't a dry cough" / "hindi tuyong ubo" / "dili uga nga ubo" / "rather
            # than having a dry cough" all negate DRY, not the cough itself.
            dry_phrase_negated = re.search(
                rf"\b{_cough_neg}\b(?:\s+\w+){{0,3}}\s+(?:dry\s+cough|tuyong\s+ubo|uga\s+nga\s+ubo)\b",
                text,
            ) is not None
            dry_phrase_negated = dry_phrase_negated or bool(
                re.search(
                    r"\b(rather\s+than|instead\s+of)\b(?:\s+\w+){0,2}\s+(?:a\s+|an\s+|the\s+)?"
                    r"(?:dry\s+cough|tuyong\s+ubo|uga\s+nga\s+ubo)\b",
                    text,
                )
            )
            dry = bool(
                re.search(
                    r"\b(dry\s+cough|tuyong\s+ubo|uga\s+nga\s+ubo|uga\s+kaayo|"
                    r"ay\s+tuyo|tuyo\s+ang|super\s+dry|very\s+dry|dry\s+at\s+)|"
                    r"\bdry\b(?:\s+\w+){{0,2}}\s+\b(cough|ubo)\b",
                    text,
                )
                # "walang lumalabas na plema" / "wala koy plema nga mogawas" = DRY
                or re.search(
                    rf"\b{_cough_neg}\b(?:\s+\w+){{0,3}}\s+(?:nga\s+|na\s+)?"
                    r"(?:plema|plemang|phlegm|mucus)\b",
                    text,
                )
                or re.search(r"\bnothing\s+(?:comes|coming|is\s+coming)\s+out\b", text)
                or re.search(
                    r"\b(?:without|not|isnt|dont)\b(?:\s+\w+){0,3}\s+"
                    r"bringing\s+up\s+(?:anything|plema|phlegm|mucus)\b",
                    text,
                )
            ) and not dry_phrase_negated
            negated_plema = re.search(
                rf"\b{_cough_neg}\b(?:\s+\w+){{0,3}}\s+(?:nga\s+|na\s+)?"
                r"(?:plema|plemang|phlegm|mucus)\b",
                text,
            ) is not None
            productive = bool(
                re.search(
                    r"\b(plema|plemang|phlegm|mucus|wet\s+cough|productive\s+cough|"
                    r"thick\s+mucus|thick\s+phlegm|baga\s+nga\s+plema|"
                    r"coughing\s+up|brought\s+up)\b",
                    text,
                )
            ) and not negated_plema
            if productive and not dry:
                for label in ("COUGH_GENERAL", "COUGH_DRY"):
                    remove(label, "phlegm_selects_productive_cough")
                add("COUGH_PRODUCTIVE", "phlegm_selects_productive_cough")
            elif dry and not productive:
                for label in ("COUGH_GENERAL", "COUGH_PRODUCTIVE"):
                    remove(label, "dry_cue_selects_dry_cough")
                add("COUGH_DRY", "dry_cue_selects_dry_cough")
            else:
                for label in ("COUGH_DRY", "COUGH_PRODUCTIVE"):
                    remove(label, "generic_cough_requires_clarification")
                add("COUGH_GENERAL", "generic_cough_requires_clarification")

    report["final"]["symptoms"] = list(dict.fromkeys(symptoms))
    if transformations:
        report["final"]["source"] = "expert_rule_adjusted"


def apply_headache_selection(
    trace: Dict[str, Any],
    headache: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply the explicit sinus expert rule and document the transformation."""
    if not headache:
        return trace
    trace = deepcopy(trace)
    trace["headache_selection"] = headache
    transformations = trace.setdefault("transformations", [])
    if headache.get("key") == "sinus":
        symptoms = trace.setdefault("final", {}).setdefault("symptoms", [])
        if "NASAL_CONGESTION" not in symptoms:
            symptoms.append("NASAL_CONGESTION")
            transformations.append(
                {
                    "rule": "sinus_headache_adds_nasal_congestion",
                    "input": "user_selected_illustration:sinus",
                    "output": "NASAL_CONGESTION",
                    "reason": "Sinus illustration triggers the peer-approved decongestant rule.",
                }
            )
    return trace


def record_decision(
    trace: Dict[str, Any],
    *,
    action: str,
    severity: Optional[int] = None,
    duration: Optional[Dict[str, Any]] = None,
    clarification: Optional[Dict[str, Any]] = None,
    recommendation_filtering: Optional[list[dict]] = None,
) -> Dict[str, Any]:
    """Attach downstream expert-system decisions to an existing trace."""
    result = deepcopy(trace)
    red_flags = result.get("red_flags", [])
    result["decision"] = {
        "final_action": action,
        "severity": {
            "reported_max": severity,
            "referral_threshold": 8,
            "result": (
                "refer"
                if severity is not None and severity >= 8
                else "continue"
            ),
        },
        "red_flags": {
            "detected": red_flags,
            "result": "suppress_otc_and_refer" if red_flags else "continue",
        },
        "duration": duration,
        "clarification": clarification,
        "recommendation_filtering": recommendation_filtering or [],
    }
    return result


def _selection_reason(symptom: str, stages: list[dict]) -> str:
    dictionary = next((s for s in stages if s.get("stage") == "dictionary"), {})
    semantic = next((s for s in stages if s.get("stage") == "semantic"), {})
    in_dictionary = symptom in dictionary.get("detected", [])
    in_semantic = symptom in semantic.get("detected_selected", [])
    if in_dictionary and in_semantic:
        return "dictionary_match_and_semantic_corroboration"
    if in_semantic:
        return "semantic_similarity_passed_threshold_and_safety_filters"
    if in_dictionary:
        return "dictionary_phrase_match"
    return "expert_rule_transformation"
