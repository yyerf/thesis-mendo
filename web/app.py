from flask import Flask, redirect, render_template, url_for, flash, session
import joblib
from flask import request, jsonify
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.preprocessing import LabelEncoder
import pickle

from typing import Any, Dict, List, Optional, Tuple

import os
import sys
import re
import tempfile

# Ensure project root is on sys.path so `mendo_core` is importable regardless of CWD
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Database is OPTIONAL - only needed for shop/cart features, NOT for core NLP
try:
    import pymysql
    pymysql.install_as_MySQLdb()
    from flask_mysqldb import MySQL
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    print("Note: MySQL not installed. Core NLP features will work fine. Shop/cart disabled.")

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'mendo-dev-secret-key'

# ── POS system (SQLite — zero-config) ──
POS_AVAILABLE = False
try:
    from pos import init_pos
    from pos.db import (
        get_inventory_by_brand, list_inventory, get_inventory_item,
        create_transaction,
    )
    init_pos(app)
    POS_AVAILABLE = True
except Exception as _pos_err:
    print(f"Note: POS system not loaded ({_pos_err}). Buy/vend features disabled.")

# ── Hardware serial bridge (optional) ──
_VEND_BRIDGE = None
try:
    from hardware.serial_bridge import VendoBridge
    _VEND_BRIDGE = VendoBridge()
    print("✓ Vendo serial bridge loaded")
except Exception as _hw_err:
    print(f"Note: Vendo hardware bridge not loaded ({_hw_err}). Dispensing will be simulated.")

# MysQL Database (optional - only for shop)
if MYSQL_AVAILABLE:
    try:
        app.config['MYSQL_HOST'] = 'localhost'
        app.config['MYSQL_USER'] = 'mendo-user'
        app.config['MYSQL_PASSWORD'] = '120904'
        app.config['MYSQL_DB'] = 'mendo'
        shopsql = MySQL(app)
        print("✓ MySQL connected (shop features enabled)")
    except:
        shopsql = None
        print("Note: MySQL not configured. Core NLP works without it.")
else:
    shopsql = None

# Legacy ML artifacts (optional). These are only required for the old `/assess` SVM page.
vectorizer = None
encoder = None
svm_model = None
LEGACY_MODEL_AVAILABLE = False

try:
    vectorizer = pickle.load(open('pred_vectorizer', 'rb'))
    encoder = pickle.load(open('pred_encoder', 'rb'))
    svm_model = pickle.load(open('machine_learning_model/svm_pred_model', 'rb'))
    LEGACY_MODEL_AVAILABLE = True
except FileNotFoundError as e:
    LEGACY_MODEL_AVAILABLE = False
    print(f"Warning: Legacy model files missing ({e}). '/assess' will be disabled.")
except Exception as e:
    LEGACY_MODEL_AVAILABLE = False
    print(f"Warning: Failed to load legacy model artifacts ({e}). '/assess' will be disabled.")


_MENDO_ROWS = None

# Offline STT (Whisper). Cached at module level so we don't reload per request.
_WHISPER_MODEL = None
_WHISPER_BACKEND: Optional[str] = None  # 'faster-whisper' | 'whisper'
_WHISPER_LOAD_ERROR: Optional[str] = None


def _get_whisper_model():
    """Load Whisper model once and reuse (offline STT).

    Configure model via env var `MENDO_WHISPER_MODEL`:
      - "small" (default)
      - or a local model path
    """
    global _WHISPER_MODEL, _WHISPER_BACKEND, _WHISPER_LOAD_ERROR
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL
    if _WHISPER_LOAD_ERROR:
        raise RuntimeError(_WHISPER_LOAD_ERROR)

    model_name_or_path = os.environ.get("MENDO_WHISPER_MODEL", "small")

    # Preferred: faster-whisper
    try:
        from faster_whisper import WhisperModel  # type: ignore

        device = os.environ.get("MENDO_WHISPER_DEVICE", "cpu")
        compute_type = os.environ.get("MENDO_WHISPER_COMPUTE_TYPE", "int8")
        _WHISPER_MODEL = WhisperModel(model_name_or_path, device=device, compute_type=compute_type)
        _WHISPER_BACKEND = "faster-whisper"
        return _WHISPER_MODEL
    except Exception as e:
        last_fw = str(e)

    # Fallback: openai-whisper
    try:
        import whisper  # type: ignore

        _WHISPER_MODEL = whisper.load_model(model_name_or_path)
        _WHISPER_BACKEND = "whisper"
        return _WHISPER_MODEL
    except Exception as e:
        _WHISPER_LOAD_ERROR = (
            "Offline STT is not available. Install one of:\n"
            "  - faster-whisper (recommended): pip3 install --user faster-whisper\n"
            "  - openai-whisper: pip3 install --user openai-whisper\n"
            f"\nLoad errors:\n  faster-whisper: {last_fw}\n  whisper: {e}"
        )
        raise RuntimeError(_WHISPER_LOAD_ERROR)


def _transcribe_wav_file(wav_path: str) -> str:
    model = _get_whisper_model()
    backend = _WHISPER_BACKEND
    if backend == "faster-whisper":
        segments, _info = model.transcribe(wav_path, vad_filter=True)
        text = "".join((seg.text or "") for seg in segments)
        return text.strip()
    if backend == "whisper":
        result = model.transcribe(wav_path)
        return str(result.get("text") or "").strip()
    raise RuntimeError("Whisper backend not initialized")


def _load_mendo_rows() -> Tuple[Optional[List[Any]], Optional[str]]:
    """Load and cache Mendo dataset rows for recommendations."""
    global _MENDO_ROWS
    if _MENDO_ROWS is not None:
        return _MENDO_ROWS, None

    try:
        from mendo_core.step4_recommend import DATASET_DEFAULT, load_mendo_dataset
    except Exception as e:
        return None, f"recommendation imports unavailable: {e}"

    try:
        _MENDO_ROWS = load_mendo_dataset(DATASET_DEFAULT)
        return _MENDO_ROWS, None
    except Exception as e:
        return None, f"failed to load dataset: {e}"


def _apply_cough_override(labels: List[str], cough_type: Optional[str]) -> List[str]:
    if not cough_type:
        return labels
    cough_type = str(cough_type).strip().lower()

    mapped = None
    if cough_type in {"dry", "dry_cough", "walang", "walay"}:
        mapped = "COUGH_DRY"
    elif cough_type in {"productive", "wet", "with_phlegm", "plema"}:
        mapped = "COUGH_PRODUCTIVE"

    if not mapped:
        return labels

    out = [l for l in labels if l != "COUGH_GENERAL" and l != mapped]
    out.append(mapped)
    return out


def _reason_text(codes: List[str]) -> str:
    lookup = {
        "productive_cough_match": "Matched productive cough (with plema/phlegm).",
        "dry_cough_match": "Matched dry cough (no plema/phlegm).",
        "general_cough_match": "Matched general cough indications.",
        "fever_match": "Matched fever indications.",
        "headache_match": "Matched headache indications.",
        "body_aches_match": "Matched body aches/pain indications.",
        "nasal_congestion_match": "Matched nasal congestion indications.",
        "runny_nose_match": "Matched runny nose/sipon indications.",
        "allergy_match": "Matched allergy indications.",
        "rash_match": "Matched rash/skin allergy indications.",
        "diarrhea_match": "Matched diarrhea indications.",
        "stomach_ache_match": "Matched stomach discomfort indications.",
    }
    parts = [lookup.get(c, c) for c in (codes or [])]
    return " ".join(parts).strip()


def _flow_text(report: Dict[str, Any], *, debug: bool) -> str:
    lines: List[str] = []
    lines.append(f"INPUT:  {report.get('input', '')}")
    for s in report.get("stages", []) or []:
        if s.get("stage") == "dictionary":
            lines.append(f"STAGE1: DICTIONARY -> {s.get('detected', [])}")
            if debug:
                for d in s.get("details", []) or []:
                    lines.append(f"        hit {d.get('symptom')}: {d.get('matched_phrases')}")
        if s.get("stage") == "semantic":
            if not s.get("available", True):
                lines.append("STAGE2: SEMANTIC -> unavailable")
                err = s.get("error")
                if err:
                    lines.append(f"        error: {err}")
            else:
                lines.append(f"STAGE2: SEMANTIC -> selected={s.get('detected_selected', [])}")
                if debug:
                    for row in (s.get("scores", []) or [])[:8]:
                        try:
                            score = float(row.get("score"))
                        except Exception:
                            score = 0.0
                        lines.append(f"        score {row.get('symptom')}: {score:.4f} (anchor: {row.get('best_anchor')!r})")
    final = report.get("final", {}) or {}
    lines.append(f"FINAL:  {final.get('symptoms', [])} (source={final.get('source')})")
    return "\n".join(lines)


def _filter_dosage_for_age(age_group_text: str, user_age: int) -> str:
    """Return only the dosage line(s) applicable to the user's age.

    The Age Group field contains multiple lines like:
      Adults (18+ years): 1 tablet every 6 hours …
      Adolescents (12-17 years): 1 tablet every 6-8 hours …
      Children (7 to 12 years old): ½ tablet …

    We parse each line, check if user_age falls in that bracket,
    and return only matching lines.  If nothing matches, return the
    full text as-is (safe fallback).
    """
    if not age_group_text or not age_group_text.strip():
        return ""

    lines = [l.strip() for l in age_group_text.replace('\\n', '\n').split('\n') if l.strip()]
    if not lines:
        return age_group_text

    matched: List[str] = []
    for line in lines:
        low = line.lower()

        # Pattern: "(18+ years)" or "18+ years"
        plus = re.findall(r'(\d+)\s*\+\s*(?:years|year|yo)', low)
        if plus:
            min_v = min(int(x) for x in plus)
            if user_age >= min_v:
                matched.append(line)
            continue

        # Pattern: "(12-17 years)" or "2 – 6 years" or "7 to 12 years"
        ranges = re.findall(r'(\d+)\s*(?:-|–|to)\s*(\d+)\s*(?:years|year|yo|months)', low)
        if ranges:
            hit = False
            for (a, b) in ranges:
                lo, hi = int(a), int(b)
                if lo <= user_age <= hi:
                    hit = True
                    break
            if hit:
                matched.append(line)
            continue

        # Generic "adults" with no numbers
        if 'adult' in low and user_age >= 18:
            matched.append(line)
            continue

        # Generic "children" / "kids" with no numbers
        if ('children' in low or 'kids' in low) and user_age < 18:
            matched.append(line)
            continue

        # Lines with no age info (instructions like "Give with or without meals.")
        if not re.search(r'\d+', low):
            matched.append(line)

    if not matched:
        return age_group_text  # fallback: return everything
    return '\n'.join(matched)


def _compute_recommendation(
    *,
    text: str,
    age: int,
    cough_type: Optional[str] = None,
    debug: bool = False,
    show_flow: bool = False,
) -> Dict[str, Any]:
    """Shared backend for both HTML results and JSON API."""

    try:
        from mendo_core.step3_hybrid import extract_symptoms_hybrid_report
    except Exception as e:
        return {"ok": False, "error": f"hybrid extractor unavailable: {e}"}

    report = extract_symptoms_hybrid_report(
        text,
        semantic_threshold=0.65,
        semantic_top_margin=0.08,
        semantic_max_symptoms=3,
        enable_semantic_fallback=True,
    )

    detected = list(report.get("final", {}).get("symptoms", []) or [])
    detected = _apply_cough_override(detected, cough_type)

    rows, ds_err = _load_mendo_rows()
    if rows is None:
        return {"ok": False, "error": ds_err or "dataset unavailable"}

    try:
        from mendo_core.step4_recommend import recommend_from_dataset
    except Exception as e:
        return {"ok": False, "error": f"recommender unavailable: {e}"}

    rec = recommend_from_dataset(detected, rows, user_age=age, user_input=text)

    clarify = {"needed": False, "question": ""}
    recommendations: List[Dict[str, Any]] = []
    filtered_out: List[Dict[str, Any]] = []
    warnings: List[str] = rec.get("warnings", []) or []

    if rec.get("action") == "ask_clarify":
        clarify = {"needed": True, "question": rec.get("question") or "Please clarify your cough type."}
    elif rec.get("action") == "recommend":
        for r in rec.get("recommendations", []) or []:
            reasons = r.get("reasons", []) or []
            recommendations.append(
                {
                    "brand": r.get("brand"),
                    "active_ingredients": r.get("active_ingredients"),
                    "reason": _reason_text(list(reasons)),
                    "dosage_form": r.get("dosage_form"),
                    "dosage": _filter_dosage_for_age(r.get("age_group", ""), age),
                    "notes": r.get("notes", ""),
                    "drug_category": r.get("drug_category", ""),
                    "condition_label": r.get("condition_label", ""),
                }
            )

    return {
        "ok": True,
        "text": text,
        "age": age,
        "detected_labels": detected,
        "recommendations": recommendations,
        "warnings": warnings,
        "clarify": clarify,
        "flow_text": _flow_text(report, debug=debug) if show_flow else "",
        "age_filtered_out": filtered_out,
    }

@app.route("/")
@app.route("/index")
def index():
    return redirect(url_for("nlp"))

@app.route("/warning")
def warning():
    return render_template("warning.html")

@app.route("/disclaimer")
def disclaimer():
    return render_template("disclaimer.html")

@app.route("/welcome")
def welcome():
    return render_template("welcome.html")


@app.route("/nlp")
def nlp():
    return render_template("nlp.html")


@app.post("/nlp/results")
def nlp_results():
    # Legacy POST route — the SPA uses /api/recommend via AJAX now.
    return redirect(url_for("nlp"))


@app.post("/api/recommend")
def api_recommend():
    payload = request.get_json(silent=True) or {}
    text = str(payload.get("text") or "").strip()
    age_raw = payload.get("age")
    debug = bool(payload.get("debug"))
    show_flow = bool(payload.get("show_flow"))
    cough_type = payload.get("cough_type")

    if not text:
        return jsonify({"error": "missing text"}), 400

    try:
        age = int(age_raw)
    except Exception:
        return jsonify({"error": "missing or invalid age"}), 400
    if age < 0 or age > 120:
        return jsonify({"error": "age out of range"}), 400

    data = _compute_recommendation(text=text, age=age, cough_type=cough_type, debug=debug, show_flow=show_flow)
    if not data.get("ok"):
        return jsonify({"error": data.get("error") or "unknown error"}), 500

    # UI requested: do not return checklist for display; keep only essentials.
    recs = data.get("recommendations", [])

    # ── Enrich with stock data from POS ──
    if POS_AVAILABLE:
        inv_items = list_inventory(active_only=True)
        inv_map = {it["brand"]: it for it in inv_items}
        for r in recs:
            it = inv_map.get(r.get("brand"))
            if it:
                r["stock"] = {
                    "inventory_id": it["id"],
                    "in_stock": it["stock_quantity"] > 0,
                    "quantity": it["stock_quantity"],
                    "unit_price": it["unit_price"],
                    "low_stock": 0 < it["stock_quantity"] <= it["min_stock_level"],
                }
            else:
                r["stock"] = {"inventory_id": 0, "in_stock": False, "quantity": 0,
                              "unit_price": 0, "low_stock": False}

    return jsonify(
        {
            "detected_labels": data.get("detected_labels", []),
            "recommendations": recs,
            "warnings": data.get("warnings", []),
            "clarify": data.get("clarify", {}),
            "flow_text": data.get("flow_text", ""),
            "age_filtered_out": data.get("age_filtered_out", []),
            "pos_available": POS_AVAILABLE,
        }
    )


# ─────────────────────────────────────────────────
# Vend / Buy API  (kiosk direct-purchase + dispense)
# ─────────────────────────────────────────────────

@app.post("/api/vend")
def api_vend():
    """Purchase a single medicine and trigger vending machine dispense.

    JSON body: {"inventory_id": int, "brand": str, "age": int}
    Returns:   {"success": True, "transaction": {...}, "dispensed": bool}
    """
    if not POS_AVAILABLE:
        return jsonify({"error": "POS system not available"}), 503

    payload = request.get_json(silent=True) or {}
    inv_id = int(payload.get("inventory_id", 0))
    brand = str(payload.get("brand", ""))
    age = payload.get("age")

    if not inv_id:
        return jsonify({"error": "missing inventory_id"}), 400

    # Check stock
    item = get_inventory_item(inv_id)
    if not item:
        return jsonify({"error": "Product not found"}), 404
    if item["stock_quantity"] <= 0:
        return jsonify({"error": "Out of stock"}), 400

    # Create a 1-item transaction (kiosk self-service)
    try:
        result = create_transaction(
            items=[{"inventory_id": inv_id, "quantity": 1}],
            payment_method="kiosk",
            amount_tendered=item["unit_price"],
            cashier_id=None,  # kiosk / self-service (no cashier)
            customer_age=int(age) if age else None,
            customer_note=f"Kiosk vend: {brand}",
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # Attempt hardware dispense
    dispensed = False
    dispense_msg = "No hardware connected (simulated)"
    if _VEND_BRIDGE and _VEND_BRIDGE.is_connected():
        try:
            ok = _VEND_BRIDGE.dispense_by_brand(brand)
            dispensed = ok
            dispense_msg = "Dispensed OK" if ok else "Dispense command sent but no ACK"
        except Exception as hw_err:
            dispense_msg = f"Hardware error: {hw_err}"
    elif _VEND_BRIDGE:
        try:
            _VEND_BRIDGE.connect()
            ok = _VEND_BRIDGE.dispense_by_brand(brand)
            dispensed = ok
            dispense_msg = "Dispensed OK" if ok else "Dispense command sent but no ACK"
        except Exception as hw_err:
            dispense_msg = f"Hardware error: {hw_err}"

    return jsonify({
        "success": True,
        "transaction": result,
        "dispensed": dispensed,
        "dispense_msg": dispense_msg,
    })


@app.post("/api/vend/config")
def api_vend_config():
    """Return vending machine slot configuration."""
    import json as _json
    config_path = os.path.join(_ROOT, "hardware", "config.json")
    if os.path.exists(config_path):
        with open(config_path) as f:
            return jsonify(_json.load(f))
    return jsonify({"slots": {}, "error": "config not found"})


# ─────────────────────────────────────────────────
# Batch Vend (cart checkout + multi-dispense)
# ─────────────────────────────────────────────────

@app.post("/api/vend/batch")
def api_vend_batch():
    """Purchase multiple medicines (with quantities) and trigger dispensing.

    JSON body:
        {
            "items": [{"inventory_id": int, "brand": str, "quantity": int}, ...],
            "age": int,
            "amount_tendered": float
        }
    Returns:
        {
            "success": true,
            "transaction": {...},
            "dispense_results": [
                {"brand": str, "dispensed": bool, "qty_dispensed": int, "message": str, "no_slot": bool}, ...
            ]
        }
    """
    if not POS_AVAILABLE:
        return jsonify({"error": "POS system not available"}), 503

    payload = request.get_json(silent=True) or {}
    items_raw = payload.get("items", [])
    age = payload.get("age")
    amount_tendered = float(payload.get("amount_tendered", 0))

    if not items_raw:
        return jsonify({"error": "Cart is empty"}), 400

    # Build transaction items list
    txn_items = []
    for it in items_raw:
        inv_id = int(it.get("inventory_id", 0))
        qty = int(it.get("quantity", 1))
        if not inv_id or qty < 1:
            return jsonify({"error": f"Invalid item: id={inv_id}, qty={qty}"}), 400
        txn_items.append({"inventory_id": inv_id, "quantity": qty})

    # Create multi-item transaction
    try:
        result = create_transaction(
            items=txn_items,
            payment_method="kiosk",
            amount_tendered=amount_tendered,
            cashier_id=None,
            customer_age=int(age) if age else None,
            customer_note="Kiosk batch vend",
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    # Dispense all items simultaneously via hardware BATCH command
    dispense_results = []

    # Build brand → qty map for brands that have hardware slots
    brand_qty_map = {}
    no_slot_brands = []
    for it in items_raw:
        brand = str(it.get("brand", ""))
        qty = int(it.get("quantity", 1))
        if _VEND_BRIDGE:
            slot = _VEND_BRIDGE.get_slot(brand)
            if slot is not None:
                brand_qty_map[brand] = qty
            else:
                no_slot_brands.append((brand, qty))
        else:
            no_slot_brands.append((brand, qty))

    # Ensure connected
    if _VEND_BRIDGE and brand_qty_map and not _VEND_BRIDGE.is_connected():
        try:
            _VEND_BRIDGE.connect()
        except Exception:
            pass

    # Send single BATCH command (all slots spin simultaneously)
    if _VEND_BRIDGE and brand_qty_map and _VEND_BRIDGE.is_connected():
        try:
            batch_result = _VEND_BRIDGE.dispense_batch_by_brands(brand_qty_map)
            for brand, info in batch_result.items():
                dispense_results.append({
                    "brand": brand,
                    "dispensed": info["dispensed"],
                    "qty_dispensed": info["qty"],
                    "message": f"Dispensed {info['qty']}/{brand_qty_map[brand]}" if info["dispensed"] else (info.get("error") or "Dispense failed"),
                    "no_slot": info["slot"] is None,
                })
        except Exception as hw_err:
            for brand, qty in brand_qty_map.items():
                dispense_results.append({
                    "brand": brand,
                    "dispensed": False,
                    "qty_dispensed": 0,
                    "message": f"Hardware error: {hw_err}",
                    "no_slot": False,
                })
    elif brand_qty_map:
        # Bridge exists but not connected
        for brand, qty in brand_qty_map.items():
            dispense_results.append({
                "brand": brand,
                "dispensed": False,
                "qty_dispensed": 0,
                "message": "Hardware not connected (simulated)",
                "no_slot": False,
            })

    # Brands with no hardware slot
    for brand, qty in no_slot_brands:
        dispense_results.append({
            "brand": brand,
            "dispensed": False,
            "qty_dispensed": 0,
            "message": "No vending slot mapped — collect from counter",
            "no_slot": True,
        })

    return jsonify({
        "success": True,
        "transaction": result,
        "dispense_results": dispense_results,
    })


# ─────────────────────────────────────────────────
# Kiosk Shop Inventory (browse OTC without AI)
# ─────────────────────────────────────────────────

@app.get("/api/kiosk/inventory")
def api_kiosk_inventory():
    """Return active POS inventory for the kiosk shop screen.

    No auth required — this is the customer-facing kiosk.
    Returns: [{"id", "brand", "generic_name", "category", "dosage_form",
               "unit_price", "stock_quantity", "in_stock", "low_stock"}, ...]
    """
    if not POS_AVAILABLE:
        return jsonify({"error": "POS system not available"}), 503

    items = list_inventory(active_only=True)
    return jsonify([
        {
            "id": it["id"],
            "brand": it["brand"],
            "generic_name": it.get("generic_name", ""),
            "category": it.get("category", ""),
            "dosage_form": it.get("dosage_form", ""),
            "unit_price": it["unit_price"],
            "stock_quantity": it["stock_quantity"],
            "in_stock": it["stock_quantity"] > 0,
            "low_stock": 0 < it["stock_quantity"] <= it.get("min_stock_level", 5),
        }
        for it in items
    ])


@app.post("/api/stt")
def api_stt():
    """Offline speech-to-text.

    Expects multipart/form-data with `audio` as WAV.
    Returns: {"text": "..."}
    """

    f = request.files.get("audio")
    if not f:
        return jsonify({"error": "missing audio file"}), 400

    # Only accept wav to avoid ffmpeg dependency.
    filename = str(getattr(f, "filename", "") or "").lower()
    if filename and not filename.endswith(".wav"):
        return jsonify({"error": "unsupported audio format; please send WAV"}), 400

    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(prefix="mendo_stt_", suffix=".wav")
        os.close(fd)
        f.save(tmp_path)
        text = _transcribe_wav_file(tmp_path)
        return jsonify({"text": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

@app.route("/assess", methods = ["GET", "POST"])
def assess():
    if not LEGACY_MODEL_AVAILABLE or vectorizer is None or encoder is None or svm_model is None:
        flash("Legacy SVM model files are missing; use Symptom Check (Hybrid NLP) instead.")
        return redirect(url_for("nlp"))

    if request.method == "GET":
        return render_template("assess.html")

    text = str(request.form.get("input_data") or "").strip()
    if not text:
        flash("Please enter symptoms.")
        return render_template("assess.html")

    try:
        X = vectorizer.transform([text])
        pred = svm_model.predict(X)
        label = encoder.inverse_transform(pred)[0]
    except Exception as e:
        flash(f"Legacy model prediction failed: {e}")
        return render_template("assess.html")

    # Keep legacy flow self-contained (no DB requirement).
    return render_template("result.html", item=[(0, text, str(label))])

@app.route("/finished")
def finished():
    return render_template("finished.html")

@app.route("/result", methods = ["GET", "POST"])
def result():
    if not shopsql:
        flash("Database features not available.")
        return redirect(url_for("nlp"))
    cur = shopsql.connection.cursor()
    cur.execute("SELECT * FROM predictiontable ORDER BY id DESC")
    item = cur.fetchall()
    cur.execute("DELETE FROM predictiontable")
    cur.close()
    return render_template("result.html", item=item)

@app.route("/assessagain")
def assessagain():
    if not shopsql:
        return redirect(url_for("welcome"))
    cur = shopsql.connection.cursor()
    cur.execute("DELETE FROM predictiontable")
    shopsql.connection.commit()
    cur.close()
    return render_template("welcome.html")


@app.route("/shop")
def shop():
    if not shopsql:
        flash("Shop requires database (not needed for symptom detection).")
        return redirect(url_for("nlp"))
    curs = shopsql.connection.cursor()
    curs.execute('SELECT * FROM shopdatabase')
    item = curs.fetchall()
    curs.close()
    return render_template("shop.html", item=item)


@app.route("/itemdescription/<int:item_id>")
def itemdescription(item_id):
    if not shopsql:
        return redirect(url_for("nlp"))
    cur = shopsql.connection.cursor()
    # SELECT * FROM shopdatabase WHERE item = :item_id LIMIT 1 ORDER BY item DESC LIMIT 1 ORDER    
    cur.execute("SELECT * FROM shopdatabase WHERE item_id = %s LIMIT 1", (item_id,))
    item = cur.fetchone()
    return render_template("itemdescription.html", item=item)

@app.route("/addtocart", methods = ["GET", "POST"])
def addtocart():
    if not shopsql:
        return redirect(url_for("nlp"))
    cur = shopsql.connection.cursor()
    
    if request.method == "POST":
        try:
            item_id = request.form['item_id']
            qty = request.form['qty']
            item_name = request.form['item_name']
            
            # Check if quantity is greater than 0
            # if qty <= 0:
            #   flash("Invalid quantity. Quantity must be greater than 0.")
            #    return redirect(url_for("shop"))
            
            
            cur.execute("SELECT * FROM shopdatabase WHERE item_id = %s", (item_id,))
            item = cur.fetchall()
            
            if item:
                # Calculate total price
                # total_price = qty * item['price']
                
                cur.execute("INSERT INTO cartdatabase (item_id, item_name, qty) VALUES (%s,%s,%s)", (item_id, item_name, qty,))
                shopsql.connection.commit()
                flash("Item added to cart!")
            
            else:
                return "ITEM ALREADY ADDED TO CART!"
                
            return redirect(url_for("shop"))
        
        except Exception as e:
            return f"ERROR OCCURRED: Unable to add item to cart. {str(e)}"
    else:
        cur.execute("SELECT * FROM shopdatabase")
        item = cur.fetchall()
        print(type(item))
        return render_template("shop.html", item=item)
        

@app.route("/cart", methods=["GET", "POST"])
def cart():
    if not shopsql:
        return redirect(url_for("nlp"))
    cur = shopsql.connection.cursor()
    cur.execute("""
        SELECT shopdatabase.item_id, shopdatabase.item_name, cartdatabase.qty, shopdatabase.price
        FROM shopdatabase
        INNER JOIN cartdatabase ON shopdatabase.item_id = cartdatabase.item_id
    """)
    item = cur.fetchall()
    return render_template("cart.html", item=item)
    

@app.route('/deleteitem/<int:item_id>', methods=['GET','POST'])
def deleteitem(item_id):
    if not shopsql:
        return redirect(url_for("nlp"))
    cur = shopsql.connection.cursor()
    cur.execute("DELETE FROM shopdatabase WHERE item_id = %s", (item_id,))
    shopsql.connection.commit()
    flash("Data has been deleted successfully!")
    cur.close()
    return redirect(url_for("admindashboard"))

@app.route('/cartitemdelete/<int:item_id>', methods=['GET','POST'])
def deletecartitem(item_id):
    if not shopsql:
        return redirect(url_for("nlp"))
    cur = shopsql.connection.cursor()
    cur.execute("DELETE FROM cartdatabase WHERE item_id = %s", (item_id,))
    shopsql.connection.commit()
    flash("Item has been removed")
    cur.close()
    return redirect(url_for("cart"))


@app.post("/purchased")
def purchased():
    if not shopsql:
        return redirect(url_for("nlp"))
    # get all the items from the cartdatabase
    cur = shopsql.connection.cursor()
    cur.execute("SELECT * FROM cartdatabase");
    items = cur.fetchall()
    
    # create outtable
    cur.execute("INSERT INTO outtable (total_price) VALUES (0.00)");
    shopsql.connection.commit()
    outtable_id = cur.lastrowid
    
    total_price = 0
    
    for item in items:
        # get medicine from shopdatabase
        cur.execute("SELECT * FROM shopdatabase WHERE item_id = %s", (item[0],))
        shopitem = cur.fetchone()
        
        # insert new entry into outtable
        cur.execute("INSERT INTO outtable_shopdatabase (item_id, price, qty, outtable_id) VALUES (%s, %s, %s, %s)", (item[0], shopitem[3], item[2], outtable_id))   
        
        # update the quantity from a specific item in the shopdatabase
        cur.execute("UPDATE shopdatabase SET qty = %s WHERE item_id = %s", (shopitem[2] - item[2], item[0]))
        
        # add price to the total price
        total_price += (shopitem[3] * item[2])
        
    
    # update total price from the specific outtable
    cur.execute("UPDATE outtable SET total_price = %s WHERE id = %s", (total_price, outtable_id))
    
    # delete all entries from the cartdatabase
    cur.execute("DELETE FROM cartdatabase")
    
    # commit the transaction
    shopsql.connection.commit()
    return render_template("purchased.html")


def array_merge(first_array, second_array):
    if isinstance(first_array, list) and isinstance (second_array, list):
        return first_array + second_array
    elif isinstance (first_array, dict) and isinstance(second_array,dict):
        return dict(list(first_array.items())) + list(second_array.items())
    elif isinstance(first_array,set) and isinstance(second_array,set):
        return first_array.union(second_array)
    return False
    

if __name__ == '__main__':
    app.secret_key = 'super secret key' # paki-change nalang ni later
    app.config['SESSION_TYPE'] = 'filesystem'
    app.run(debug=True)