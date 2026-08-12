"""POS Shop Blueprint — product browsing, cart, checkout (cashier-facing)."""

from __future__ import annotations

import uuid

from flask import (
    Blueprint, render_template, request, session, jsonify,
)

from .auth import login_required
from .db import (
    list_inventory, get_inventory_item,
)
from .order_service import ConsentRequired, InvalidTransition, OrderService, OrderError
from hardware.interface import HardwareFault
from hardware.service import get_hardware_service

shop_bp = Blueprint(
    "shop",
    __name__,
    url_prefix="/shop",
)


# ─────────── Shop page (cashier view) ───────────

@shop_bp.route("/")
@login_required
def index(current_user=None):
    return render_template("pos/shop.html", user=current_user)


# ─────────── Product list API ───────────

@shop_bp.route("/api/products")
@login_required
def api_products(current_user=None):
    items = list_inventory(active_only=True, catalog_only=True)
    return jsonify([
        {
            "id": it["id"],
            "hardware_slot": it.get("hardware_slot"),
            "brand": it["brand"],
            "generic_name": it["generic_name"],
            "category": it["category"],
            "dosage_form": it["dosage_form"],
            "unit_price": it["unit_price"],
            "unit_price_centavos": int(it.get("unit_price_centavos") or round(float(it["unit_price"]) * 100)),
            "stock_quantity": it["stock_quantity"],
            "reserved_quantity": it.get("reserved_quantity", 0),
            "available_quantity": it.get("available_quantity", it["stock_quantity"]),
            "min_stock_level": it.get("min_stock_level", 5),
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
    total_centavos = 0
    for ci in cart:
        item = get_inventory_item(ci["inventory_id"])
        if item and item["is_active"] and item.get("hardware_slot") is not None:
            unit_price_centavos = int(item.get("unit_price_centavos") or round(float(item["unit_price"]) * 100))
            subtotal_centavos = unit_price_centavos * ci["quantity"]
            total_centavos += subtotal_centavos
            enriched.append({
                "inventory_id": item["id"],
                "hardware_slot": item.get("hardware_slot"),
                "brand": item["brand"],
                "generic_name": item.get("generic_name", ""),
                "unit_price": unit_price_centavos / 100,
                "unit_price_centavos": unit_price_centavos,
                "quantity": ci["quantity"],
                "stock_available": item["stock_quantity"],
                "available_quantity": item.get("available_quantity", item["stock_quantity"]),
                "subtotal": subtotal_centavos / 100,
                "subtotal_centavos": subtotal_centavos,
            })
    return jsonify({
        "items": enriched,
        "total": total_centavos / 100,
        "total_centavos": total_centavos,
        "item_count": sum(item["quantity"] for item in enriched),
    })


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
    if item.get("hardware_slot") is None:
        return jsonify({"error": "Product is outside the active hardware catalog"}), 400

    cart = _get_cart()
    for ci in cart:
        if ci["inventory_id"] == inv_id:
            new_qty = ci["quantity"] + qty
            if new_qty > item.get("available_quantity", item["stock_quantity"]):
                return jsonify({"error": f"Not enough stock (available: {item.get('available_quantity', item['stock_quantity'])})"}), 400
            ci["quantity"] = new_qty
            _set_cart(cart)
            return jsonify({"success": True, "message": f"{item['brand']} updated in cart"})
    if qty > item.get("available_quantity", item["stock_quantity"]):
        return jsonify({"error": f"Not enough stock (available: {item.get('available_quantity', item['stock_quantity'])})"}), 400
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
        if item and qty > item.get("available_quantity", item["stock_quantity"]):
            return jsonify({"error": f"Not enough stock (available: {item.get('available_quantity', item['stock_quantity'])})"}), 400
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
    session.pop("pos_order_ref", None)
    return jsonify({"success": True})


# ─────────── Checkout ───────────

@shop_bp.route("/api/checkout", methods=["POST"])
@login_required
def api_checkout(current_user=None):
    """Start the physical cash acceptor for the cashier's current cart.

    Completion is driven by the same durable order polling endpoint as the
    kiosk. No counted-tender shortcut and no medicine-motor command is used in
    this payment-hardware test phase.
    """
    try:
        data = request.get_json(force=True)
        cart = _get_cart()
        if not cart:
            return jsonify({"error": "Cart is empty"}), 400

        if not data.get("no_change_consent"):
            raise ConsentRequired(
                "Confirm that the machine gives no change before starting payment"
            )
        hardware = get_hardware_service()
        if not hardware.ready_for_cash():
            return jsonify({
                "error": "Cash acceptor controller is unhealthy or disconnected",
                "hardware": hardware.status(),
            }), 503
        service = OrderService()
        order = None
        existing_ref = str(session.get("pos_order_ref") or "")
        if existing_ref:
            try:
                existing = service.get_order(existing_ref)
            except OrderError:
                session.pop("pos_order_ref", None)
            else:
                if existing["payment_state"] in {"unpaid", "awaiting_cash", "paid"}:
                    order = existing
                else:
                    session.pop("pos_order_ref", None)
        if order is None:
            key = request.headers.get("Idempotency-Key") or data.get("idempotency_key") or f"cashier-{current_user['id']}-{uuid.uuid4().hex}"
            order = service.create_order(
                cart, idempotency_key=key, source="cashier", payment_method="cash"
            )
            session["pos_order_ref"] = order["order_ref"]
        if order["payment_state"] == "paid":
            order = service.finalize_payment_only_sale(
                order["order_ref"], actor=f"cashier:{current_user['id']}"
            )
        elif order["payment_state"] in {"unpaid", "awaiting_cash"}:
            started = service.start_cash(order["order_ref"], no_change_consent=True)
            try:
                hardware.start_cash(started["session_ref"], order["total_centavos"])
            except Exception:
                if order["payment_state"] == "unpaid":
                    service.reset_cash_start(order["order_ref"])
                raise
            order = service.get_order(order["order_ref"])
        else:
            raise InvalidTransition(
                f"Order cannot collect cash in state {order['payment_state']}"
            )
        return jsonify({
            "success": True,
            "order": order,
            "transaction_ref": order.get("transaction_ref"),
            "amount_due": order["amount_due"],
            "hardware": hardware.status(),
        })

    except (OrderError, ValueError) as e:
        return jsonify({"error": str(e)}), 409
    except HardwareFault as e:
        return jsonify({"error": f"Cash controller error: {e}"}), 503
    except Exception as e:
        return jsonify({"error": f"Checkout failed: {e}"}), 500
