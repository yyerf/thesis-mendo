"""Mendo AI Consultation Blueprint — symptom assessment & medicine recommendation.

This blueprint exposes the customer-facing kiosk flow:
  1. Patient describes symptoms (text or voice)
  2. Hybrid NLP pipeline extracts symptom intents
  3. If ambiguous cough → ask clarifying question
  4. Recommend OTC medicines from the Mendo dataset
  5. (Optional) Dispense via hardware bridge

The entire mendo_core pipeline is used:
  step1  →  Dictionary-based phrase matching (Tagalog/Bisaya/English)
  step2  →  Semantic fallback via sentence-transformers
  step3  →  Hybrid merge + negation handling
  step4  →  Rule-based recommendation from Mendo-Datasets.json
"""

from __future__ import annotations

import json
import logging
import re
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import (
    Blueprint,
    render_template,
    request,
    session,
    jsonify,
)

from mendo_core.interaction_logger import log_interaction

log = logging.getLogger("mendo.consultation")

consultation_bp = Blueprint(
    "consultation",
    __name__,
    url_prefix="/consult",
)

# ── Dataset (loaded once) ──────────────────────────────────────────────────

_DATASET_PATH = str(Path(__file__).resolve().parents[1] / "data" / "Mendo-Datasets.json")
_MED_ROWS: Optional[list] = None


def _get_med_rows():
    """Lazy-load the Mendo medicine dataset."""
    global _MED_ROWS
    if _MED_ROWS is not None:
        return _MED_ROWS
    try:
        from mendo_core.step4_recommend import load_mendo_dataset
        _MED_ROWS = load_mendo_dataset(_DATASET_PATH)
        log.info("Loaded %d medicines from dataset", len(_MED_ROWS))
    except Exception as e:
        log.error("Failed to load dataset: %s", e)
        _MED_ROWS = []
    return _MED_ROWS


# ── Routes ─────────────────────────────────────────────────────────────────

# ── Intensity-word extraction for per-symptom severity hints ──────────────

_INTENSITY_HIGH = [
    "kaayo", "grabe", "grabeng", "sobra", "sobrang", "matindi",
    "very", "really", "extremely", "severe", "intense", "worst",
    "terrible", "unbearable", "masyado", "todo", "lagpas", "super",
    "perte", "perteng", "mao jud", "bug-at", "bug at",
]
_INTENSITY_LOW = [
    "gamay", "gamay ra", "konti", "kaunti", "konting", "slight", "mild",
    "onti", "bahagya", "naa lang", "parang", "medyo", "dili kaayo",
    "not really", "a little", "bit", "small", "kaunting",
]

# Map symptom labels → keywords used in user text for proximity matching
_SYMPTOM_KEYWORDS: Dict[str, List[str]] = {
    "HEADACHE":         ["ulo", "head", "headache", "labad", "bumbunan", "migraine"],
    "FEVER":            ["lagnat", "fever", "hilanat", "init", "mainit", "nilalagnat"],
    "COUGH_GENERAL":    ["ubo", "cough", "inuubo", "gi-ubo", "giubo", "nauubo", "kakaubo", "naubo", "umuubo"],
    "COUGH_DRY":        ["ubo", "cough", "dry", "tuyo", "tuyong"],
    "COUGH_PRODUCTIVE": ["ubo", "cough", "plema", "phlegm", "mucus"],
    "SORE_THROAT":      ["lalamunan", "throat", "sore throat", "tutunlan"],
    "STOMACH_ACHE":     ["tiyan", "stomach", "tummy", "puson"],
    "BODY_ACHES":       ["katawan", "lawas", "body", "likod", "back"],
    "DIARRHEA":         ["pagtatae", "diarrhea", "lbm", "kalibang", "tatae"],
    "RUNNY_NOSE":       ["sipon", "runny", "ilong"],
    "NASAL_CONGESTION": ["barado", "congestion", "ilong", "nasal"],
    "RASHES":           ["pantal", "rash", "rashes", "butlig"],
    "ALLERGIC_RHINITIS":["allergy", "allergic", "rhinitis", "alerdyi"],
}


def _extract_severity_hints(user_text: str, symptoms: List[str]) -> Dict[str, int]:
    """Return a mapping of symptom → suggested severity (1-10) based on
    intensity modifiers found near each symptom's keywords in the text."""

    text = (user_text or "").lower()
    text = re.sub(r"[^a-z0-9ñ\s]", " ", text)
    tokens = text.split()

    if not tokens or not symptoms:
        return {}

    # Phase 1: locate each symptom's keyword positions in the text
    symptom_positions: Dict[str, List[int]] = {}
    for symptom in symptoms:
        kw_list = _SYMPTOM_KEYWORDS.get(symptom, [])
        positions: List[int] = []
        for i, tok in enumerate(tokens):
            for kw in kw_list:
                kw_parts = kw.split()
                if len(kw_parts) == 1 and tok == kw:
                    positions.append(i)
                elif len(kw_parts) > 1:
                    segment = " ".join(tokens[i:i + len(kw_parts)])
                    if segment == kw:
                        positions.extend(range(i, i + len(kw_parts)))
        symptom_positions[symptom] = positions

    # Phase 2: find all intensity word positions
    intensity_hits: List[Dict] = []
    for i, tok in enumerate(tokens):
        for phrase in _INTENSITY_HIGH:
            parts = phrase.split()
            segment = " ".join(tokens[i:i + len(parts)])
            if segment == phrase:
                intensity_hits.append({"pos": i, "level": "high"})
        for phrase in _INTENSITY_LOW:
            parts = phrase.split()
            segment = " ".join(tokens[i:i + len(parts)])
            if segment == phrase:
                intensity_hits.append({"pos": i, "level": "low"})

    # Phase 3: assign each intensity word to the CLOSEST symptom
    # Build (intensity_idx, symptom, distance) pairs, sort by distance,
    # and greedily assign
    assignments: List[tuple] = []
    for hit in intensity_hits:
        for symptom, positions in symptom_positions.items():
            if not positions:
                continue
            dist = min(abs(hit["pos"] - p) for p in positions)
            if dist <= 5:
                assignments.append((dist, hit["pos"], symptom, hit["level"]))

    assignments.sort()  # shortest distance first
    used_positions: set = set()
    assigned_symptoms: set = set()
    hints: Dict[str, int] = {}

    for dist, pos, symptom, level in assignments:
        if pos in used_positions or symptom in assigned_symptoms:
            continue
        hints[symptom] = 8 if level == "high" else 2
        used_positions.add(pos)
        assigned_symptoms.add(symptom)

    # Default unassigned symptoms to 5
    for symptom in symptoms:
        if symptom not in hints:
            hints[symptom] = 5

    return hints


@consultation_bp.route("/")
def index():
    """Render the AI consultation kiosk page."""
    return render_template("pos/consultation.html")


@consultation_bp.route("/api/pre-detect", methods=["POST"])
def api_pre_detect():
    """Lightweight symptom detection — called before the pain scale step
    so the UI can ask per-symptom severity.

    Request JSON:
        { "text": "gi ubo ko and sakit kaayo akong ulo" }

    Response JSON:
        {
            "symptoms": ["COUGH_GENERAL", "HEADACHE"],
            "severity_hints": {"COUGH_GENERAL": 5, "HEADACHE": 8},
            "red_flags": []
        }
    """
    try:
        data = request.get_json(force=True)
        user_text = (data.get("text") or "").strip()
        if not user_text:
            return jsonify({"error": "Please describe your symptoms."}), 400

        from mendo_core.step3_hybrid import extract_symptoms_hybrid_report

        report = extract_symptoms_hybrid_report(
            user_text,
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=2,
            enable_semantic_fallback=True,
        )
        symptoms = report.get("final", {}).get("symptoms", [])
        red_flags = report.get("red_flags", [])

        severity_hints = _extract_severity_hints(user_text, symptoms)

        return jsonify({
            "symptoms": symptoms,
            "severity_hints": severity_hints,
            "red_flags": red_flags,
        })
    except Exception as e:
        log.error("Pre-detect error: %s\n%s", e, traceback.format_exc())
        return jsonify({"error": f"Pre-detection failed: {e}"}), 500


@consultation_bp.route("/api/analyze", methods=["POST"])
def api_analyze():
    """Run the full hybrid NLP pipeline on user input text.

    Request JSON:
        { "text": "masakit ulo ko tapos inuubo" }

    Response JSON:
        {
            "symptoms": ["HEADACHE", "COUGH_GENERAL"],
            "pipeline": { ... },  // extraction report
            "recommendation": {
                "action": "recommend" | "ask_clarify",
                "recommendations": [...] | null,
                "question": "..." | null
            }
        }
    """
    try:
        data = request.get_json(force=True)
        user_text = (data.get("text") or "").strip()
        user_age = data.get("age")  # int or None
        severity = data.get("severity")  # int 1-10 or None (legacy single value)
        severity_map = data.get("severity_map")  # dict symptom→int (per-symptom)

        if not user_text:
            return jsonify({"error": "Please describe your symptoms."}), 400

        # ── Assign a session ID for this consultation flow ──
        session["sid"] = uuid.uuid4().hex[:8]

        # ── Resolve effective severity ──
        # If per-symptom severity_map is provided, use the max value for the
        # referral gate; otherwise fall back to the legacy single value.
        if severity_map and isinstance(severity_map, dict):
            try:
                int_vals = [int(v) for v in severity_map.values()]
                severity = max(int_vals) if int_vals else None
            except (TypeError, ValueError):
                severity = None
        else:
            if severity is not None:
                try:
                    severity = int(severity)
                except (TypeError, ValueError):
                    severity = None

        # ── Severity gate: high pain → pharmacist referral ──
        referral = None

        if severity is not None and severity >= 8:
            referral = {
                "level": "high",
                "severity": severity,
                "message": (
                    "Your reported severity is high. We strongly recommend "
                    "consulting a licensed pharmacist or doctor before "
                    "taking any medication. Self-medication may not be "
                    "appropriate for your condition."
                ),
            }

        # ── Step 1-3: Hybrid symptom extraction ──
        from mendo_core.step3_hybrid import extract_symptoms_hybrid_report

        report = extract_symptoms_hybrid_report(
            user_text,
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=2,
            enable_semantic_fallback=True,
        )
        symptoms = report.get("final", {}).get("symptoms", [])
        detected_conditions = report.get("final", {}).get("conditions", [])
        source = report.get("final", {}).get("source", "unknown")
        red_flags = report.get("red_flags", [])

        # ── Step 4: Recommendation ──
        from mendo_core.step4_recommend import recommend_medicine

        med_rows = _get_med_rows()
        recommendation = recommend_medicine(
            symptoms,
            med_rows,
            red_flags=red_flags,
            user_input=user_text,
            detected_conditions=detected_conditions,
        )

        # ── Filter by age + cross-reference POS inventory ──
        if user_age is not None:
            try:
                user_age = int(user_age)
            except (TypeError, ValueError):
                user_age = None

        try:
            from pos.db import get_inventory_by_brand
            if recommendation.get("action") == "recommend":
                filtered_recs = []
                for rec in recommendation.get("recommendations", []):
                    # ── Age filter ──
                    min_age_str = rec.get("min_age", "")
                    try:
                        min_age = int(min_age_str)
                    except (TypeError, ValueError):
                        min_age = 0
                    if user_age is not None and user_age < min_age:
                        continue  # skip medicines not suitable for this age

                    inv = get_inventory_by_brand(rec["brand"])
                    if inv:
                        rec["in_stock"] = inv["stock_quantity"] > 0
                        rec["stock_quantity"] = inv["stock_quantity"]
                        rec["pos_price"] = inv["unit_price"]
                        rec["inventory_id"] = inv["id"]
                    else:
                        rec["in_stock"] = False
                        rec["stock_quantity"] = 0
                        rec["pos_price"] = None
                        rec["inventory_id"] = None
                    filtered_recs.append(rec)
                recommendation["recommendations"] = filtered_recs
        except Exception:
            pass  # POS integration is optional

        resp: Dict[str, Any] = {
            "symptoms": symptoms,
            "detected_conditions": detected_conditions,
            "source": source,
            "pipeline": {
                "stages": report.get("stages", []),
            },
            "recommendation": recommendation,
        }
        if user_age is not None:
            resp["age"] = user_age
        if severity_map:
            resp["severity_map"] = severity_map
        if referral is not None:
            resp["referral"] = referral

        # ── Log interaction for Iteration 2 expert validation ──
        try:
            log_interaction(
                user_input=user_text,
                extracted_symptoms=symptoms,
                extraction_source=source,
                pipeline_stages=report.get("stages", []),
                recommendation=recommendation,
                red_flags=red_flags,
                interaction_type="initial_analysis",
                severity=severity,
                age=user_age,
                session_id=session.get("sid"),
            )
        except Exception:
            pass  # logging must never break the main flow

        return jsonify(resp)

    except Exception as e:
        log.error("Analyze error: %s\n%s", e, traceback.format_exc())
        return jsonify({"error": f"Analysis failed: {e}"}), 500


@consultation_bp.route("/api/duration-check", methods=["POST"])
def api_duration_check():
    """OLDCARTS Duration Safeguard — check whether symptom duration exceeds
    the clinically-safe threshold and block OTC if needed.

    Request JSON:
        {
            "symptom": "FEVER",
            "duration_value": "4+",
            "original_symptoms": ["FEVER", "HEADACHE"],
            "original_conditions": [],
            "pending_durations": ["HEADACHE"],
            "age": 25,
            "context_override": null,
            "clarification_data": {}
        }

    Response JSON (safe → next duration or proceed):
        {
            "safe": true,
            "next_duration": { ... } | null,
            "proceed": true | false,
            "symptoms": [...],
            "recommendation": { ... } | null
        }

    Response JSON (unsafe → doctor referral):
        {
            "safe": false,
            "referral": { ... },
            "symptom": "FEVER",
            "reported_days": 4
        }
    """
    try:
        data = request.get_json(force=True)
        symptom = (data.get("symptom") or "").strip()
        duration_value = (data.get("duration_value") or "").strip()
        original_symptoms = list(data.get("original_symptoms", []))
        original_conditions = list(data.get("original_conditions", []))
        pending_durations = list(data.get("pending_durations", []))
        user_age = data.get("age")
        dur_severity = data.get("severity")
        dur_severity_map = data.get("severity_map")
        context_override = data.get("context_override")
        clarification_data = data.get("clarification_data", {})

        if not symptom or not duration_value:
            return jsonify({"error": "Missing symptom or duration_value"}), 400

        if user_age is not None:
            try:
                user_age = int(user_age)
            except (TypeError, ValueError):
                user_age = None

        from mendo_core.step4_recommend import (
            parse_duration_days,
            check_duration_safety,
            get_duration_question,
            recommend_medicine,
        )

        reported_days = parse_duration_days(duration_value)
        result = check_duration_safety(symptom, reported_days)

        if not result["safe"]:
            # Duration exceeded — block OTC, refer to doctor
            try:
                log_interaction(
                    user_input=f"[duration-block:{symptom}={duration_value}({reported_days}d)]",
                    extracted_symptoms=original_symptoms,
                    extraction_source="duration_safeguard",
                    pipeline_stages=[],
                    recommendation=result["referral"],
                    interaction_type="duration_block",
                    severity=dur_severity,
                    age=user_age,
                    session_id=session.get("sid"),
                )
            except Exception:
                pass
            return jsonify({
                "safe": False,
                "referral": result["referral"],
                "symptom": symptom,
                "reported_days": reported_days,
            })

        # Duration is safe — check if there are more symptoms to ask about
        if pending_durations:
            next_symptom = pending_durations[0]
            remaining = pending_durations[1:]
            next_q = get_duration_question(next_symptom)
            if next_q:
                return jsonify({
                    "safe": True,
                    "proceed": False,
                    "next_duration": {
                        **next_q,
                        "original_symptoms": original_symptoms,
                        "original_conditions": original_conditions,
                        "pending_durations": remaining,
                        "context_override": context_override,
                        "clarification_data": clarification_data,
                    },
                })

        # All durations checked and safe — proceed with recommendation
        med_rows = _get_med_rows()
        recommendation = recommend_medicine(
            original_symptoms,
            med_rows,
            user_input=clarification_data.get("pseudo_input"),
            context_override=context_override,
            detected_conditions=original_conditions,
        )

        # Age filter + POS stock cross-reference
        try:
            from pos.db import get_inventory_by_brand
            if recommendation.get("action") == "recommend":
                filtered_recs = []
                for rec in recommendation.get("recommendations", []):
                    min_age_str = rec.get("min_age", "")
                    try:
                        min_age = int(min_age_str)
                    except (TypeError, ValueError):
                        min_age = 0
                    if user_age is not None and user_age < min_age:
                        continue
                    inv = get_inventory_by_brand(rec["brand"])
                    if inv:
                        rec["in_stock"] = inv["stock_quantity"] > 0
                        rec["stock_quantity"] = inv["stock_quantity"]
                        rec["pos_price"] = inv["unit_price"]
                        rec["inventory_id"] = inv["id"]
                    else:
                        rec["in_stock"] = False
                        rec["stock_quantity"] = 0
                        rec["pos_price"] = None
                        rec["inventory_id"] = None
                    filtered_recs.append(rec)
                recommendation["recommendations"] = filtered_recs
        except Exception:
            pass

        # Log
        try:
            log_interaction(
                user_input=f"[duration-safe:{symptom}={duration_value}({reported_days}d)]",
                extracted_symptoms=original_symptoms,
                extraction_source="duration_safeguard",
                pipeline_stages=[],
                recommendation=recommendation,
                interaction_type="duration_pass",
                severity=dur_severity,
                age=user_age,
                session_id=session.get("sid"),
            )
        except Exception:
            pass

        # Build display symptoms (carry over clarification-specific labels)
        display_symptoms = list(original_symptoms)
        if clarification_data:
            clarification = clarification_data.get("clarification")
            if clarification == "STOMACH_ACIDIC":
                display_symptoms = ["STOMACH_ACHE_ACIDIC" if s == "STOMACH_ACHE" else s for s in display_symptoms]
            elif clarification == "STOMACH_CRAMPING":
                display_symptoms = ["STOMACH_ACHE_CRAMPING" if s == "STOMACH_ACHE" else s for s in display_symptoms]
            elif clarification == "DIARRHEA_FOOD_POISONING":
                display_symptoms = ["DIARRHEA_INFECTIOUS_CONTEXT" if s == "DIARRHEA" else s for s in display_symptoms]
            elif clarification == "DIARRHEA_NON_INFECTIOUS":
                display_symptoms = ["DIARRHEA_NON_INFECTIOUS_CONTEXT" if s == "DIARRHEA" else s for s in display_symptoms]
            elif clarification == "SIPON_ALLERGY":
                display_symptoms = ["RUNNY_NOSE_ALLERGY_CONTEXT" if s == "RUNNY_NOSE" else s for s in display_symptoms]
            elif clarification == "SIPON_COLD_WEATHER":
                display_symptoms = ["RUNNY_NOSE_COLD_WEATHER_CONTEXT" if s == "RUNNY_NOSE" else s for s in display_symptoms]
            elif clarification == "SIPON_VIRAL_COLD":
                display_symptoms = ["RUNNY_NOSE_VIRAL_CONTEXT" if s == "RUNNY_NOSE" else s for s in display_symptoms]

        return jsonify({
            "safe": True,
            "proceed": True,
            "symptoms": original_symptoms,
            "symptoms_display": display_symptoms,
            "detected_conditions": original_conditions,
            "recommendation": recommendation,
        })

    except Exception as e:
        log.error("Duration-check error: %s\n%s", e, traceback.format_exc())
        return jsonify({"error": f"Duration check failed: {e}"}), 500


@consultation_bp.route("/api/context-clarify", methods=["POST"])
def api_context_clarify():
    """Handle OLDCARTS-style context clarification (diarrhea / stomach ache).

    Request JSON:
        {
            "original_symptoms": ["DIARRHEA"],
            "clarify_type": "DIARRHEA_CONTEXT",
            "clarification": "DIARRHEA_FOOD_POISONING"  // or "DIARRHEA_NON_INFECTIOUS"
        }
    """
    try:
        data = request.get_json(force=True)
        original = list(data.get("original_symptoms", []))
        original_conditions = list(data.get("original_conditions", []))
        clarify_type = data.get("clarify_type", "")
        clarification = data.get("clarification", "").strip()
        user_age = data.get("age")

        if not clarification:
            return jsonify({"error": "Missing clarification"}), 400

        if user_age is not None:
            try:
                user_age = int(user_age)
            except (TypeError, ValueError):
                user_age = None

        symptoms = list(original)

        # UI display labels can be more specific than core model labels.
        # We keep core labels for rule-based recommendation compatibility,
        # and send a parallel display list for frontend rendering.
        display_symptoms = list(symptoms)
        if clarification == "STOMACH_ACIDIC":
            display_symptoms = ["STOMACH_ACHE_ACIDIC" if s == "STOMACH_ACHE" else s for s in display_symptoms]
        elif clarification == "STOMACH_CRAMPING":
            display_symptoms = ["STOMACH_ACHE_CRAMPING" if s == "STOMACH_ACHE" else s for s in display_symptoms]
        elif clarification == "DIARRHEA_FOOD_POISONING":
            display_symptoms = ["DIARRHEA_INFECTIOUS_CONTEXT" if s == "DIARRHEA" else s for s in display_symptoms]
        elif clarification == "DIARRHEA_NON_INFECTIOUS":
            display_symptoms = ["DIARRHEA_NON_INFECTIOUS_CONTEXT" if s == "DIARRHEA" else s for s in display_symptoms]
        elif clarification == "SIPON_ALLERGY":
            display_symptoms = ["RUNNY_NOSE_ALLERGY_CONTEXT" if s == "RUNNY_NOSE" else s for s in display_symptoms]
        elif clarification == "SIPON_COLD_WEATHER":
            display_symptoms = ["RUNNY_NOSE_COLD_WEATHER_CONTEXT" if s == "RUNNY_NOSE" else s for s in display_symptoms]
        elif clarification == "SIPON_VIRAL_COLD":
            display_symptoms = ["RUNNY_NOSE_VIRAL_CONTEXT" if s == "RUNNY_NOSE" else s for s in display_symptoms]

        # Provide a light pseudo_input for extra downstream context where useful,
        # but pass the explicit clarification as a hard override so the user is
        # not asked the same question again.
        if clarification == "DIARRHEA_FOOD_POISONING":
            pseudo_input = "diarrhea food poisoning spoiled"
        elif clarification == "DIARRHEA_NON_INFECTIOUS":
            pseudo_input = "diarrhea no spoiled food no fever"
        elif clarification == "STOMACH_ACIDIC":
            pseudo_input = "stomach ache acidic burning"
        elif clarification == "STOMACH_CRAMPING":
            pseudo_input = "stomach ache cramp bloated"
        elif clarification == "SIPON_VIRAL_COLD":
            pseudo_input = "sipon runny nose cough fever cold"
        elif clarification == "SIPON_ALLERGY":
            pseudo_input = "sipon allergy sneezing itchy nose"
        elif clarification == "SIPON_COLD_WEATHER":
            pseudo_input = "sipon cold weather malamig"
        else:
            pseudo_input = None

        from mendo_core.step4_recommend import recommend_medicine
        med_rows = _get_med_rows()
        recommendation = recommend_medicine(
            symptoms,
            med_rows,
            user_input=pseudo_input,
            context_override=clarification,
            detected_conditions=original_conditions,
        )

        # Age filter + POS stock cross-reference
        try:
            from pos.db import get_inventory_by_brand
            if recommendation.get("action") == "recommend":
                filtered_recs = []
                for rec in recommendation.get("recommendations", []):
                    min_age_str = rec.get("min_age", "")
                    try:
                        min_age = int(min_age_str)
                    except (TypeError, ValueError):
                        min_age = 0
                    if user_age is not None and user_age < min_age:
                        continue
                    inv = get_inventory_by_brand(rec["brand"])
                    if inv:
                        rec["in_stock"] = inv["stock_quantity"] > 0
                        rec["stock_quantity"] = inv["stock_quantity"]
                        rec["pos_price"] = inv["unit_price"]
                        rec["inventory_id"] = inv["id"]
                    else:
                        rec["in_stock"] = False
                        rec["stock_quantity"] = 0
                        rec["pos_price"] = None
                        rec["inventory_id"] = None
                    filtered_recs.append(rec)
                recommendation["recommendations"] = filtered_recs
        except Exception:
            pass

        # Log
        try:
            log_interaction(
                user_input=f"[context-clarify:{clarify_type}={clarification}]",
                extracted_symptoms=symptoms,
                extraction_source="context_clarification",
                pipeline_stages=[],
                recommendation=recommendation,
                clarification=clarification,
                context_override=clarification,
                interaction_type="context_clarification",
                severity=data.get("severity"),
                age=user_age,
                session_id=session.get("sid"),
            )
        except Exception:
            pass

        return jsonify({
            "symptoms": symptoms,
            "symptoms_display": display_symptoms,
            "detected_conditions": original_conditions,
            "recommendation": recommendation,
        })

    except Exception as e:
        log.error("Context-clarify error: %s", e)
        return jsonify({"error": str(e)}), 500


@consultation_bp.route("/api/clarify", methods=["POST"])
def api_clarify():
    """Handle clarifying answer (e.g., dry vs wet cough) and re-recommend.

    Request JSON:
        {
            "original_symptoms": ["COUGH_GENERAL", "HEADACHE"],
            "clarification": "COUGH_DRY"  // or "COUGH_PRODUCTIVE"
        }
    """
    try:
        data = request.get_json(force=True)
        original = list(data.get("original_symptoms", []))
        original_conditions = list(data.get("original_conditions", []))
        clarification = data.get("clarification", "").strip()
        user_age = data.get("age")  # int or None

        if not clarification:
            return jsonify({"error": "Missing clarification"}), 400

        if user_age is not None:
            try:
                user_age = int(user_age)
            except (TypeError, ValueError):
                user_age = None

        # Replace COUGH_GENERAL with the specific type
        symptoms = [clarification if s == "COUGH_GENERAL" else s for s in original]
        symptoms = list(dict.fromkeys(symptoms))

        from mendo_core.step4_recommend import recommend_medicine
        med_rows = _get_med_rows()
        recommendation = recommend_medicine(
            symptoms,
            med_rows,
            detected_conditions=original_conditions,
        )

        # Cross-reference POS stock + age filter
        try:
            from pos.db import get_inventory_by_brand
            if recommendation.get("action") == "recommend":
                filtered_recs = []
                for rec in recommendation.get("recommendations", []):
                    min_age_str = rec.get("min_age", "")
                    try:
                        min_age = int(min_age_str)
                    except (TypeError, ValueError):
                        min_age = 0
                    if user_age is not None and user_age < min_age:
                        continue

                    inv = get_inventory_by_brand(rec["brand"])
                    if inv:
                        rec["in_stock"] = inv["stock_quantity"] > 0
                        rec["stock_quantity"] = inv["stock_quantity"]
                        rec["pos_price"] = inv["unit_price"]
                        rec["inventory_id"] = inv["id"]
                    else:
                        rec["in_stock"] = False
                        rec["stock_quantity"] = 0
                        rec["pos_price"] = None
                        rec["inventory_id"] = None
                    filtered_recs.append(rec)
                recommendation["recommendations"] = filtered_recs
        except Exception:
            pass

        # ── Log clarification interaction ──
        try:
            log_interaction(
                user_input="[clarification]",
                extracted_symptoms=symptoms,
                extraction_source="clarification",
                pipeline_stages=[],
                recommendation=recommendation,
                clarification=clarification,
                interaction_type="cough_clarification",
                severity=data.get("severity"),
                age=user_age,
                session_id=session.get("sid"),
            )
        except Exception:
            pass  # logging must never break the main flow

        return jsonify({
            "symptoms": symptoms,
            "detected_conditions": original_conditions,
            "recommendation": recommendation,
        })

    except Exception as e:
        log.error("Clarify error: %s", e)
        return jsonify({"error": str(e)}), 500


@consultation_bp.route("/api/transcribe", methods=["POST"])
def api_transcribe():
    """Speech-to-text endpoint. Accepts audio file upload.

    Form data:
        audio: file (wav/webm/mp3)

    Returns:
        { "text": "transcribed text" }
    """
    try:
        audio_file = request.files.get("audio")
        if not audio_file:
            return jsonify({"error": "No audio file provided"}), 400

        # Save temp file
        import tempfile
        suffix = Path(audio_file.filename or "audio.wav").suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            audio_file.save(tmp.name)
            tmp_path = tmp.name

        try:
            from tools.stt import transcribe_audio
            text = transcribe_audio(tmp_path, backend="auto")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        if not text:
            return jsonify({"error": "Could not transcribe audio. Please try typing instead."}), 400

        return jsonify({"text": text})

    except Exception as e:
        log.error("Transcribe error: %s", e)
        return jsonify({"error": f"Transcription failed: {e}"}), 500
