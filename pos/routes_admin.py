"""POS Admin Blueprint — dashboard, inventory, transactions, stock logs, users."""

from __future__ import annotations

from flask import (
    Blueprint, render_template, request, redirect,
    url_for, session, flash, jsonify,
)

from .auth import login_required, admin_required
from .db import (
    authenticate_user, get_dashboard_stats,
    list_inventory, get_inventory_item, update_stock,
    update_inventory_details,
    list_transactions, count_transactions, get_transaction, void_transaction,
    get_stock_logs, list_users, create_user, change_password,
    toggle_user_active,
)

from mendo_core.interaction_logger import (
    get_interaction_logs,
    count_interaction_logs,
    count_logs_today,
    get_most_common_symptom,
    export_logs_as_csv as export_logs_csv,
    export_logs_as_json as export_logs_json,
    export_logs_as_pdf as export_logs_pdf,
)

admin_bp = Blueprint(
    "admin",
    __name__,
    url_prefix="/admin",
)


# ─────────── Auth ───────────

@admin_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = authenticate_user(username, password)
        if user:
            session["pos_user_id"] = user["id"]
            session["pos_user_name"] = user["full_name"]
            session["pos_user_role"] = user["role"]
            next_url = request.args.get("next", url_for("admin.dashboard"))
            return redirect(next_url)
        flash("Invalid username or password.", "error")
    return render_template("pos/login.html")


@admin_bp.route("/logout")
def logout():
    session.pop("pos_user_id", None)
    session.pop("pos_user_name", None)
    session.pop("pos_user_role", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("admin.login"))


# ─────────── Dashboard ───────────

@admin_bp.route("/")
@admin_bp.route("/dashboard")
@login_required
def dashboard(current_user=None):
    stats = get_dashboard_stats()
    return render_template("pos/dashboard.html", stats=stats, user=current_user)


# ─────────── Inventory ───────────

@admin_bp.route("/inventory")
@login_required
def inventory(current_user=None):
    items = list_inventory()
    return render_template("pos/inventory.html", items=items, user=current_user)


@admin_bp.route("/api/inventory", methods=["GET"])
@login_required
def api_inventory(current_user=None):
    items = list_inventory()
    return jsonify(items)


@admin_bp.route("/api/inventory/<int:item_id>/restock", methods=["POST"])
@login_required
def api_restock(item_id, current_user=None):
    try:
        data = request.get_json(force=True)
        qty = int(data.get("quantity", 0))
        if qty <= 0:
            return jsonify({"error": "Quantity must be positive"}), 400
        item = get_inventory_item(item_id)
        if not item:
            return jsonify({"error": "Item not found"}), 404
        new_qty = item["stock_quantity"] + qty
        update_stock(item_id, new_qty, "restock",
                     reference=f"Restocked +{qty} units",
                     performed_by=current_user["id"])
        return jsonify({"success": True, "new_quantity": new_qty, "brand": item["brand"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@admin_bp.route("/api/inventory/<int:item_id>/adjust", methods=["POST"])
@login_required
def api_adjust(item_id, current_user=None):
    try:
        data = request.get_json(force=True)
        new_qty = int(data.get("quantity", 0))
        reason = data.get("reason", "Manual adjustment")
        if new_qty < 0:
            return jsonify({"error": "Quantity cannot be negative"}), 400
        item = get_inventory_item(item_id)
        if not item:
            return jsonify({"error": "Item not found"}), 404
        update_stock(item_id, new_qty, "adjustment",
                     reference=reason,
                     performed_by=current_user["id"])
        return jsonify({"success": True, "new_quantity": new_qty, "brand": item["brand"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@admin_bp.route("/api/inventory/<int:item_id>/details", methods=["POST"])
@login_required
def api_update_details(item_id, current_user=None):
    try:
        data = request.get_json(force=True)
        kwargs = {}
        if "unit_price" in data:
            kwargs["unit_price"] = float(data["unit_price"])
        if "min_stock_level" in data:
            kwargs["min_stock_level"] = int(data["min_stock_level"])
        if "is_active" in data:
            kwargs["is_active"] = 1 if data["is_active"] else 0
        update_inventory_details(item_id, **kwargs)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ─────────── Transactions ───────────

@admin_bp.route("/transactions")
@login_required
def transactions(current_user=None):
    page = int(request.args.get("page", 1))
    per_page = 20
    status = request.args.get("status", "")
    txns = list_transactions(limit=per_page, offset=(page - 1) * per_page, status=status)
    total = count_transactions(status=status)
    total_pages = max(1, (total + per_page - 1) // per_page)
    return render_template("pos/transactions.html", transactions=txns, user=current_user,
                           page=page, status_filter=status, total_pages=total_pages)


@admin_bp.route("/api/transactions/<int:txn_id>")
@login_required
def api_transaction_detail(txn_id, current_user=None):
    txn = get_transaction(txn_id)
    if not txn:
        return jsonify({"error": "Not found"}), 404
    return jsonify(txn)


@admin_bp.route("/api/transactions/<int:txn_id>/void", methods=["POST"])
@admin_required
def api_void_transaction(txn_id, current_user=None):
    try:
        void_transaction(txn_id, performed_by=current_user["id"])
        return jsonify({"success": True})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# ─────────── Stock Logs ───────────

@admin_bp.route("/stock-logs")
@login_required
def stock_logs(current_user=None):
    inv_id = int(request.args.get("inventory_id", 0))
    logs = get_stock_logs(limit=200, inventory_id=inv_id)
    all_items = list_inventory()
    return render_template("pos/stock_logs.html", logs=logs, user=current_user,
                           inv_filter=inv_id, all_items=all_items)


# ─────────── User Management ───────────

@admin_bp.route("/users")
@admin_required
def users(current_user=None):
    all_users = list_users()
    return render_template("pos/users.html", users=all_users, user=current_user)


@admin_bp.route("/api/users", methods=["POST"])
@admin_required
def api_create_user(current_user=None):
    try:
        data = request.get_json(force=True)
        username = data.get("username", "").strip()
        password = data.get("password", "")
        full_name = data.get("full_name", "").strip()
        role = data.get("role", "staff")
        if not username or not password or not full_name:
            return jsonify({"error": "All fields are required"}), 400
        if role not in ("admin", "staff"):
            return jsonify({"error": "Invalid role"}), 400
        create_user(username, password, full_name, role)
        return jsonify({"success": True, "message": f"User '{username}' created"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@admin_bp.route("/api/users/<int:uid>/password", methods=["POST"])
@admin_required
def api_change_password(uid, current_user=None):
    try:
        data = request.get_json(force=True)
        new_password = data.get("password", "")
        if len(new_password) < 4:
            return jsonify({"error": "Password must be at least 4 characters"}), 400
        change_password(uid, new_password)
        return jsonify({"success": True, "message": "Password updated"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@admin_bp.route("/api/users/<int:uid>/toggle", methods=["POST"])
@admin_required
def api_toggle_user(uid, current_user=None):
    try:
        if uid == current_user["id"]:
            return jsonify({"error": "Cannot deactivate your own account"}), 400
        new_status = toggle_user_active(uid)
        return jsonify({"success": True, "is_active": new_status})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400


# ─────────── Interaction Logs Dashboard ───────────

@admin_bp.route("/logs")
@login_required
def logs_dashboard(current_user=None):
    """Render the interaction logs dashboard page."""
    total = count_interaction_logs()
    today = count_logs_today()
    top_symptom = get_most_common_symptom()
    return render_template("pos/logs.html", user=current_user,
                           total_logs=total, today_logs=today,
                           top_symptom=top_symptom)


@admin_bp.route("/api/logs", methods=["GET"])
@login_required
def api_logs(current_user=None):
    """Return interaction logs as paginated JSON (for frontend table)."""
    limit = int(request.args.get("limit", 100))
    offset = int(request.args.get("offset", 0))
    search = request.args.get("search", "").strip()
    logs = get_interaction_logs(limit=limit, offset=offset, search=search)
    total = count_interaction_logs(search=search)
    return jsonify({"logs": logs, "total": total})


@admin_bp.route("/api/logs/export/json")
@login_required
def api_export_logs_json(current_user=None):
    data = export_logs_json()
    if not data or data == "[]":
        return jsonify({"error": "No logs found"}), 404
    from flask import Response
    return Response(data, mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=interaction_logs.json"})


@admin_bp.route("/api/logs/export/csv")
@login_required
def api_export_logs_csv(current_user=None):
    data = export_logs_csv()
    if not data:
        return jsonify({"error": "No logs found"}), 404
    from flask import Response
    return Response(data, mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=interaction_logs.csv"})


@admin_bp.route("/api/logs/export/pdf")
@login_required
def api_export_logs_pdf(current_user=None):
    data = export_logs_pdf()
    if not data:
        return jsonify({"error": "No logs found"}), 404
    from flask import Response
    return Response(data, mimetype="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=interaction_logs.pdf"})
