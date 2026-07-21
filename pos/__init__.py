"""Mendo POS — Point-of-Sale & Inventory system.

Registers admin and shop blueprints.
Database: SQLite stored at ``data/mendo_pos.db`` (zero-config).
"""

from __future__ import annotations

from flask import Flask

from .db import init_db, close_db
from .routes_admin import admin_bp
from .routes_shop import shop_bp
from .routes_consultation import consultation_bp

__all__ = ["init_pos"]


def init_pos(app: Flask) -> None:
    """Attach POS sub-system to a Flask app."""
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()

    # Migrate legacy JSONL logs to SQLite
    try:
        from mendo_core.interaction_logger import migrate_jsonl_to_sqlite
        migrate_jsonl_to_sqlite()
    except Exception:
        pass

    app.register_blueprint(admin_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(consultation_bp)
