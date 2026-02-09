"""Mendo POS — Point-of-Sale & Inventory Blueprint.

Registers all admin / shop / cart / checkout routes.
Database: SQLite stored at ``data/mendo_pos.db`` (zero-config).
"""

from __future__ import annotations

from flask import Flask

from .db import init_db, close_db
from .routes_admin import admin_bp
from .routes_shop import shop_bp

__all__ = ["init_pos"]


def init_pos(app: Flask) -> None:
    """Attach POS sub-system to a Flask app."""
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()

    app.register_blueprint(admin_bp)
    app.register_blueprint(shop_bp)
    print("✓ POS system initialized (SQLite)")
