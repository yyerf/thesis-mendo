"""Kiosk checkout APIs backed by the recoverable OrderService.

Cash and Xendit share the same order, reservation, inventory, and receipt
sequence. The current rollout is payment-only: a paid order commits stock but
never sends a medicine-motor command. Real cash still crosses the local
hardware daemon boundary; simulator input remains explicitly labelled.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any, Dict, Optional

from flask import Blueprint, jsonify, request, session, render_template_string, url_for

from hardware.interface import HardwareFault
from hardware.service import get_hardware_service
from mendo_core.money import to_centavos

from .db import get_db, get_inventory_by_brand, get_inventory_item
from .order_service import (
    BILL_DENOMINATIONS_CENTAVOS,
    COIN_DENOMINATIONS_CENTAVOS,
    ConsentRequired,
    IdempotencyConflict,
    InvalidTransition,
    OrderError,
    OrderNotFound,
    OrderService,
    StockUnavailable,
)


log = logging.getLogger("mendo.checkout")
checkout_bp = Blueprint("checkout", __name__, url_prefix="/checkout")

MAX_QTY_PER_ITEM = 3
MAX_DISTINCT_ITEMS = 5

_PAYMENT_RETURN_HTML = """
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mendo Payment Return</title>
<style>
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0d1718;color:#eff8f0;font-family:Georgia,serif}
.card{width:min(92vw,430px);padding:34px 28px;border:1px solid #466a54;border-radius:24px;background:#132321;box-shadow:0 24px 80px #07100dcc;text-align:center}
h1{margin:0 0 12px;font-size:30px}.ok{color:#b7ee8d}.fail{color:#ffad83}p{color:#bfd1c2;line-height:1.65}
</style></head>
<body><div class="card"><h1 class="{{ 'ok' if result == 'success' else 'fail' }}">{{ 'Payment completed' if result == 'success' else 'Payment incomplete' }}</h1><p>{{ message }}</p></div>
<script>try{if(window.opener&&!window.opener.closed){window.opener.postMessage({source:'mendo-xendit',result:{{result|tojson}},invoiceId:{{invoice_id|tojson}},orderRef:{{order_ref|tojson}}},window.location.origin)}}catch(e){};setTimeout(()=>window.close(),800)</script>
</body></html>
"""


def _service() -> OrderService:
    return OrderService()


def _truthy(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "on"}


def _hardware_status() -> Dict[str, Any]:
    status = dict(get_hardware_service().status())
    for key in ("healthy", "connected", "simulator", "acceptors_inhibited", "coin_power_enabled", "pca_outputs_enabled", "physical_evidence_required"):
        if key in status and isinstance(status[key], str):
            status[key] = _truthy(status[key])
    status["mode_label"] = "SIMULATOR — no physical cash" if status.get("simulator") else "REAL CONTROLLER"
    return status


def _order_response(order: Dict[str, Any], *, status_code: int = 200):
    status = _hardware_status()
    payload = dict(order)
    payload["hardware"] = status
    payload["simulator_notice"] = (
        "Simulator mode: cash and dispensing events are synthetic and must not be presented as hardware acceptance evidence."
        if status.get("simulator") else None
    )
    return jsonify(payload), status_code


def _get_kiosk_cart() -> list:
    return session.get("kiosk_cart", [])


def _set_kiosk_cart(cart: list) -> None:
    session["kiosk_cart"] = cart


def _cart_order_items(cart: list) -> list:
    return [{"inventory_id": int(item["inventory_id"]), "quantity": int(item["quantity"])} for item in cart]


def _create_order_from_cart(*, payment_method: str = "cash", idempotency_key: Optional[str] = None, source: str = "kiosk") -> Dict[str, Any]:
    cart = _get_kiosk_cart()
    if not cart:
        raise OrderError("Cart is empty")
    body = request.get_json(silent=True) or {}
    key = idempotency_key or request.headers.get("Idempotency-Key") or body.get("idempotency_key")
    if not key and payment_method == "xendit_cashless":
        key = session.get("kiosk_xendit_idempotency") or f"kiosk-xendit-{uuid.uuid4().hex}"
        session["kiosk_xendit_idempotency"] = key
    if not key:
        raise OrderError("Idempotency-Key is required")
    order = _service().create_order(_cart_order_items(cart), idempotency_key=key, source=source, payment_method=payment_method)
    session["kiosk_order_ref"] = order["order_ref"]
    return order


def _dispatch_order(order_ref: str) -> Dict[str, Any]:
    """Run one sequential job at the hardware boundary.

    Simulator jobs complete synchronously. Real jobs are checked by immutable
    job id and then reconciled with ``JOB_STATUS``; a transport failure never
    triggers a second physical command.
    """
    service = _service()
    hardware = get_hardware_service()
    if not hardware.bridge.simulator and not hardware.ready_for_cash():
        return service.get_order(order_ref)
    service.enqueue_dispense_jobs(order_ref)

    # A worker may have died after claiming a job. Reconcile the controller's
    # durable job record before considering any new motion. A missing or
    # unreachable result is deliberately manual review; only an explicit
    # controller-negative result is safe to release for staff retry.
    while True:
        started = service.started_dispense_job(order_ref)
        if not started:
            break
        try:
            stored = hardware.bridge.job_status(started["job_id"])
        except Exception as exc:
            stored = None
            detail = f"Unable to query stored controller result: {exc}"
        else:
            detail = "Controller did not report a completed stored job result"
        if _controller_job_completed(stored):
            service.record_dispense_event(
                started["job_id"], "DISPENSE_DONE_UNVERIFIED",
                ack_result="reconciled", controller_result="executed",
            )
            continue
        controller_result = "unexecuted" if _controller_job_unexecuted(stored) else "unknown"
        service.fail_dispense_job(
            started["job_id"], error_code="JOB_RESULT_UNKNOWN",
            error_detail=detail, controller_result=controller_result,
        )
        return service.get_order(order_ref)

    while True:
        job = service.next_dispense_job(order_ref)
        if not job:
            break
        service.claim_dispense_job(job["job_id"])
        try:
            result = hardware.dispense(job["job_id"], job["slot"], job["profile_version"])
            if result.get("event") == "DISPENSE_FAILED":
                service.record_dispense_event(
                    job["job_id"], "DISPENSE_FAILED", error_code=result.get("error_code"),
                    error_detail="Simulator fault injection", controller_result=result.get("controller_result", "unknown")
                )
                break
            if hardware.bridge.simulator:
                service.record_dispense_event(
                    job["job_id"], "DISPENSE_DONE_UNVERIFIED",
                    ack_result="ack_lost" if result.get("ack_lost") else "ack",
                    controller_result=result.get("controller_result", "executed"),
                )
            else:
                stored = hardware.bridge.job_status(job["job_id"])
                if _controller_job_completed(stored):
                    service.record_dispense_event(
                        job["job_id"], "DISPENSE_DONE_UNVERIFIED",
                        ack_result="ack", controller_result="executed",
                    )
                else:
                    service.record_dispense_event(
                        job["job_id"], "DISPENSE_FAILED", error_code="JOB_RESULT_UNKNOWN",
                        error_detail="Controller did not return a completed stored job result",
                        controller_result="unknown",
                    )
                    break
        except Exception as exc:
            # A lost response is not evidence of a failed movement. Query the
            # controller once using the immutable job id before recording an
            # unknown result, so a completed motion is never repeated.
            try:
                stored = hardware.bridge.job_status(job["job_id"])
            except Exception as query_exc:
                stored = None
                detail = f"{exc}; job query failed: {query_exc}"
            else:
                detail = str(exc)
            if _controller_job_completed(stored):
                service.record_dispense_event(
                    job["job_id"], "DISPENSE_DONE_UNVERIFIED",
                    ack_result="reconciled", controller_result="executed",
                )
            else:
                service.record_dispense_event(
                    job["job_id"], "DISPENSE_FAILED", error_code="HARDWARE_REQUEST_FAILED",
                    error_detail=detail,
                    controller_result="unexecuted" if _controller_job_unexecuted(stored) else "unknown",
                )
            break
    return service.get_order(order_ref)


def _controller_job_completed(result: Optional[Dict[str, Any]]) -> bool:
    if not result:
        return False
    return (
        str(result.get("state", "")) in {"2", "done", "done_unverified"}
        or str(result.get("result", "")).lower() == "done_unverified"
        or str(result.get("event", "")).upper() == "DISPENSE_DONE_UNVERIFIED"
    )


def _controller_job_unexecuted(result: Optional[Dict[str, Any]]) -> bool:
    if not result:
        return False
    return str(result.get("known", "")).lower() in {"0", "false", "no"} or str(result.get("controller_result", "")).lower() == "unexecuted"


def _dispatch_simulator(order_ref: str) -> Dict[str, Any]:
    """Compatibility name used by the cashier route and simulator tests."""
    return _dispatch_order(order_ref)


def _finish_paid_order(order_ref: str) -> Dict[str, Any]:
    # Payment-hardware test phase: commit the sale and inventory exactly once,
    # but deliberately do not enqueue or dispatch medicine-motor jobs.
    return _service().finalize_payment_only_sale(order_ref)


def _ingest_hardware_events() -> None:
    """Commit daemon events before acknowledging them to the controller."""
    hardware = get_hardware_service()
    service = _service()
    for _ in range(16):
        try:
            event = hardware.poll_event()
        except Exception:
            # A disconnected daemon is reflected by the hardware status; it
            # must not make a durable order unreadable.
            log.warning("Hardware event poll failed", exc_info=True)
            return
        if not event:
            return
        session_ref = str(event.get("session_ref", ""))
        if not session_ref:
            log.error("Hardware event has no payment session; leaving it for staff review")
            return
        row = get_db().execute(
            "SELECT o.order_ref FROM orders o JOIN cash_payment_sessions s ON s.order_id=o.id WHERE s.session_ref=?",
            (session_ref,),
        ).fetchone()
        if not row:
            log.error("Hardware event references unknown payment session %s", session_ref)
            return
        boot_id = str(event.get("boot_id", ""))
        sequence_no = int(event.get("sequence_no", 0))
        source = str(event.get("source", ""))
        event_id = str(event.get("event_id") or f"{boot_id}-{source}-{sequence_no}")
        result = service.record_cash_event(
            row["order_ref"], session_ref=session_ref, event_id=event_id,
            source=source, raw_pulses=int(event.get("raw_pulses", 0)),
            mapped_centavos=int(event.get("mapped_centavos", 0)), boot_id=boot_id,
            sequence_no=sequence_no, pulse_started_at=event.get("pulse_started_at"),
            quality=str(event.get("quality", "ok")),
        )
        # The ACK is sent only after the database transition has committed.
        hardware.ack_cash_event(boot_id, sequence_no, source)
        if result.get("stop_acceptors"):
            hardware.stop_cash(session_ref)
        if result.get("payment_complete"):
            _finish_paid_order(row["order_ref"])


def _expire_stale_cash_sessions(service: OrderService, hardware) -> list[str]:
    """Close timed-out database sessions and inhibit their hardware session."""
    expired = service.expire_cash_sessions()
    for expired_ref in expired:
        cash_session = service.get_order(expired_ref).get("cash_session") or {}
        session_ref = str(cash_session.get("session_ref") or "")
        if not session_ref:
            continue
        try:
            hardware.stop_cash(session_ref)
        except Exception:
            # The database timeout remains authoritative. A failed stop keeps
            # the next PAY_START fail-safe rather than pretending two orders
            # can collect at once.
            log.warning("Hardware stop failed for expired cash session %s", session_ref, exc_info=True)
    return expired


def _error(exc: Exception):
    if isinstance(exc, OrderNotFound):
        return jsonify({"error": str(exc), "code": exc.__class__.__name__}), 404
    if isinstance(exc, HardwareFault):
        return jsonify({"error": str(exc), "code": "HardwareFault"}), 503
    if isinstance(exc, (StockUnavailable, ConsentRequired, InvalidTransition, IdempotencyConflict, OrderError)):
        return jsonify({"error": str(exc), "code": exc.__class__.__name__}), 409
    log.exception("Checkout failure")
    return jsonify({"error": str(exc)}), 500


# ── Legacy cart endpoints retained as a non-authoritative pre-order cart ───

@checkout_bp.route("/api/cart", methods=["GET"])
def api_kiosk_cart():
    enriched = []
    total_centavos = 0
    for ci in _get_kiosk_cart():
        item = get_inventory_item(ci["inventory_id"])
        if item and item["is_active"] and item.get("hardware_slot") is not None:
            cents = int(item.get("unit_price_centavos") or to_centavos(item["unit_price"]))
            quantity = int(ci["quantity"])
            subtotal = cents * quantity
            total_centavos += subtotal
            enriched.append({
                "inventory_id": item["id"], "hardware_slot": item.get("hardware_slot"),
                "brand": item["brand"], "generic_name": item.get("generic_name", ""),
                "unit_price": cents / 100, "unit_price_centavos": cents,
                "quantity": quantity, "stock_available": max(0, int(item["stock_quantity"]) - int(item.get("reserved_quantity", 0))),
                "subtotal": subtotal / 100, "subtotal_centavos": subtotal,
            })
    return jsonify({"items": enriched, "total": total_centavos / 100, "total_centavos": total_centavos, "item_count": sum(item["quantity"] for item in enriched)})


@checkout_bp.route("/api/cart/add", methods=["POST"])
def api_kiosk_cart_add():
    data = request.get_json(force=True)
    brand = str(data.get("brand", "")).strip()
    try:
        qty = int(data.get("quantity", 1))
    except (TypeError, ValueError):
        return jsonify({"error": "Quantity must be an integer"}), 400
    if qty <= 0:
        return jsonify({"error": "Quantity must be positive"}), 400
    item = get_inventory_by_brand(brand)
    if not item or not item["is_active"] or item.get("hardware_slot") is None:
        return jsonify({"error": "Product is not available"}), 404
    if int(item["stock_quantity"]) - int(item.get("reserved_quantity", 0)) <= 0:
        return jsonify({"error": "Out of stock"}), 400
    cart = _get_kiosk_cart()
    existing_ids = {int(c["inventory_id"]) for c in cart}
    if item["id"] not in existing_ids and len(existing_ids) >= MAX_DISTINCT_ITEMS:
        return jsonify({"error": f"Maximum {MAX_DISTINCT_ITEMS} different items allowed per purchase"}), 400
    for ci in cart:
        if int(ci["inventory_id"]) == item["id"]:
            new_qty = int(ci["quantity"]) + qty
            if new_qty > MAX_QTY_PER_ITEM:
                return jsonify({"error": f"Maximum {MAX_QTY_PER_ITEM} units per medicine"}), 400
            if new_qty > int(item["stock_quantity"]) - int(item.get("reserved_quantity", 0)):
                return jsonify({"error": "Not enough available stock"}), 400
            ci["quantity"] = new_qty
            _set_kiosk_cart(cart)
            return jsonify({"success": True, "message": f"{item['brand']} updated in cart"})
    if qty > MAX_QTY_PER_ITEM:
        return jsonify({"error": f"Maximum {MAX_QTY_PER_ITEM} units per medicine"}), 400
    cart.append({"inventory_id": item["id"], "quantity": qty})
    _set_kiosk_cart(cart)
    return jsonify({"success": True, "message": f"{item['brand']} added to cart"})


@checkout_bp.route("/api/cart/remove", methods=["POST"])
def api_kiosk_cart_remove():
    data = request.get_json(force=True)
    inv_id = int(data.get("inventory_id", 0))
    _set_kiosk_cart([c for c in _get_kiosk_cart() if int(c["inventory_id"]) != inv_id])
    return jsonify({"success": True})


@checkout_bp.route("/api/cart/clear", methods=["POST"])
def api_kiosk_cart_clear():
    _set_kiosk_cart([])
    session.pop("kiosk_order_ref", None)
    return jsonify({"success": True})


# ── Unified order APIs ────────────────────────────────────────────────────

@checkout_bp.route("/api/orders", methods=["POST"])
def api_create_order():
    try:
        data = request.get_json(silent=True) or {}
        items = data.get("items") or _cart_order_items(_get_kiosk_cart())
        key = request.headers.get("Idempotency-Key") or data.get("idempotency_key")
        order = _service().create_order(items, idempotency_key=key or "", source=str(data.get("source", "kiosk")), payment_method=str(data.get("payment_method", "cash")))
        session["kiosk_order_ref"] = order["order_ref"]
        return _order_response(order, status_code=201)
    except Exception as exc:
        return _error(exc)


@checkout_bp.route("/api/orders/<order_ref>", methods=["GET"])
def api_get_order(order_ref: str):
    try:
        _ingest_hardware_events()
        service = _service()
        _expire_stale_cash_sessions(service, get_hardware_service())
        order = service.get_order(order_ref)
        # Polling is also a safe recovery trigger after a Flask restart. Stock
        # finalization is transactional and idempotent; no motor is contacted.
        if (
            order["payment_state"] == "paid"
            and order["fulfillment_state"] == "reserved"
            and not order.get("stock_committed_at")
        ):
            order = _finish_paid_order(order_ref)
        return _order_response(order)
    except Exception as exc:
        return _error(exc)


@checkout_bp.route("/api/orders/<order_ref>/cash/start", methods=["POST"])
def api_start_cash(order_ref: str):
    try:
        data = request.get_json(silent=True) or {}
        if not _truthy(data.get("no_change_consent", data.get("accept_no_change", False))):
            raise ConsentRequired("Confirm that this machine does not give change before inserting cash")
        hardware = get_hardware_service()
        status = _hardware_status()
        if not hardware.ready_for_cash():
            return jsonify({"error": "Cash hardware is unhealthy or disconnected", "hardware": status}), 503
        service = _service()
        # Reconcile queued money first, then release a genuinely abandoned
        # zero-cash session before enforcing the one-acceptor invariant.
        _ingest_hardware_events()
        _expire_stale_cash_sessions(service, hardware)
        result = service.start_cash(order_ref, no_change_consent=True)
        try:
            hardware.start_cash(result["session_ref"], service.get_order(order_ref)["total_centavos"])
        except Exception:
            try:
                hardware.stop_cash(result["session_ref"])
            except Exception:
                pass
            try:
                service.reset_cash_start(order_ref)
            except Exception:
                log.exception("Could not roll back failed cash-session handshake")
            raise
        return _order_response(service.get_order(order_ref))
    except Exception as exc:
        return _error(exc)


@checkout_bp.route("/api/orders/<order_ref>/cash/cancel", methods=["POST"])
def api_cancel_cash(order_ref: str):
    try:
        service = _service()
        before = service.get_order(order_ref)
        result = service.cancel_order(order_ref)
        if before.get("cash_session"):
            try:
                get_hardware_service().stop_cash(before["cash_session"]["session_ref"])
            except Exception:
                log.warning("Hardware stop failed during cancellation", exc_info=True)
        return _order_response(result)
    except Exception as exc:
        return _error(exc)


@checkout_bp.route("/api/orders/<order_ref>/cash/simulate", methods=["POST"])
def api_simulate_cash(order_ref: str):
    """Development-only cash insertion endpoint; never available in real mode."""
    try:
        hardware = get_hardware_service()
        if not hardware.bridge.simulator:
            return jsonify({"error": "Simulator cash injection is disabled in real mode"}), 403
        data = request.get_json(force=True)
        source = str(data.get("source", "coin"))
        if "raw_pulses" in data:
            event = hardware.bridge.backend.inject_raw_pulses(source, int(data["raw_pulses"]))
        else:
            amount = data.get("centavos")
            if amount is None:
                amount = to_centavos(data.get("amount", 0))
            event = hardware.inject_cash(source, int(amount))
        result = _service().record_cash_event(order_ref, session_ref=event["session_ref"], event_id=event["event_id"], source=event["source"], raw_pulses=event["raw_pulses"], mapped_centavos=event["mapped_centavos"], boot_id=event["boot_id"], sequence_no=event["sequence_no"], pulse_started_at=event.get("pulse_started_at"))
        if result.get("payment_complete"):
            order = _finish_paid_order(order_ref)
        else:
            order = result["order"]
        return _order_response(order)
    except Exception as exc:
        return _error(exc)


@checkout_bp.route("/api/hardware/status", methods=["GET"])
def api_hardware_status():
    return jsonify(_hardware_status())


@checkout_bp.route("/payment-return")
def payment_return():
    result = request.args.get("result", "success")
    return render_template_string(_PAYMENT_RETURN_HTML, result=result, invoice_id=request.args.get("invoice_id", ""), order_ref=request.args.get("order_ref", ""), message="Return to the Mendo checkout screen; the order status is stored on the machine.")


# ── Xendit persistence and verification ──────────────────────────────────

def _xendit_order(data: Dict[str, Any]) -> Dict[str, Any]:
    order_ref = str(data.get("order_ref") or session.get("kiosk_order_ref") or "").strip()
    service = _service()
    if order_ref:
        order = service.get_order(order_ref)
    else:
        order = _create_order_from_cart(payment_method="xendit_cashless", idempotency_key=request.headers.get("Idempotency-Key") or data.get("idempotency_key"), source="kiosk")
    if order["payment_method"] != "xendit_cashless":
        raise OrderError("Order is not configured for Xendit")
    external_id = f"MENDO-{order['order_ref']}"
    attempt = service.ensure_xendit_attempt(order["order_ref"], external_id=external_id, amount_centavos=order["total_centavos"], payload={"order_ref": order["order_ref"]})
    return {"order": order, "external_id": external_id, "attempt": attempt}


@checkout_bp.route("/api/pay/xendit", methods=["POST"])
def api_pay_xendit():
    try:
        data = request.get_json(silent=True) or {}
        prepared = _xendit_order(data)
        order, external_id, attempt = prepared["order"], prepared["external_id"], prepared["attempt"]
        payload = json.loads(attempt.get("payload_json") or "{}")
        if attempt.get("provider_payment_id") and payload.get("invoice_url"):
            return jsonify({"success": True, "order_ref": order["order_ref"], "invoice_id": attempt["provider_payment_id"], "invoice_url": payload["invoice_url"], "external_id": external_id, "amount": order["total_centavos"] / 100, "amount_centavos": order["total_centavos"]})
        secret_key = os.environ.get("XENDIT_SECRET_KEY", "")
        if not secret_key:
            return jsonify({"error": "Xendit is not configured", "order_ref": order["order_ref"]}), 503
        try:
            import xendit
            from xendit.apis import InvoiceApi
            from xendit.invoice.model.create_invoice_request import CreateInvoiceRequest
            xendit.set_api_key(secret_key)
            invoice = InvoiceApi().create_invoice(CreateInvoiceRequest(
                external_id=external_id, amount=order["total_centavos"] / 100,
                description=f"Mendo Medicine Purchase ({len(order['items'])} line(s))", currency="PHP",
                invoice_duration=600.0,
                success_redirect_url=url_for("checkout.payment_return", result="success", order_ref=order["order_ref"], _external=True),
                failure_redirect_url=url_for("checkout.payment_return", result="failure", order_ref=order["order_ref"], _external=True),
            ))
            invoice_id = str(getattr(invoice, "id", ""))
            invoice_url = str(getattr(invoice, "invoice_url", ""))
            service.attach_xendit_invoice(external_id, invoice_id)
            service.save_xendit_payload(external_id, {"order_ref": order["order_ref"], "invoice_url": invoice_url})
            return jsonify({"success": True, "order_ref": order["order_ref"], "invoice_id": invoice_id, "invoice_url": invoice_url, "external_id": external_id, "amount": order["total_centavos"] / 100, "amount_centavos": order["total_centavos"]})
        except Exception as exc:
            log.error("Xendit invoice creation failed: %s", exc)
            return jsonify({"error": f"Payment creation failed: {exc}", "order_ref": order["order_ref"]}), 502
    except Exception as exc:
        return _error(exc)


@checkout_bp.route("/api/pay/verify", methods=["POST"])
def api_verify_payment():
    try:
        data = request.get_json(force=True)
        invoice_id = str(data.get("invoice_id", ""))
        order_ref = str(data.get("order_ref") or session.get("kiosk_order_ref") or "")
        if not invoice_id or not order_ref:
            return jsonify({"error": "order_ref and invoice_id are required"}), 400
        secret_key = os.environ.get("XENDIT_SECRET_KEY", "")
        if not secret_key:
            return jsonify({"error": "Xendit is not configured"}), 503
        import xendit
        from xendit.apis import InvoiceApi
        xendit.set_api_key(secret_key)
        invoice = InvoiceApi().get_invoice_by_id(invoice_id)
        status = str(getattr(invoice, "status", "")).upper()
        external_id = str(getattr(invoice, "external_id", "") or "")
        amount = getattr(invoice, "paid_amount", None) or getattr(invoice, "amount", None)
        currency = str(getattr(invoice, "currency", "PHP") or "PHP")
        if status not in {"PAID", "SETTLED"}:
            return jsonify({"success": False, "status": status, "order_ref": order_ref, "message": "Payment not yet completed"})
        order = _service().get_order(order_ref)
        if external_id != f"MENDO-{order_ref}":
            raise OrderError("Invoice external id does not match order")
        paid = _service().complete_xendit_payment(order_ref, external_id=external_id, provider_payment_id=invoice_id, amount_centavos=to_centavos(amount), currency=currency, payload={"status": status, "invoice_id": invoice_id})
        paid = _finish_paid_order(order_ref)
        return _order_response(paid)
    except Exception as exc:
        return _error(exc)


@checkout_bp.route("/api/webhook/xendit", methods=["POST"])
def xendit_webhook():
    configured = os.environ.get("XENDIT_WEBHOOK_TOKEN", "")
    if configured and request.headers.get("x-callback-token", "") != configured:
        return jsonify({"error": "Unauthorized"}), 403
    if not configured and os.environ.get("MENDO_ENV", "development").lower() == "production":
        return jsonify({"error": "Webhook token is not configured"}), 503
    try:
        data = request.get_json(force=True)
        external_id = str(data.get("external_id", ""))
        status = str(data.get("status", "")).upper()
        if not external_id or not status:
            return jsonify({"error": "external_id and status are required"}), 400
        if status not in {"PAID", "SETTLED"}:
            return jsonify({"success": True, "status": status})
        if not external_id.startswith("MENDO-"):
            return jsonify({"error": "Invalid external id"}), 400
        order_ref = external_id[6:]
        amount = data.get("paid_amount", data.get("amount"))
        currency = data.get("currency", "PHP")
        if amount is None:
            return jsonify({"error": "Paid amount is required"}), 400
        order = _service().get_order(order_ref)
        paid = _service().complete_xendit_payment(order_ref, external_id=external_id, provider_payment_id=str(data.get("id") or data.get("invoice_id") or ""), amount_centavos=to_centavos(amount), currency=currency, payload=data)
        paid = _finish_paid_order(order_ref)
        return jsonify({"success": True, "order_ref": order_ref, "payment_state": paid["payment_state"], "fulfillment_state": paid["fulfillment_state"]})
    except Exception as exc:
        return _error(exc)
