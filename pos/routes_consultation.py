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
    jsonify,
    Response,
    session,
)

from mendo_core.headache_locations import (
    HEADACHE_LOCATIONS,
    get_location,
    classify_danger,
    build_red_flag_response,
    all_keys,
)
from mendo_core.interaction_logger import log_interaction
from mendo_core.prediction_pipeline import (
    ENGINE_ID,
    TRACE_SCHEMA_VERSION,
    apply_headache_selection,
    predict_symptoms,
    record_decision,
)
from pos.auth import reviewer_required

log = logging.getLogger("mendo.consultation")

consultation_bp = Blueprint(
    "consultation",
    __name__,
    url_prefix="/consult",
)

CONSENT_COPY_VERSION = "research-consent-v1-2026-07"


def _consent_log_kwargs(data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = data or {}
    return {
        "research_consent": bool(session.get("research_consent", False)),
        "consent_version": session.get("consent_version"),
        "language": data.get("language") or session.get("consult_language") or "unspecified",
        "input_mode": data.get("input_mode") or session.get("consult_input_mode") or "text",
    }


def _headache_snapshot(
    location_key: Optional[str],
    user_age: Optional[int],
    source: str = "user_selected_illustration",
) -> Optional[Dict[str, Any]]:
    if not location_key:
        return None
    location = get_location(location_key)
    if not location:
        raise ValueError(f"Unknown headache illustration: {location_key}")
    danger = classify_danger(location_key, user_age=user_age or 0)
    return {
        "source": source,
        "key": location.key,
        "label_en": location.label_en,
        "label_tl": location.label_tl,
        "label_ceb": location.label_ceb,
        "image": location.image,
        "image_url": f"/static/images/headache/{location.image}",
        "zone": location.zone,
        "danger": danger,
        "safety_note_en": location.safety_note_en,
        "rule_effects": (
            ["add_nasal_congestion_for_sinus_recommendation_rule"]
            if location.key == "sinus"
            else []
        ),
    }

def _apply_text_headache_intake(
    report: Dict[str, Any],
    user_text: str,
    user_age: Optional[int],
) -> Optional[Dict[str, Any]]:
    """Free-text headache-type intake (deterministic tags, no ML).

    Runs only when no illustration was clicked:
      - HEADACHE already detected  -> classify the type directly
      - nothing detected at all    -> promote a bare type cue ("sinus",
        "sinusitis", "tension", "high blood") to a headache consult
    Returns the intake dict (or None). In the bare-cue case HEADACHE is
    promoted into report["final"]["symptoms"].
    """
    from mendo_core.headache_intake import (
        classify_headache_text,
        promote_bare_headache_cue,
    )

    symptoms = report["final"]["symptoms"]
    if "HEADACHE" in symptoms:
        intake = classify_headache_text(user_text, user_age=user_age)
        if intake and intake.get("matched"):
            return intake
        return None
    if not symptoms:
        intake = promote_bare_headache_cue(user_text)
        if intake:
            report["final"]["symptoms"].append("HEADACHE")
            return intake
    return None


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


@consultation_bp.route("/api/research-consent", methods=["GET", "POST"])
def api_research_consent():
    """Store the participant's research choice separately from clinical access."""
    if request.method == "GET":
        return jsonify(
            {
                "decided": "research_consent" in session,
                "research_consent": bool(session.get("research_consent", False)),
                "consent_version": session.get("consent_version"),
            }
        )
    data = request.get_json(force=True)
    if not isinstance(data.get("consent"), bool):
        return jsonify({"error": "consent must be true or false"}), 400
    session["research_consent"] = data["consent"]
    session["consent_version"] = CONSENT_COPY_VERSION
    return jsonify(
        {
            "saved": True,
            "research_consent": data["consent"],
            "consultation_available": True,
            "raw_input_persisted": data["consent"],
            "consent_version": CONSENT_COPY_VERSION,
        }
    )


_NO_MATCH_NEGATION_RX = re.compile(
    r"\b(wala|walang|walay|waley|no|not|without|never|none|neither|nor|"
    r"isnt|arent|dili|di|hindi|hnd|wara|wa)\b"
)

# Symptom-family words the dictionary covers (negation-only statements are
# honest no-treat cases, not "input not recognized" failures).
_NO_MATCH_SYMPTOM_WORDS = [
    "lagnat", "hilanat", "fever", "sinat", "ubo", "cough", "sipon", "sip-on",
    "runny", "ulo", "headache", "head ache", "tiyan", "sikmura", "stomach",
    "tutunlan", "lalamunan", "throat", "pantal", "rash", "hives", "butlig",
    "pagtatae", "kalibang", "diarrhea", "barado", "congestion", "plema",
    "allergy", "katawan", "lawas", "body ache", "naalibadbad",
]

# Health words the kiosk does NOT treat OTC — these deserve a polite
# "outside our scope, see a doctor/pharmacist" card, not "unrecognized".
_NO_MATCH_OUT_OF_SCOPE_WORDS = [
    "dibdib", "chest", "tenga", "ear", "mata", "eye", "mata ko", "ngipin",
    "ngipon", "tooth", "teeth", "tuhod", "knee", "siko", "elbow", "lutahan",
    "joint", "sugat", "wound", "hiwa", "dugo", "blood", "ihi", "urine",
    "pag-ihi", "peklat", "scar", "bukol", "lump", "pamamanhid", "numb",
    "manhid", "hilo-hilo", "hirap huminga", "nahihirapang huminga",
    "dili makahinga", "lisod makaginhawa", "short of breath", "breath",
    "hininga", "ginhawa", "paminaw", "paminawon", "tunog", "pandinig",
]

# Greeting / chit-chat / commerce phrases: nothing health-related at all.
_NO_MATCH_NONSENSE_WORDS = [
    "hello", "hi ", "kamusta", "kumusta", "musta", "good morning",
    "good afternoon", "good evening", "magandang", "maayong", "salamat",
    "thanks", "thank you", "magkano", "pila", "pila ang", "how much",
    "how much is", "biogesic", "paracetamol", "gamot", "tabang", "help me",
]


def classify_no_match(user_text: str) -> str:
    """Tag an empty-detection input so the kiosk can show a helpful page.

    Returns one of:
      "negated_only" — symptom words are explicitly denied ("wala akong
                       lagnat"); nothing to treat, no failure to explain.
      "out_of_scope" — a real health complaint that is outside the 13 OTC
                       labels (chest, ear, tooth, wound, ...); polite
                       referral, not "unrecognized".
      "nonsense"     — greeting / chit-chat / shopping words, or very short
                       text with no health content at all.
      "vague"        — fallback: some text but no health signal we can map.

    Deterministic by design (matches the precision-first architecture).
    """
    text = (user_text or "").strip()
    low = text.lower()

    def has(words):
        for w in words:
            if re.search(rf"\b{re.escape(w)}\b", low):
                return True
        return False

    if not text or len(low) < 3:
        return "nonsense"

    has_symptom_word = has(_NO_MATCH_SYMPTOM_WORDS)

    # A wholly negated statement ("wala akong lagnat", "no fever at all") is
    # an honest "no symptoms to treat" — the words were understood.
    if has_symptom_word and _NO_MATCH_NEGATION_RX.search(low):
        return "negated_only"

    if has(_NO_MATCH_OUT_OF_SCOPE_WORDS):
        return "out_of_scope"

    if has(_NO_MATCH_NONSENSE_WORDS):
        return "nonsense"

    if has_symptom_word or len(low.split()) >= 4:
        return "vague"

    return "nonsense"


@consultation_bp.route("/api/pre-detect", methods=["POST"])
def api_pre_detect():
    """Lightweight symptom detection — called before the pain scale step

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

        report = predict_symptoms(user_text)
        headache_intake = _apply_text_headache_intake(report, user_text, None)
        # Mirror apply_headache_selection so the severity step asks about the
        # full final symptom set (e.g. sinus intake -> NASAL_CONGESTION too).
        if headache_intake and headache_intake.get("key") == "sinus":
            if "NASAL_CONGESTION" not in report["final"]["symptoms"]:
                report["final"]["symptoms"].append("NASAL_CONGESTION")
        symptoms = report.get("final", {}).get("symptoms", [])
        red_flags = report.get("red_flags", [])

        severity_hints = _extract_severity_hints(user_text, symptoms)

        return jsonify({
            "symptoms": symptoms,
            "severity_hints": severity_hints,
            "red_flags": red_flags,
            "headache_intake": headache_intake,
            "no_match_reason": classify_no_match(user_text) if not symptoms else None,
            "engine": report.get("engine"),
            "trace_version": report.get("trace_version"),
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
        headache_location = data.get("headache_location")  # str key or None
        language = (data.get("language") or "unspecified").strip()
        input_mode = (data.get("input_mode") or "text").strip()

        if not user_text:
            return jsonify({"error": "Please describe your symptoms."}), 400
        if user_age is not None:
            try:
                user_age = int(user_age)
            except (TypeError, ValueError):
                return jsonify({"error": "age must be a whole number"}), 400

        # ── Assign a session ID for this consultation flow ──
        session["sid"] = uuid.uuid4().hex[:8]
        session["consult_language"] = language
        session["consult_input_mode"] = input_mode

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

        # ── Step 1-3: one shared, versioned prediction service ──
        report = predict_symptoms(user_text)
        symptoms = report.get("final", {}).get("symptoms", [])

        # ── Free-text headache-type intake: when HEADACHE is detected from
        #    typed text and no illustration was clicked, try to classify the
        #    type directly from the description (deterministic tags). An
        #    explicit illustration click always wins. A bare type cue with
        #    no other detected symptom (e.g. "sinus", "sinusitis") is
        #    promoted to a headache consult instead of a no-match. ──
        headache_intake = None
        if not headache_location:
            headache_intake = _apply_text_headache_intake(report, user_text, user_age)
            if headache_intake:
                headache_location = headache_intake["key"]

        # An explicit/auto-confirmed headache location implies a headache
        # consult even when the typed text was a bare type cue ("tusok tusok
        # sa ulo", "sinus") that the dictionary could not map to HEADACHE.
        if headache_location and "HEADACHE" not in report["final"]["symptoms"]:
            report["final"]["symptoms"].append("HEADACHE")
            report.setdefault("transformations", []).append({
                "rule": "headache_location_implies_headache",
                "input": f"headache_location:{headache_location}",
                "output": "HEADACHE",
                "reason": "User-confirmed headache type guarantees the headache symptom.",
            })

        try:
            headache = _headache_snapshot(
                headache_location,
                user_age,
                source=(
                    "user_selected_illustration"
                    if headache_location and headache_location == data.get("headache_location")
                    else "free_text_intake"
                ),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        report = apply_headache_selection(report, headache)
        report["headache_intake"] = headache_intake
        symptoms = report.get("final", {}).get("symptoms", [])
        detected_conditions = report.get("final", {}).get("conditions", [])
        source = report.get("final", {}).get("source", "unknown")
        red_flags = report.get("red_flags", [])

        # ── Headache location red flags: only real red_flag danger blocks OTC ──
        headache_cautions = []
        if headache_location:
            loc_data_red = get_location(headache_location)
            if loc_data_red:
                hf_danger = classify_danger(headache_location, user_age=user_age or 0)
                if hf_danger == "red_flag":
                    red_flags.append({
                        "flag": "headache_location",
                        "message": loc_data_red.safety_note_en,
                    })
                elif loc_data_red.red_flags_en:
                    headache_cautions = loc_data_red.red_flags_en

        # Keep raw health text out of general application logs.
        log.info(
            "Analyze request session=%s age=%s severity=%s labels=%d red_flags=%d engine=%s",
            session.get("sid"),
            user_age,
            severity,
            len(symptoms),
            len(red_flags),
            ENGINE_ID,
        )

        # ── Step 4: Recommendation ──
        from mendo_core.step4_recommend import recommend_medicine

        med_rows = _get_med_rows()

        # Resolve headache location preferences for recommendation tuning
        headache_prefer = None
        headache_avoid = None
        if headache_location:
            loc_data = get_location(headache_location)
            if loc_data:
                headache_prefer = loc_data.prefer_categories
                headache_avoid = loc_data.avoid_categories

        recommendation = recommend_medicine(
            symptoms,
            med_rows,
            red_flags=red_flags,
            user_input=user_text,
            detected_conditions=detected_conditions,
            headache_prefer_categories=headache_prefer,
            headache_avoid_categories=headache_avoid,
        )

        # Log recommendation details
        rec_action = recommendation.get("action", "unknown")
        log.info("RECOMMENDATION: action=%s", rec_action)
        if rec_action == "recommend":
            for r in recommendation.get("recommendations", []) or []:
                log.info("  MED: brand=%s generic=%s category=%s reasons=%s min_age=%s",
                         r.get("brand"), r.get("active_ingredients"), r.get("drug_category"),
                         r.get("reasons"), r.get("min_age"))
        elif rec_action == "ask_clarify":
            log.info("  CLARIFY: question=%s options=%s", recommendation.get("question"),
                     [o.get("label") for o in (recommendation.get("options") or [])])
        elif rec_action in ("triage", "no_match"):
            log.info("  ACTION=%s message=%s", rec_action, recommendation.get("message") or recommendation.get("question"))

        # ── Filter by age + cross-reference POS inventory ──
        if user_age is not None:
            try:
                user_age = int(user_age)
            except (TypeError, ValueError):
                user_age = None

        recommendation_filtering: List[Dict[str, Any]] = []
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
                        recommendation_filtering.append(
                            {
                                "brand": rec.get("brand"),
                                "decision": "excluded",
                                "reason": "patient_age_below_minimum",
                                "patient_age": user_age,
                                "minimum_age": min_age,
                            }
                        )
                        continue  # skip medicines not suitable for this age

                    inv = get_inventory_by_brand(rec["brand"])
                    if (
                        inv
                        and inv.get("is_active")
                        and inv.get("hardware_slot") is not None
                    ):
                        rec["in_stock"] = inv["stock_quantity"] > 0
                        rec["stock_quantity"] = inv["stock_quantity"]
                        rec["pos_price"] = inv["unit_price"]
                        rec["inventory_id"] = inv["id"]
                        rec["hardware_slot"] = inv.get("hardware_slot")
                    else:
                        rec["in_stock"] = False
                        rec["stock_quantity"] = 0
                        rec["pos_price"] = None
                        rec["inventory_id"] = None
                        rec["hardware_slot"] = None
                    recommendation_filtering.append(
                        {
                            "brand": rec.get("brand"),
                            "decision": "kept",
                            "reason": "age_eligible",
                            "hardware_slot": rec.get("hardware_slot"),
                            "inventory": (
                                "in_stock" if rec.get("in_stock") else "out_of_stock"
                            ),
                        }
                    )
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
                "semantic": report.get("semantic"),
            },
            "recommendation": recommendation,
            "recommendation_filtering": recommendation_filtering,
            "engine": report.get("engine"),
            "trace_version": TRACE_SCHEMA_VERSION,
            "no_match_reason": classify_no_match(user_text) if not symptoms else None,
        }
        if user_age is not None:
            resp["age"] = user_age
        if severity_map:
            resp["severity_map"] = severity_map
        if referral is not None:
            resp["referral"] = referral
        if headache_cautions:
            resp["headache_cautions"] = headache_cautions

        # ── Headache location context ──
        if headache_location:
            loc_data = get_location(headache_location)
            if loc_data:
                resp["headache_location"] = headache
                resp["headache_intake"] = report.get("headache_intake")
                # If headache danger is red_flag, add a specific referral
                if headache and headache["danger"] == "red_flag":
                    if referral is None:
                        referral = {
                            "level": "high",
                            "severity": severity,
                            "message": (
                                "The reported headache type requires medical "
                                "attention. Please consult a doctor before "
                                "taking any medication."
                            ),
                        }
                        resp["referral"] = referral

        # ── Log interaction for Iteration 2 expert validation ──
        try:
            is_triage = bool(referral)
            if not is_triage and headache_location:
                is_triage = classify_danger(headache_location, user_age or 0) == "red_flag"
            trace = record_decision(
                report,
                action="refer" if is_triage else recommendation.get("action", "unknown"),
                severity=severity,
                clarification=(
                    {
                        "required": True,
                        "type": recommendation.get("clarify_type"),
                        "question": recommendation.get("question"),
                        "options": [
                            option.get("value")
                            for option in recommendation.get("options", []) or []
                        ],
                    }
                    if recommendation.get("action") == "ask_clarify"
                    else {"required": False}
                ),
                recommendation_filtering=recommendation_filtering,
            )
            interaction_id = log_interaction(
                user_input=user_text,
                extracted_symptoms=symptoms,
                extraction_source=source,
                pipeline_stages=report.get("stages", []),
                recommendation=recommendation,
                red_flags=red_flags,
                interaction_type="triage" if is_triage else "analysis",
                severity=severity,
                age=user_age,
                session_id=session.get("sid"),
                trace=trace,
                headache=headache,
                severity_map=severity_map if isinstance(severity_map, dict) else None,
                **_consent_log_kwargs(data),
            )
            resp["interaction_id"] = interaction_id
        except Exception as exc:
            log.error("Structured interaction logging failed: %s", exc)
            resp["interaction_id"] = "write_failed"

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
            # RUNNY_NOSE exceeding threshold gets a soft warning (still proceed)
            if symptom == "RUNNY_NOSE":
                warning_msg = (
                    f"Your runny nose has lasted {reported_days} days. "
                    "We recommend consulting a doctor if it persists. "
                    "You may still proceed with OTC medication."
                )
                try:
                    log_interaction(
                        user_input=f"{symptom} ({reported_days} days) — duration warning, allowed",
                        extracted_symptoms=original_symptoms,
                        extraction_source="duration_safeguard",
                        pipeline_stages=[],
                        recommendation={"action": "none", "recommendations": []},
                        interaction_type="duration_warning",
                        severity=dur_severity,
                        age=user_age,
                        session_id=session.get("sid"),
                        duration_symptom=symptom,
                        duration_value=duration_value,
                        duration_days=reported_days,
                        **_consent_log_kwargs(data),
                    )
                except Exception:
                    pass
                # Return safe=true so the flow continues, but attach a warning
                return jsonify({
                    "safe": True,
                    "proceed": True,
                    "warning": warning_msg,
                    "symptoms": original_symptoms,
                    "recommendation": {"action": "none", "recommendations": []},
                })

            # Duration exceeded — block OTC, refer to doctor
            try:
                log_interaction(
                    user_input=f"{symptom} ({reported_days} days) — duration too long, blocked",
                    extracted_symptoms=original_symptoms,
                    extraction_source="duration_safeguard",
                    pipeline_stages=[],
                    recommendation=result["referral"],
                    interaction_type="duration_blocked",
                    severity=dur_severity,
                    age=user_age,
                    session_id=session.get("sid"),
                    duration_symptom=symptom,
                    duration_value=duration_value,
                    duration_days=reported_days,
                    **_consent_log_kwargs(data),
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
                    if (
                        inv
                        and inv.get("is_active")
                        and inv.get("hardware_slot") is not None
                    ):
                        rec["in_stock"] = inv["stock_quantity"] > 0
                        rec["stock_quantity"] = inv["stock_quantity"]
                        rec["pos_price"] = inv["unit_price"]
                        rec["inventory_id"] = inv["id"]
                        rec["hardware_slot"] = inv.get("hardware_slot")
                    else:
                        rec["in_stock"] = False
                        rec["stock_quantity"] = 0
                        rec["pos_price"] = None
                        rec["inventory_id"] = None
                        rec["hardware_slot"] = None
                    filtered_recs.append(rec)
                recommendation["recommendations"] = filtered_recs
        except Exception:
            pass

        # Log
        try:
            log_interaction(
                user_input=f"{symptom} ({reported_days} days) — duration ok",
                extracted_symptoms=original_symptoms,
                extraction_source="duration_safeguard",
                pipeline_stages=[],
                recommendation=recommendation,
                interaction_type="duration_ok",
                severity=dur_severity,
                age=user_age,
                session_id=session.get("sid"),
                duration_symptom=symptom,
                duration_value=duration_value,
                duration_days=reported_days,
                **_consent_log_kwargs(data),
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
        elif clarification == "RASHES_BREATHING_YES":
            pseudo_input = "rashes difficulty breathing emergency"
        elif clarification == "RASHES_BREATHING_NO":
            pseudo_input = "rashes no difficulty breathing"
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
                    if (
                        inv
                        and inv.get("is_active")
                        and inv.get("hardware_slot") is not None
                    ):
                        rec["in_stock"] = inv["stock_quantity"] > 0
                        rec["stock_quantity"] = inv["stock_quantity"]
                        rec["pos_price"] = inv["unit_price"]
                        rec["inventory_id"] = inv["id"]
                        rec["hardware_slot"] = inv.get("hardware_slot")
                    else:
                        rec["in_stock"] = False
                        rec["stock_quantity"] = 0
                        rec["pos_price"] = None
                        rec["inventory_id"] = None
                        rec["hardware_slot"] = None
                    filtered_recs.append(rec)
                recommendation["recommendations"] = filtered_recs
        except Exception:
            pass

        # Log
        try:
            log_interaction(
                user_input=f"Clarified: {clarification}",
                extracted_symptoms=symptoms,
                extraction_source="context_clarification",
                pipeline_stages=[],
                recommendation=recommendation,
                clarification=clarification,
                context_override=clarification,
                interaction_type="clarify_context",
                severity=data.get("severity"),
                age=user_age,
                session_id=session.get("sid"),
                **_consent_log_kwargs(data),
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
                    if (
                        inv
                        and inv.get("is_active")
                        and inv.get("hardware_slot") is not None
                    ):
                        rec["in_stock"] = inv["stock_quantity"] > 0
                        rec["stock_quantity"] = inv["stock_quantity"]
                        rec["pos_price"] = inv["unit_price"]
                        rec["inventory_id"] = inv["id"]
                        rec["hardware_slot"] = inv.get("hardware_slot")
                    else:
                        rec["in_stock"] = False
                        rec["stock_quantity"] = 0
                        rec["pos_price"] = None
                        rec["inventory_id"] = None
                        rec["hardware_slot"] = None
                    filtered_recs.append(rec)
                recommendation["recommendations"] = filtered_recs
        except Exception:
            pass

        # ── Log clarification interaction ──
        try:
            log_interaction(
                user_input=f"Clarified: {clarification}",
                extracted_symptoms=symptoms,
                extraction_source="clarification",
                pipeline_stages=[],
                recommendation=recommendation,
                clarification=clarification,
                interaction_type="clarify_symptom",
                severity=data.get("severity"),
                age=user_age,
                session_id=session.get("sid"),
                **_consent_log_kwargs(data),
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


@consultation_bp.route("/api/headache-locations", methods=["GET"])
def api_headache_locations():
    """Return the list of known headache locations with multilingual labels.

    Response JSON:
        {
            "locations": [...]
        }
    """
    try:
        locs = []
        for loc in HEADACHE_LOCATIONS:
            locs.append({
                "key": loc.key,
                "image": loc.image,
                "label_en": loc.label_en,
                "label_tl": loc.label_tl,
                "label_ceb": loc.label_ceb,
                "desc_en": loc.desc_en,
                "desc_tl": loc.desc_tl,
                "desc_ceb": loc.desc_ceb,
                "danger": loc.danger,
                "common_causes_en": loc.common_causes_en,
                "common_causes_tl": loc.common_causes_tl,
                "common_causes_ceb": loc.common_causes_ceb,
                "red_flags_en": loc.red_flags_en,
                "red_flags_tl": loc.red_flags_tl,
                "red_flags_ceb": loc.red_flags_ceb,
                "safety_note_en": loc.safety_note_en,
                "safety_note_tl": loc.safety_note_tl,
                "safety_note_ceb": loc.safety_note_ceb,
                "otc_safe_if_isolated": loc.otc_safe_if_isolated,
            })
        return jsonify({"locations": locs})
    except Exception as e:
        log.error("Headache locations error: %s", e)
        return jsonify({"error": str(e)}), 500


@consultation_bp.route("/api/headache-assess", methods=["POST"])
def api_headache_assess():
    """Assess a selected headache location and return red-flag / safety info.

    Request JSON:
        {
            "location_key": "occipital",
            "age": 25,
            "has_fever": false,
            "has_neck_stiffness": false,
            "has_vision_changes": false
        }

    Response JSON:
        {
            "location_key": "occipital",
            "label_en": "Back of Head / Base of Skull",
            "danger": "caution",            # "safe" | "caution" | "red_flag"
            "red_flag": null | { "flag": "headache_red_flag", ... },
            "safety_note_en": "...",
            "prefer_categories": [...],
            "avoid_categories": [],
            "otc_safe_if_isolated": true
        }
    """
    try:
        data = request.get_json(force=True)
        location_key = (data.get("location_key") or "").strip()
        if not location_key:
            return jsonify({"error": "Missing location_key"}), 400

        user_age = data.get("age", 0)
        has_fever = bool(data.get("has_fever", False))
        has_neck_stiffness = bool(data.get("has_neck_stiffness", False))
        has_vision_changes = bool(data.get("has_vision_changes", False))

        loc = get_location(location_key)
        if not loc:
            return jsonify({"error": f"Unknown location: {location_key}"}), 400

        danger = classify_danger(
            location_key,
            user_age=user_age,
            has_fever=has_fever,
            has_neck_stiffness=has_neck_stiffness,
            has_vision_changes=has_vision_changes,
        )

        resp = {
            "location_key": loc.key,
            "label_en": loc.label_en,
            "label_tl": loc.label_tl,
            "label_ceb": loc.label_ceb,
            "danger": danger,
            "red_flag": None,
            "safety_note_en": loc.safety_note_en,
            "safety_note_tl": loc.safety_note_tl,
            "safety_note_ceb": loc.safety_note_ceb,
            "prefer_categories": loc.prefer_categories,
            "avoid_categories": loc.avoid_categories,
            "otc_safe_if_isolated": loc.otc_safe_if_isolated,
        }

        if danger == "red_flag":
            resp["red_flag"] = build_red_flag_response(location_key)

        return jsonify(resp)

    except Exception as e:
        log.error("Headache assess error: %s", e)
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


@consultation_bp.route("/api/export-logs/csv", methods=["GET"])
@reviewer_required
def api_export_logs_csv(current_user=None):
    """Export all interaction logs as CSV."""
    try:
        from mendo_core.interaction_logger import export_logs_as_csv
        csv_data = export_logs_as_csv()
        if not csv_data:
            return jsonify({"error": "No logs found"}), 404
        return Response(csv_data, mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=interaction_logs.csv"})
    except Exception as e:
        log.error("Export CSV error: %s", e)
        return jsonify({"error": str(e)}), 500


@consultation_bp.route("/api/export-logs/pdf", methods=["GET"])
@reviewer_required
def api_export_logs_pdf(current_user=None):
    """Export all interaction logs as PDF."""
    try:
        from mendo_core.interaction_logger import export_logs_as_pdf
        pdf_data = export_logs_as_pdf()
        if not pdf_data:
            return jsonify({"error": "No logs found"}), 404
        return Response(pdf_data, mimetype="application/pdf",
                        headers={"Content-Disposition": "attachment; filename=interaction_logs.pdf"})
    except Exception as e:
        log.error("Export PDF error: %s", e)
        return jsonify({"error": str(e)}), 500
