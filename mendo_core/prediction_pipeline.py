"""Single, versioned symptom-prediction service used by web and benchmarks.

The service is intentionally descriptive: Mendo is a deterministic expert
system assisted by a pretrained sentence-embedding model. Similarity scores
are cosine similarities, not calibrated probabilities.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any, Dict, Optional

from .step3_hybrid import extract_symptoms_hybrid_report

ENGINE_ID = "mendo-expert-minilm-v3.1"
TRACE_SCHEMA_VERSION = 2
SEMANTIC_MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
SEMANTIC_THRESHOLD = 0.65
SEMANTIC_TOP_MARGIN = 0.08
SEMANTIC_MAX_SYMPTOMS = 2
DICTIONARY_CORROBORATION_THRESHOLD = 0.40


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
    trace["engine"] = {
        "engine_id": ENGINE_ID,
        "architecture": "knowledge_based_expert_system_with_pretrained_semantic_component",
        "semantic_model_id": SEMANTIC_MODEL_ID,
        "semantic_score_type": "cosine_similarity",
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
                row["score_type"] = "cosine_similarity"
                row["threshold"] = threshold
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
    return trace


def _apply_expert_disambiguation(user_input: str, report: Dict[str, Any]) -> None:
    """Resolve known semantic overlaps without conflating distinct labels."""
    text = re.sub(r"[^a-z0-9ñ\s]", " ", (user_input or "").lower())
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

    has_runny = bool(re.search(r"\b(sipon|sip on|runny nose|tumutulo(?:ng)? ilong|nagatulo(?:ng)? ilong)\b", text))
    has_blocked = bool(re.search(r"\b(barado|bara(?:do)?|stuffy nose|nasal congestion|blocked nose)\b", text))
    positive_runny = positive_in_last_clause(r"\b(sipon|sip on|runny nose)\b")
    positive_blocked = positive_in_last_clause(r"\b(barado|stuffy nose|nasal congestion|blocked nose)\b")

    if has_runny and not has_blocked:
        remove("NASAL_CONGESTION", "runny_cue_does_not_imply_congestion")
        if positive_runny:
            add("RUNNY_NOSE", "explicit_runny_nose_after_contrast")
    if has_blocked and not has_runny:
        remove("RUNNY_NOSE", "congestion_cue_does_not_imply_runny_nose")
        if positive_blocked:
            add("NASAL_CONGESTION", "explicit_congestion_after_contrast")

    allergy_explicit = bool(
        re.search(r"\b(allergy|allergies|allergic|rhinitis|alerdyi|aalerdyi)\b", text)
    )
    allergy_nasal_pattern = bool(
        re.fullmatch(r"(bahing|sneeze|sneezing)", text)
        or (
            re.search(r"\b(bahing|sneeze|sneezing)\b", text)
            and re.search(r"\b(makati|katol|itchy)\b(?:\s+\w+){0,3}\s+\b(ilong|nose|mata|eyes)\b", text)
        )
    )
    if not (allergy_explicit or allergy_nasal_pattern):
        remove("ALLERGIC_RHINITIS", "allergy_requires_explicit_or_nasal_allergy_context")

    skin_context = bool(
        re.search(r"\b(pantal|rash|rashes|hives|butlig|balat|panit|skin|braso)\b", text)
    )
    nasal_context = bool(re.search(r"\b(ilong|nose|bahing|sneeze)\b", text))
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
        dry = bool(re.search(r"\b(dry cough|tuyong ubo|uga nga ubo|walang plema|walay plema)\b", text))
        productive = bool(
            re.search(r"\b(plema|phlegm|mucus|wet cough|productive cough)\b", text)
        ) and not dry
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
