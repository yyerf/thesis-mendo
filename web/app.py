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
