"""POS Shop Blueprint — browse, cart, checkout, receipt (cashier-facing)."""

from __future__ import annotations

from flask import (
    Blueprint, render_template, request, session, jsonify,
)

# Optional hardware bridge (Arduino)
_VEND_BRIDGE = None
try:
    from hardware.serial_bridge import VendoBridge
    _VEND_BRIDGE = VendoBridge()
except Exception:
    _VEND_BRIDGE = None

from .auth import login_required
from .db import (
    list_inventory, get_inventory_item, create_transaction,
    get_transaction,
)

shop_bp = Blueprint(
    "shop",
    __name__,
    url_prefix="/shop",
)


# ─────────── Shop page (SPA cashier view) ───────────

@shop_bp.route("/")
@login_required
def index(current_user=None):
    return render_template("pos/shop.html", user=current_user)


# ─────────── Product list API ───────────

@shop_bp.route("/api/products")
@login_required
def api_products(current_user=None):
    items = list_inventory(active_only=True)
    return jsonify([
        {
            "id": it["id"],
            "brand": it["brand"],
            "generic_name": it["generic_name"],
            "category": it["category"],
            "dosage_form": it["dosage_form"],
            "unit_price": it["unit_price"],
            "stock_quantity": it["stock_quantity"],
        }
        for it in items
    ])


# ─────────── Cart — session-based ───────────

def _get_cart() -> list:
    return session.get("pos_cart", [])


def _set_cart(cart: list) -> None:
    session["pos_cart"] = cart


@shop_bp.route("/api/cart", methods=["GET"])
@login_required
def api_get_cart(current_user=None):
    cart = _get_cart()
    enriched = []
    total = 0.0
    for ci in cart:
        item = get_inventory_item(ci["inventory_id"])
        if item:
            subtotal = round(item["unit_price"] * ci["quantity"], 2)
            total += subtotal
            enriched.append({
                "inventory_id": item["id"],
                "brand": item["brand"],
                "unit_price": item["unit_price"],
                "quantity": ci["quantity"],
                "stock_available": item["stock_quantity"],
                "subtotal": subtotal,
            })
    return jsonify({"items": enriched, "total": round(total, 2), "item_count": sum(c["quantity"] for c in cart)})


@shop_bp.route("/api/cart/add", methods=["POST"])
@login_required
def api_cart_add(current_user=None):
    data = request.get_json(force=True)
    inv_id = int(data.get("inventory_id", 0))
    qty = int(data.get("quantity", 1))
    if qty <= 0:
        return jsonify({"error": "Quantity must be positive"}), 400
    item = get_inventory_item(inv_id)
    if not item:
        return jsonify({"error": "Product not found"}), 404
    if not item["is_active"]:
        return jsonify({"error": "Product is inactive"}), 400

    cart = _get_cart()
    # Check if already in cart
    for ci in cart:
        if ci["inventory_id"] == inv_id:
            new_qty = ci["quantity"] + qty
            if new_qty > item["stock_quantity"]:
                return jsonify({"error": f"Not enough stock (available: {item['stock_quantity']})"}), 400
            ci["quantity"] = new_qty
            _set_cart(cart)
            return jsonify({"success": True, "message": f"{item['brand']} updated in cart"})
    # New item
    if qty > item["stock_quantity"]:
        return jsonify({"error": f"Not enough stock (available: {item['stock_quantity']})"}), 400
    cart.append({"inventory_id": inv_id, "quantity": qty})
    _set_cart(cart)
    return jsonify({"success": True, "message": f"{item['brand']} added to cart"})


@shop_bp.route("/api/cart/update", methods=["POST"])
@login_required
def api_cart_update(current_user=None):
    data = request.get_json(force=True)
    inv_id = int(data.get("inventory_id", 0))
    qty = int(data.get("quantity", 0))
    cart = _get_cart()
    if qty <= 0:
        cart = [c for c in cart if c["inventory_id"] != inv_id]
    else:
        item = get_inventory_item(inv_id)
        if item and qty > item["stock_quantity"]:
            return jsonify({"error": f"Not enough stock (available: {item['stock_quantity']})"}), 400
        for ci in cart:
            if ci["inventory_id"] == inv_id:
                ci["quantity"] = qty
                break
    _set_cart(cart)
    return jsonify({"success": True})


@shop_bp.route("/api/cart/remove", methods=["POST"])
@login_required
def api_cart_remove(current_user=None):
    data = request.get_json(force=True)
    inv_id = int(data.get("inventory_id", 0))
    cart = [c for c in _get_cart() if c["inventory_id"] != inv_id]
    _set_cart(cart)
    return jsonify({"success": True})


@shop_bp.route("/api/cart/clear", methods=["POST"])
@login_required
def api_cart_clear(current_user=None):
    _set_cart([])
    return jsonify({"success": True})


# ─────────── Checkout ───────────

@shop_bp.route("/api/checkout", methods=["POST"])
@login_required
def api_checkout(current_user=None):
    try:
        data = request.get_json(force=True)
        cart = _get_cart()
        if not cart:
            return jsonify({"error": "Cart is empty"}), 400

        payment_method = data.get("payment_method", "cash")
        amount_tendered = float(data.get("amount_tendered", 0))

        result = create_transaction(
            items=cart,
            payment_method=payment_method,
            amount_tendered=amount_tendered,
            cashier_id=current_user["id"],
            customer_age=data.get("customer_age"),
            customer_note=data.get("customer_note", ""),
        )

        # Optional: dispense items via hardware if mapped
        dispense_results = []
        if _VEND_BRIDGE:
            try:
                if not _VEND_BRIDGE.is_connected():
                    _VEND_BRIDGE.connect()
                for li in result.get("items", []):
                    try:
                        ok = _VEND_BRIDGE.dispense_by_brand(li["brand"])
                        dispense_results.append({"brand": li["brand"], "dispensed": ok})
                    except Exception as e:
                        dispense_results.append({"brand": li["brand"], "dispensed": False, "error": str(e)})
            except Exception as e:
                dispense_results.append({"brand": "__hardware__", "dispensed": False, "error": str(e)})

        # Clear cart after successful checkout
        _set_cart([])
        return jsonify({**result, "dispense_results": dispense_results})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@shop_bp.route("/api/receipt/<int:txn_id>")
@login_required
def api_receipt(txn_id, current_user=None):
    txn = get_transaction(txn_id)
    if not txn:
        return jsonify({"error": "Not found"}), 404
    return jsonify(txn)


# ─────────── Stock check for recommendation integration ───────────

@shop_bp.route("/api/stock/check", methods=["POST"])
def api_stock_check():
    """Public endpoint: given a list of brand names, return stock status."""
    data = request.get_json(force=True)
    brands = data.get("brands", [])
    result = {}
    items = list_inventory(active_only=True)
    inv_map = {it["brand"]: it for it in items}
    for b in brands:
        it = inv_map.get(b)
        if it:
            result[b] = {
                "in_stock": it["stock_quantity"] > 0,
                "quantity": it["stock_quantity"],
                "unit_price": it["unit_price"],
                "low_stock": 0 < it["stock_quantity"] <= it["min_stock_level"],
            }
        else:
            result[b] = {"in_stock": False, "quantity": 0, "unit_price": 0, "low_stock": False}
    return jsonify(result)
