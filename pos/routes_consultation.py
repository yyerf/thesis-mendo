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

@consultation_bp.route("/")
def index():
    """Render the AI consultation kiosk page."""
    return render_template("pos/consultation.html")


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
        severity = data.get("severity")  # int 1-10 or None

        if not user_text:
            return jsonify({"error": "Please describe your symptoms."}), 400

        # ── Assign a session ID for this consultation flow ──
        session["sid"] = uuid.uuid4().hex[:8]

        # ── Severity gate: high pain → pharmacist referral ──
        referral = None
        if severity is not None:
            try:
                severity = int(severity)
            except (TypeError, ValueError):
                severity = None

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
            semantic_max_symptoms=3,
            enable_semantic_fallback=True,
        )
        symptoms = report.get("final", {}).get("symptoms", [])
        source = report.get("final", {}).get("source", "unknown")
        red_flags = report.get("red_flags", [])

        # ── Step 4: Recommendation ──
        from mendo_core.step4_recommend import recommend_from_dataset

        med_rows = _get_med_rows()
        recommendation = recommend_from_dataset(
            symptoms, med_rows, red_flags=red_flags, user_input=user_text,
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
            "source": source,
            "pipeline": {
                "stages": report.get("stages", []),
            },
            "recommendation": recommendation,
        }
        if user_age is not None:
            resp["age"] = user_age
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

        from mendo_core.step4_recommend import recommend_from_dataset
        med_rows = _get_med_rows()
        recommendation = recommend_from_dataset(
            symptoms, med_rows, user_input=pseudo_input, context_override=clarification,
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

        from mendo_core.step4_recommend import recommend_from_dataset
        med_rows = _get_med_rows()
        recommendation = recommend_from_dataset(symptoms, med_rows)

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
