"""POS authentication — login_required & admin_required decorators."""

from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import redirect, request, session, url_for, flash

from .db import get_user_by_id


def login_required(f: Callable) -> Callable:
    """Redirect to login page if no valid POS session."""
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        uid = session.get("pos_user_id")
        if not uid:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("admin.login", next=request.path))
        user = get_user_by_id(uid)
        if not user or not user.get("is_active"):
            session.pop("pos_user_id", None)
            flash("Session expired. Please log in again.", "warning")
            return redirect(url_for("admin.login"))
        kwargs["current_user"] = user
        return f(*args, **kwargs)
    return wrapper


def admin_required(f: Callable) -> Callable:
    """Restrict to admin role only."""
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        uid = session.get("pos_user_id")
        if not uid:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("admin.login", next=request.path))
        user = get_user_by_id(uid)
        if not user or not user.get("is_active"):
            session.pop("pos_user_id", None)
            return redirect(url_for("admin.login"))
        if user["role"] != "admin":
            flash("Admin privileges required.", "error")
            return redirect(url_for("admin.dashboard"))
        kwargs["current_user"] = user
        return f(*args, **kwargs)
    return wrapper
