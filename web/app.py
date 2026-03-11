"""Mendo POS — Flask application.

Professional Point-of-Sale system for OTC medicine vending.
"""

import os
import logging

from flask import Flask, redirect, url_for

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("mendo")

# ── Flask app ──
app = Flask(__name__, template_folder="templates", static_folder="static")
_default_secret = os.urandom(32).hex()  # random fallback; set MENDO_SECRET_KEY in production
app.secret_key = os.environ.get("MENDO_SECRET_KEY", _default_secret)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("MENDO_HTTPS", "false").lower() == "true"

# ── POS system (SQLite — zero-config) ──
try:
    from pos import init_pos
    init_pos(app)
    log.info("POS system initialized")
except Exception as e:
    log.error("Failed to initialize POS: %s", e)


# ── Preload semantic model (background thread) ──
# The transformer model takes ~25s to load from disk on Raspberry Pi.
# Loading it eagerly in a background thread means the first user query
# never has to wait for the cold-start penalty.
import threading

def _preload_semantic_model():
    try:
        from mendo_core.step3_hybrid import _get_semantic_extractor
        ext = _get_semantic_extractor()
        # Warm up PyTorch buffers with a throwaway encode
        ext.analyze("warmup", threshold=0.99)
        log.info("Semantic model preloaded and warmed up")
    except Exception as e:
        log.warning("Semantic model preload failed (will retry on first query): %s", e)

threading.Thread(target=_preload_semantic_model, daemon=True).start()


# ── Root redirect ──
@app.route("/")
def index():
    return redirect(url_for("consultation.index"))


@app.errorhandler(404)
def not_found(e):
    return redirect(url_for("admin.login"))


@app.errorhandler(500)
def server_error(e):
    log.error("Internal server error: %s", e)
    return "Internal Server Error", 500
