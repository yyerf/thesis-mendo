"""POS Checkout Blueprint — kiosk purchase flow with Xendit cashless payment.

Flow:
  1. Customer selects medicines from recommendation results
  2. Anti-hoarding: max 3 units per item, max 5 distinct items
  3. Fingerprint auth (simulated with button click for demo)
  4. Payment method: Cashless (Xendit invoice) or Cash (coming soon)
  5. On successful payment → inventory deducted, transaction logged
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any, Dict

from flask import (
    Blueprint,
    request,
    jsonify,
    session,
    render_template_string,
    url_for,
)

from .db import (
    get_inventory_item,
    get_inventory_by_brand,
    create_transaction,
    get_db,
)

log = logging.getLogger("mendo.checkout")

checkout_bp = Blueprint("checkout", __name__, url_prefix="/checkout")

_PAYMENT_RETURN_HTML = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Mendo Payment Return</title>
    <style>
        body {
            margin: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            font-family: Inter, Arial, sans-serif;
            background: #f8fafc;
            color: #0f172a;
        }
        .card {
            width: min(92vw, 420px);
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 20px;
            padding: 28px 24px;
            box-shadow: 0 24px 60px rgba(15, 23, 42, 0.12);
            text-align: center;
        }
        h1 { margin: 0 0 10px; font-size: 28px; }
        p { margin: 0; font-size: 15px; line-height: 1.6; color: #475569; }
        .ok { color: #16a34a; }
        .fail { color: #dc2626; }
    </style>
</head>
<body>
    <div class="card">
        <h1 class="{{ 'ok' if result == 'success' else 'fail' }}">
            {{ 'Payment Completed' if result == 'success' else 'Payment Incomplete' }}
        </h1>
        <p>
            {{ message }}
        </p>
    </div>
    <script>
        (function () {
            const payload = {
                source: 'mendo-xendit',
                result: {{ result|tojson }},
                invoiceId: {{ invoice_id|tojson }}
            };
            try {
                if (window.opener && !window.opener.closed) {
                    window.opener.postMessage(payload, window.location.origin);
                }
            } catch (err) {}
            setTimeout(() => {
                try { window.close(); } catch (err) {}
            }, 800);
        })();
    </script>
</body>
</html>
"""

# ── Anti-hoarding limits ──
MAX_QTY_PER_ITEM = 3
MAX_DISTINCT_ITEMS = 5


# ─────────── Kiosk cart (session-based, separate from POS cart) ───────────

def _get_kiosk_cart() -> list:
    return session.get("kiosk_cart", [])


def _set_kiosk_cart(cart: list) -> None:
    session["kiosk_cart"] = cart


@checkout_bp.route("/api/cart", methods=["GET"])
def api_kiosk_cart():
    cart = _get_kiosk_cart()
    enriched = []
    total = 0.0
    for ci in cart:
        item = get_inventory_item(ci["inventory_id"])
        if item and item["is_active"] and item.get("hardware_slot") is not None:
            subtotal = round(item["unit_price"] * ci["quantity"], 2)
            total += subtotal
            enriched.append({
                "inventory_id": item["id"],
                "hardware_slot": item.get("hardware_slot"),
                "brand": item["brand"],
                "generic_name": item.get("generic_name", ""),
                "unit_price": item["unit_price"],
                "quantity": ci["quantity"],
                "stock_available": item["stock_quantity"],
                "subtotal": subtotal,
            })
    return jsonify({
        "items": enriched,
        "total": round(total, 2),
        "item_count": sum(item["quantity"] for item in enriched),
    })


@checkout_bp.route("/api/cart/add", methods=["POST"])
def api_kiosk_cart_add():
    data = request.get_json(force=True)
    brand = str(data.get("brand", "")).strip()
    qty = int(data.get("quantity", 1))

    if qty <= 0:
        return jsonify({"error": "Quantity must be positive"}), 400

    item = get_inventory_by_brand(brand)
    if not item:
        return jsonify({"error": "Product not found"}), 404
    if not item["is_active"]:
        return jsonify({"error": "Product is inactive"}), 400
    if item.get("hardware_slot") is None:
        return jsonify({"error": "Product is outside the active hardware catalog"}), 400
    if item["stock_quantity"] <= 0:
        return jsonify({"error": "Out of stock"}), 400

    cart = _get_kiosk_cart()

    # Anti-hoarding: max distinct items
    existing_ids = {c["inventory_id"] for c in cart}
    if item["id"] not in existing_ids and len(existing_ids) >= MAX_DISTINCT_ITEMS:
        return jsonify({"error": f"Maximum {MAX_DISTINCT_ITEMS} different items allowed per purchase"}), 400

    for ci in cart:
        if ci["inventory_id"] == item["id"]:
            new_qty = ci["quantity"] + qty
            if new_qty > MAX_QTY_PER_ITEM:
                return jsonify({"error": f"Maximum {MAX_QTY_PER_ITEM} units per medicine (anti-hoarding policy)"}), 400
            if new_qty > item["stock_quantity"]:
                return jsonify({"error": f"Not enough stock (available: {item['stock_quantity']})"}), 400
            ci["quantity"] = new_qty
            _set_kiosk_cart(cart)
            return jsonify({"success": True, "message": f"{item['brand']} updated in cart"})

    if qty > MAX_QTY_PER_ITEM:
        return jsonify({"error": f"Maximum {MAX_QTY_PER_ITEM} units per medicine (anti-hoarding policy)"}), 400
    if qty > item["stock_quantity"]:
        return jsonify({"error": f"Not enough stock (available: {item['stock_quantity']})"}), 400

    cart.append({"inventory_id": item["id"], "quantity": qty})
    _set_kiosk_cart(cart)
    return jsonify({"success": True, "message": f"{item['brand']} added to cart"})


@checkout_bp.route("/api/cart/remove", methods=["POST"])
def api_kiosk_cart_remove():
    data = request.get_json(force=True)
    inv_id = int(data.get("inventory_id", 0))
    cart = [c for c in _get_kiosk_cart() if c["inventory_id"] != inv_id]
    _set_kiosk_cart(cart)
    return jsonify({"success": True})


@checkout_bp.route("/api/cart/clear", methods=["POST"])
def api_kiosk_cart_clear():
    _set_kiosk_cart([])
    return jsonify({"success": True})


# ─────────── Fingerprint Auth (simulated) ───────────

@checkout_bp.route("/api/auth/fingerprint", methods=["POST"])
def api_fingerprint_auth():
    """Simulate AS608 fingerprint sensor authentication.
    In production this would talk to the hardware via serial bridge.
    For demo: always succeeds on button click.
    """
    session["kiosk_authenticated"] = True
    return jsonify({
        "success": True,
        "message": "Fingerprint authenticated successfully",
        "authenticated": True,
    })


# ─────────── Xendit Invoice Creation ───────────

@checkout_bp.route("/api/pay/xendit", methods=["POST"])
def api_pay_xendit():
    """Create a Xendit invoice for kiosk cashless payment."""
    if not session.get("kiosk_authenticated"):
        return jsonify({"error": "Please authenticate first (fingerprint scan)"}), 403

    cart = _get_kiosk_cart()
    if not cart:
        return jsonify({"error": "Cart is empty"}), 400

    secret_key = os.environ.get("XENDIT_SECRET_KEY", "")
    if not secret_key:
        return jsonify({"error": "Payment not configured"}), 500

    # Calculate total
    total = 0.0
    invoice_items = []
    for ci in cart:
        item = get_inventory_item(ci["inventory_id"])
        if not item:
            return jsonify({"error": f"Item id={ci['inventory_id']} not found"}), 400
        if not item["is_active"] or item.get("hardware_slot") is None:
            return jsonify({"error": f"{item['brand']} is not available for dispensing"}), 400
        if item["stock_quantity"] < ci["quantity"]:
            return jsonify({"error": f"Not enough stock for {item['brand']}"}), 400
        subtotal = round(item["unit_price"] * ci["quantity"], 2)
        total += subtotal
        invoice_items.append({
            "name": item["brand"],
            "quantity": ci["quantity"],
            "price": item["unit_price"],
        })

    total = round(total, 2)
    external_id = f"MENDO-{uuid.uuid4().hex[:12].upper()}"
    success_url = url_for("checkout.payment_return", result="success", _external=True)
    failure_url = url_for("checkout.payment_return", result="failure", _external=True)

    # Store pending order in session for webhook/callback verification
    session["pending_order"] = {
        "external_id": external_id,
        "cart": cart,
        "total": total,
    }

    try:
        import xendit
        from xendit.apis import InvoiceApi
        from xendit.invoice.model.create_invoice_request import CreateInvoiceRequest

        xendit.set_api_key(secret_key)
        api = InvoiceApi()

        invoice_req = CreateInvoiceRequest(
            external_id=external_id,
            amount=total,
            description=f"Mendo Medicine Purchase ({len(cart)} item(s))",
            currency="PHP",
            invoice_duration=600.0,  # 10 minutes
            success_redirect_url=success_url,
            failure_redirect_url=failure_url,
        )
        invoice = api.create_invoice(invoice_req)
        session["pending_order"]["invoice_id"] = invoice.id
        session.modified = True

        return jsonify({
            "success": True,
            "invoice_id": invoice.id,
            "invoice_url": invoice.invoice_url,
            "external_id": external_id,
            "amount": total,
        })

    except Exception as e:
        log.error("Xendit invoice creation failed: %s", e)
        return jsonify({"error": f"Payment creation failed: {str(e)}"}), 500


@checkout_bp.route("/payment-return")
def payment_return():
    result = request.args.get("result", "success")
    invoice_id = request.args.get("invoice_id", "")
    message = (
        "Returning to Mendo. This window can close automatically."
        if result == "success"
        else "Payment was not completed. You can return to Mendo and try again."
    )
    return render_template_string(
        _PAYMENT_RETURN_HTML,
        result=result,
        invoice_id=invoice_id,
        message=message,
    )


# ─────────── Payment verification & order completion ───────────

@checkout_bp.route("/api/pay/verify", methods=["POST"])
def api_verify_payment():
    """Verify Xendit payment and complete the order.
    Called by the frontend after user returns from Xendit payment page.
    """
    data = request.get_json(force=True)
    invoice_id = str(data.get("invoice_id", ""))

    if not invoice_id:
        return jsonify({"error": "Missing invoice_id"}), 400

    secret_key = os.environ.get("XENDIT_SECRET_KEY", "")
    if not secret_key:
        return jsonify({"error": "Payment not configured"}), 500

    pending = session.get("pending_order")
    if not pending:
        return jsonify({"error": "No pending order found"}), 400

    try:
        import xendit
        from xendit.apis import InvoiceApi

        xendit.set_api_key(secret_key)
        api = InvoiceApi()
        invoice = api.get_invoice_by_id(invoice_id)

        status = str(getattr(invoice, 'status', '')).upper()
        external_id = str(getattr(invoice, 'external_id', '') or '')
        if pending.get("external_id") and external_id and pending["external_id"] != external_id:
            return jsonify({"error": "Invoice does not match pending order"}), 400

        if status not in ('PAID', 'SETTLED'):
            return jsonify({
                "success": False,
                "status": status,
                "message": "Payment not yet completed",
            })

        # Payment confirmed — create transaction and deduct inventory
        cart = pending["cart"]
        result = create_transaction(
            items=cart,
            payment_method="xendit_cashless",
            amount_tendered=pending["total"],
            cashier_id=0,  # kiosk self-service
            customer_note=f"Xendit Invoice: {invoice_id}",
        )

        # Clear session data
        _set_kiosk_cart([])
        session.pop("pending_order", None)
        session.pop("kiosk_authenticated", None)

        return jsonify({
            "success": True,
            "status": "PAID",
            "transaction_ref": result["transaction_ref"],
            "total_amount": result["total_amount"],
            "items": result["items"],
        })

    except Exception as e:
        log.error("Payment verification failed: %s", e)
        return jsonify({"error": f"Verification failed: {str(e)}"}), 500


# ─────────── Xendit Webhook ───────────

@checkout_bp.route("/api/webhook/xendit", methods=["POST"])
def xendit_webhook():
    """Handle Xendit payment webhook notifications.
    This is called by Xendit servers when payment status changes.
    """
    webhook_token = os.environ.get("XENDIT_WEBHOOK_TOKEN", "")
    if webhook_token:
        callback_token = request.headers.get("x-callback-token", "")
        if callback_token != webhook_token:
            return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json(force=True)
    external_id = data.get("external_id", "")
    status = data.get("status", "")

    log.info("Xendit webhook: external_id=%s status=%s", external_id, status)

    # Webhook processing is handled via verify endpoint for demo
    # In production, this would handle async payment completion
    return jsonify({"success": True})
