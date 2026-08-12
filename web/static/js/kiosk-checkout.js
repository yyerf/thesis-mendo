/* Unified kiosk checkout: Cart -> Payment -> Dispensing -> Receipt.
 * This file deliberately has no biometric step. The server order reference is
 * the durable hand-off; browser state is only a view of that order.
 */
(function () {
  "use strict";

  var cart = [];
  var orderRef = null;
  var orderKey = null;
  var selectedPayment = "cash";
  var currentInvoiceId = null;
  var pollTimer = null;
  var paymentTimer = null;
  var step = 1;
  var noChange = false;
  var cashStartPending = false;

  function el(id) { return document.getElementById(id); }
  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (c) {
      return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c];
    });
  }
  function money(cents) {
    return "₱" + (Number(cents || 0) / 100).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }
  function notify(message) {
    var body = el("checkoutBody");
    if (body) {
      var existing = body.querySelector(".checkout-notice");
      if (existing) existing.remove();
      var note = document.createElement("div");
      note.className = "checkout-notice";
      note.style.cssText = "margin-top:12px;padding:10px 12px;border-radius:10px;background:#fff1ed;color:#9a3e2f;font-size:13px";
      note.textContent = message;
      body.appendChild(note);
    }
  }
  async function requestJson(url, options) {
    var response = await fetch(url, options || {});
    var data = await response.json();
    if (!response.ok) throw new Error(data.error || "Request failed");
    return data;
  }
  async function refresh() {
    var data = await requestJson("/checkout/api/cart");
    cart = data.items || [];
    var count = cart.reduce(function (sum, item) { return sum + Number(item.quantity || 0); }, 0);
    var fab = el("checkoutFab");
    var badge = el("fabBadge");
    var proceed = el("proceedCheckoutBtn");
    var countEl = el("checkoutBtnCount");
    if (fab) fab.style.display = count ? "inline-flex" : "none";
    if (badge) badge.textContent = count;
    if (proceed) proceed.style.display = count ? "inline-flex" : "none";
    if (countEl) countEl.textContent = count;
  }
  function stepDots() {
    return '<div class="checkout-steps"><div class="checkout-step-dot ' + (step >= 1 ? (step > 1 ? "done" : "active") : "") + '"></div><div class="checkout-step-line"></div><div class="checkout-step-dot ' + (step >= 2 ? (step > 2 ? "done" : "active") : "") + '"></div><div class="checkout-step-line"></div><div class="checkout-step-dot ' + (step >= 3 ? (step > 3 ? "done" : "active") : "") + '"></div><div class="checkout-step-line"></div><div class="checkout-step-dot ' + (step >= 4 ? "done active" : "") + '"></div></div>';
  }
  function modalParts() {
    return { body: el("checkoutBody"), footer: el("checkoutFooter"), title: el("checkoutTitle") };
  }
  function render() {
    var parts = modalParts();
    if (!parts.body || !parts.footer || !parts.title) return;
    var order = window._mendoOrder || {};
    var modal = document.querySelector("#checkoutOverlay .checkout-modal");
    var closeButton = document.querySelector("#checkoutOverlay .checkout-close");
    if (modal) modal.classList.toggle("checkout-modal--payment", step === 2 || step === 3);
    if (closeButton) closeButton.hidden = step === 3;
    if (step === 1) {
      parts.title.textContent = "Your cart";
      var rows = cart.map(function (item) {
        return '<div class="checkout-item"><div class="checkout-item-info"><div class="checkout-item-brand">' + esc(item.brand) + '</div><div class="checkout-item-generic">' + esc(item.generic_name) + '</div><div class="checkout-item-price">' + money(item.unit_price_centavos) + ' × ' + item.quantity + ' = ' + money(item.subtotal_centavos) + '</div></div><div class="checkout-item-qty"><button class="checkout-qty-btn" onclick="mendoKioskQty(' + item.inventory_id + ',' + (item.quantity - 1) + ')">−</button><span class="checkout-qty-val">' + item.quantity + '</span><button class="checkout-qty-btn" onclick="mendoKioskQty(' + item.inventory_id + ',' + (item.quantity + 1) + ')">+</button></div><button class="checkout-item-remove" onclick="mendoKioskRemove(' + item.inventory_id + ')">×</button></div>';
      }).join("");
      var total = cart.reduce(function (sum, item) { return sum + Number(item.subtotal_centavos || 0); }, 0);
      parts.body.innerHTML = stepDots() + (rows || '<p style="padding:30px;text-align:center;color:#8a958c">Your cart is empty. Choose a medicine to begin.</p>') + (cart.length ? '<div class="checkout-total"><span class="label">Total</span><span class="amount">' + money(total) + '</span></div><div class="checkout-limit-note">Maximum 3 units per medicine · 5 different medicines</div>' : "");
      parts.footer.innerHTML = cart.length ? '<button class="btn" onclick="closeCheckoutModal()">Continue shopping</button><button class="btn btn--primary" onclick="mendoKioskPayment()">Choose payment <i class="fa-solid fa-arrow-right"></i></button>' : '<button class="btn" onclick="closeCheckoutModal()">Close</button>';
      return;
    }
    if (step === 2) {
      parts.title.textContent = "Payment";
      var totalDue = cart.reduce(function (sum, item) { return sum + Number(item.subtotal_centavos || 0); }, 0);
      parts.body.innerHTML = stepDots() +
        '<div class="payment-section">' +
          '<div class="payment-summary">' +
            '<div><span class="payment-summary-label">Amount due</span><span class="payment-summary-note">Review the total before continuing</span></div>' +
            '<strong class="payment-summary-amount">' + money(totalDue) + '</strong>' +
          '</div>' +
          '<div class="payment-heading"><div class="payment-title">Choose a payment method</div><div class="payment-subtitle">Select how you would like to complete this purchase.</div></div>' +
          '<div class="payment-options">' +
            '<button type="button" class="payment-option ' + (selectedPayment === "cash" ? "selected" : "") + '" onclick="mendoSelectPayment(\'cash\')" aria-pressed="' + (selectedPayment === "cash" ? "true" : "false") + '">' +
              '<span class="po-icon cash"><i class="fa-solid fa-coins"></i></span>' +
              '<span class="po-info"><span class="po-label">Cash</span><span class="po-desc">Coins: ₱1, ₱5, ₱10 · Bills: ₱20, ₱50, ₱100</span></span>' +
              '<span class="po-check"><i class="fa-solid fa-check"></i></span>' +
            '</button>' +
            '<button type="button" class="payment-option ' + (selectedPayment === "cashless" ? "selected" : "") + '" onclick="mendoSelectPayment(\'cashless\')" aria-pressed="' + (selectedPayment === "cashless" ? "true" : "false") + '">' +
              '<span class="po-icon cashless"><i class="fa-solid fa-qrcode"></i></span>' +
              '<span class="po-info"><span class="po-label">Cashless</span><span class="po-desc">Pay securely through a Xendit invoice</span></span>' +
              '<span class="po-check"><i class="fa-solid fa-check"></i></span>' +
            '</button>' +
          '</div>' +
          (selectedPayment === "cash" ?
            '<label class="payment-policy" for="mendoNoChange">' +
              '<input id="mendoNoChange" type="checkbox" ' + (noChange ? "checked" : "") + ' onchange="mendoSetNoChange(this.checked)">' +
              '<span><span class="payment-policy-title">No change is dispensed</span><span class="payment-policy-copy">I understand that any overpayment is recorded separately and will not be returned by this machine.</span></span>' +
            '</label>' : "") +
        '</div>';
      parts.footer.innerHTML = '<button class="btn" onclick="mendoKioskStep(1)" ' + (cashStartPending ? "disabled" : "") + '>Back</button>' + (selectedPayment === "cash" ? '<button class="btn btn--primary" onclick="mendoStartCash()" ' + (cashStartPending ? "disabled" : "") + '>' + (cashStartPending ? '<i class="fa-solid fa-spinner fa-spin"></i> Starting payment…' : 'Continue with cash <i class="fa-solid fa-arrow-right"></i>') + '</button>' : '<button class="btn btn--primary" onclick="mendoStartXendit()">Continue to Xendit <i class="fa-solid fa-arrow-right"></i></button>');
      return;
    }
    if (step === 3) {
      parts.title.textContent = "Insert payment";
      var hardware = order.hardware || {};
      var due = Number(order.amount_due_centavos || 0);
      var received = Number(order.received_cash_centavos || 0);
      var remaining = Number(order.remaining_centavos || Math.max(0, due - received));
      var overpayment = Number(order.overpayment_centavos || Math.max(0, received - due));
      var progress = due > 0 ? Math.min(100, Math.max(0, (received / due) * 100)) : 0;
      var isReview = order.payment_state === "manual_review" || order.fulfillment_state === "manual_review";
      var isPaid = order.payment_state === "paid";
      var promptTitle = isReview ? "Please ask for assistance" : isPaid ? "Payment received" : received > 0 ? "Please insert the remaining amount" : "Please insert your money";
      var promptKicker = isReview ? "Payment paused" : isPaid ? "Payment complete" : received > 0 ? "Payment in progress" : "Cash acceptor ready";
      var promptIcon = isReview ? "triangle-exclamation" : isPaid ? "check" : "money-bill-wave";
      var controls = hardware.simulator ?
        '<div class="cash-simulator"><div class="cash-simulator-title">SIMULATOR INPUT</div><div class="cash-simulator-note">Development mode only — choose a denomination to simulate an insertion.</div><div class="cash-simulator-actions">' +
          [[100,"₱1","coin"],[500,"₱5","coin"],[1000,"₱10","coin"],[2000,"₱20","bill"],[5000,"₱50","bill"],[10000,"₱100","bill"]].map(function (v) { return '<button class="btn btn--sm" onclick="mendoSimulate(' + v[0] + ',\'' + v[2] + '\')">' + v[1] + '</button>'; }).join("") +
        '</div></div>' : "";
      parts.body.innerHTML = stepDots() +
        '<div class="cash-payment">' +
          '<section class="cash-prompt" aria-live="polite">' +
            '<div class="cash-prompt-icon"><i class="fa-solid fa-' + promptIcon + '"></i></div>' +
            '<div class="cash-prompt-kicker">' + esc(promptKicker) + '</div>' +
            '<h4>' + esc(promptTitle) + '</h4>' +
            '<p>Insert ₱1, ₱5, or ₱10 coins and ₱20, ₱50, or ₱100 bills. Your payment is counted automatically.</p>' +
            '<div class="cash-amount-due"><span>Total to pay</span><strong>' + (order.amount_due_display || "₱0.00") + '</strong></div>' +
          '</section>' +
          '<div class="cash-progress" role="progressbar" aria-label="Payment progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + Math.round(progress) + '"><div class="cash-progress-bar" style="width:' + progress.toFixed(2) + '%"></div></div>' +
          '<div class="cash-summary-grid">' +
            '<div class="cash-summary-card"><span>Money inserted</span><strong>' + (order.received_cash_display || "₱0.00") + '</strong></div>' +
            '<div class="cash-summary-card cash-summary-card--remaining"><span>Amount remaining</span><strong>' + (order.remaining_display || money(remaining)) + '</strong></div>' +
          '</div>' +
          (overpayment > 0 ? '<div class="cash-overpayment"><span>Overpayment recorded (no change)</span><strong>' + (order.overpayment_display || money(overpayment)) + '</strong></div>' : "") +
          '<div class="cash-advisory"><i class="fa-solid fa-circle-info"></i><span>This machine does not dispense change. Inserted money is detected and reflected on this screen automatically.</span></div>' +
          controls +
          (order.failure_reason ? '<div class="cash-failure"><strong>Assistance required:</strong> ' + esc(order.failure_reason) + '</div>' : "") +
        '</div>';
      var liveLabel = isReview ? "Payment paused — ask for assistance" : isPaid ? "Finalizing payment" : "Listening for payment";
      parts.footer.innerHTML = (order.payment_state === "awaiting_cash" && !received ? '<button class="btn" onclick="mendoCancelCash()">Cancel payment</button>' : "") + '<div class="cash-live-status ' + (isReview ? "cash-live-status--paused" : "") + '"><span class="cash-live-dot"></span><span>' + esc(liveLabel) + '</span></div>';
      return;
    }
    var finalReview = order.payment_state === "manual_review" || order.fulfillment_state === "manual_review";
    var finalCancelled = order.payment_state === "cancelled" || order.fulfillment_state === "cancelled";
    parts.title.textContent = finalReview ? "Staff review required" : finalCancelled ? "Payment canceled" : "Receipt";
    var receiptItems = (order.items || []).map(function (item) { return '<div class="success-item-row"><span class="brand">' + esc(item.brand) + ' × ' + item.quantity_ordered + '</span><span>' + money(item.subtotal_centavos) + '</span></div>'; }).join("");
    var finalIcon = finalReview ? "triangle-exclamation" : finalCancelled ? "xmark" : "check";
    var finalTitle = finalReview ? "Keep this reference for staff" : finalCancelled ? "Payment was canceled" : "Payment successful — stock updated";
    var finalMessage = finalReview ? "Do not insert money again. Please ask a staff member to review this payment." : finalCancelled ? "No money was collected and no stock was deducted." : "The sale and inventory deduction are recorded. No medicine motor was activated during this payment-only test.";
    var finalSummary = finalCancelled ? '<div class="success-items"><div class="success-total-row success-total-row--single"><span>Amount collected</span><span>₱0.00</span></div></div>' : '<div class="success-items">' + receiptItems + '<div class="success-total-row"><span>Total</span><span>' + (order.amount_due_display || "₱0.00") + '</span></div><div class="success-total-row"><span>Overpayment</span><span>' + (order.overpayment_display || "₱0.00") + '</span></div></div>';
    parts.body.innerHTML = stepDots() + '<div class="success-section"><div class="success-icon ' + (finalCancelled ? "cancelled" : "") + '"><i class="fa-solid fa-' + finalIcon + '"></i></div><div class="success-title">' + finalTitle + '</div><div class="success-ref">Order: ' + esc(order.order_ref || "") + (order.transaction_ref ? " · Receipt: " + esc(order.transaction_ref) : "") + '</div>' + finalSummary + '<p style="font-size:13px;color:#68796c">' + finalMessage + '</p></div>';
    parts.footer.innerHTML = '<button class="btn btn--primary btn--lg" style="width:100%" onclick="closeCheckoutAndReset()">Done</button>';
  }
  async function createOrder(method) {
    if (!orderKey) orderKey = "ui-" + Date.now() + "-" + Math.random().toString(36).slice(2);
    var data = await requestJson("/checkout/api/orders", {method:"POST",headers:{"Content-Type":"application/json","Idempotency-Key":orderKey},body:JSON.stringify({payment_method:method,items:cart.map(function (item) { return {inventory_id:item.inventory_id,quantity:item.quantity}; })})});
    orderRef = data.order_ref; window._mendoOrder = data; return data;
  }
  async function poll(showError) {
    if (!orderRef) return;
    try { window._mendoOrder = await requestJson("/checkout/api/orders/" + encodeURIComponent(orderRef)); if (["completed", "manual_review", "cancelled"].indexOf(window._mendoOrder.fulfillment_state) !== -1) { clearInterval(pollTimer); pollTimer = null; step = 4; } render(); }
    catch (error) { if (showError) notify(error.message); }
  }
  function startPolling() { clearInterval(pollTimer); pollTimer = setInterval(function () { poll(false); }, 1000); poll(false); }
  window.mendoKioskStep = function (next) { step = next; render(); };
  window.mendoKioskPayment = function () { step = 2; render(); };
  window.mendoSelectPayment = function (method) { selectedPayment = method; render(); };
  window.mendoSetNoChange = function (checked) { noChange = Boolean(checked); };
  window.mendoStartCash = async function () {
    if (cashStartPending) return;
    var consent = el("mendoNoChange");
    noChange = Boolean(noChange || (consent && consent.checked));
    if (!noChange) { notify("Confirm the no-change policy before starting cash."); return; }
    cashStartPending = true;
    render();
    try {
      var order = await createOrder("cash");
      window._mendoOrder = await requestJson("/checkout/api/orders/" + encodeURIComponent(order.order_ref) + "/cash/start", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({no_change_consent:true})});
      cashStartPending = false;
      step = 3;
      render();
      startPolling();
    } catch (error) {
      cashStartPending = false;
      render();
      notify(error.message);
    }
  };
  window.mendoSimulate = async function (centavos, source) {
    try { window._mendoOrder = await requestJson("/checkout/api/orders/" + encodeURIComponent(orderRef) + "/cash/simulate", {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({centavos:centavos,source:source})}); if (window._mendoOrder.fulfillment_state === "completed" || window._mendoOrder.fulfillment_state === "manual_review") { clearInterval(pollTimer); pollTimer=null; step=4; } render(); } catch (error) { notify(error.message); }
  };
  window.mendoCancelCash = async function () { try { window._mendoOrder=await requestJson("/checkout/api/orders/"+encodeURIComponent(orderRef)+"/cash/cancel",{method:"POST",headers:{"Content-Type":"application/json"}});clearInterval(pollTimer);pollTimer=null;step=4;render(); } catch(error){notify(error.message);} };
  window.mendoStartXendit = async function () {
    try { var order=await createOrder("xendit_cashless"); var data=await requestJson("/checkout/api/pay/xendit",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({order_ref:order.order_ref})}); currentInvoiceId=data.invoice_id; orderRef=data.order_ref||order.order_ref; var popup=window.open(data.invoice_url,"_blank","width=480,height=700,scrollbars=yes"); if(!popup){notify("Allow popups to continue to Xendit.");return;} clearInterval(paymentTimer); paymentTimer=setInterval(function(){mendoVerifyXendit(false,popup);},3000); } catch(error){notify(error.message);}
  };
  window.mendoVerifyXendit = async function (showError, popup) {
    if (!currentInvoiceId || !orderRef) return;
    try { var data=await requestJson("/checkout/api/pay/verify",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({invoice_id:currentInvoiceId,order_ref:orderRef})}); if(data.payment_state==="paid"||data.fulfillment_state==="completed"){clearInterval(paymentTimer);paymentTimer=null;window._mendoOrder=data;if(popup&&!popup.closed)popup.close();step=3;render();startPolling();} } catch(error){if(showError)notify(error.message);}
  };
  window.mendoKioskQty = async function (id, quantity) { if(quantity<=0)return mendoKioskRemove(id); var item=cart.filter(function(i){return i.inventory_id===id;})[0]; if(!item)return; try{await requestJson("/checkout/api/cart/remove",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({inventory_id:id})});await requestJson("/checkout/api/cart/add",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({brand:item.brand,quantity:quantity})});await refresh();render();}catch(error){notify(error.message);} };
  window.mendoKioskRemove = async function (id) { try{await requestJson("/checkout/api/cart/remove",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({inventory_id:id})});await refresh();render();}catch(error){notify(error.message);} };
  window.openCheckoutModal = async function () { await refresh(); orderRef=null; orderKey=null; window._mendoOrder={}; step=1; selectedPayment="cash";noChange=false;el("checkoutOverlay").classList.add("active");render(); };
  window.closeCheckoutModal = function (event) {
    if (event && event.target !== el("checkoutOverlay")) return;
    if (step === 3) return;
    clearInterval(pollTimer);
    clearInterval(paymentTimer);
    pollTimer = null;
    paymentTimer = null;
    el("checkoutOverlay").classList.remove("active");
  };
  window.closeCheckoutAndReset = function () { closeCheckoutModal(); fetch("/checkout/api/cart/clear",{method:"POST"}).catch(function(){}); cart=[]; if(window.resetAll)window.resetAll(); };
  document.addEventListener("DOMContentLoaded", function () { refresh().catch(function(){}); });
})();
