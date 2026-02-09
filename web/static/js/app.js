/* ============================================================
   Mendo Kiosk – Single-Page Touch Flow Controller
   ============================================================
   Screens: welcome → disclaimer → input → age → loading → results
   All via AJAX (no page reload). Auto-resets after idle timeout.
   ============================================================ */
(() => {
  'use strict';

  // ── endpoints (injected via <meta> tags) ──
  const RECOMMEND_URL = document.querySelector('meta[name="mendo-endpoint"]')?.content || '/api/recommend';
  const STT_URL       = document.querySelector('meta[name="mendo-stt-endpoint"]')?.content || '/api/stt';

  // ── idle auto-reset (seconds) ──
  const IDLE_LIMIT = 120;

  // ── DOM refs ──
  const $ = (sel, ctx) => (ctx || document).querySelector(sel);
  const $$ = (sel, ctx) => [...(ctx || document).querySelectorAll(sel)];

  const screens = {
    warning:    $('#screen-warning'),
    welcome:    $('#screen-welcome'),
    disclaimer: $('#screen-disclaimer'),
    shop:       $('#screen-shop'),
    input:      $('#screen-input'),
    age:        $('#screen-age'),
    loading:    $('#screen-loading'),
    results:    $('#screen-results'),
    cart:       $('#screen-cart'),
    payment:    $('#screen-payment'),
    dispensing: $('#screen-dispensing'),
    complete:   $('#screen-complete'),
  };

  const els = {
    textArea:     $('#symptomText'),
    micBtn:       $('#micBtn'),
    micStatus:    $('#micStatus'),
    micOverlay:   $('#micOverlay'),
    micOverlayStatus: $('#micOverlayStatus'),
    micOverlayStop:   $('#micOverlayStop'),
    micOverlayCancel: $('#micOverlayCancel'),
    clearBtn:     $('#clearBtn'),
    nextToAge:    $('#nextToAge'),
    ageDisplay:   $('#ageDisplay'),
    ageConfirm:   $('#ageConfirm'),
    ageBack:      $('#ageBack'),
    resultsBody:  $('#resultsBody'),
    newAssess:    $('#newAssess'),
    printBtn:     $('#printBtn'),
    idleBarFill:  $('#idleBarFill'),
  };

  // ── cart DOM refs ──
  const cartEls = {
    viewCartBtn:      $('#viewCartBtn'),
    cartCount:        $('#cartCount'),
    cartBody:         $('#cartBody'),
    cartTotal:        $('#cartTotal'),
    cartTotalAmount:  $('#cartTotalAmount'),
    cartBack:         $('#cartBack'),
    cartProceed:      $('#cartProceed'),
    paymentSummary:   $('#paymentSummary'),
    paymentTotal:     $('#paymentTotal'),
    paymentTotalAmount: $('#paymentTotalAmount'),
    paymentBack:      $('#paymentBack'),
    paymentConfirm:   $('#paymentConfirm'),
    dispenseTitle:    $('#dispenseTitle'),
    dispenseProgress: $('#dispenseProgress'),
    dispenseStatus:   $('#dispenseStatus'),
    completeBody:     $('#completeBody'),
    completeDone:     $('#completeDone'),
  };

  // ── state ──
  let currentScreen = 'warning';
  let userAge = '';
  let idleTimer = null;
  let idleStart = 0;
  let idleRaf = null;

  // ── cart state ──
  // cart = [ { brand, dosage_form, active_ingredients, stock: {inventory_id, quantity, unit_price, ...}, qty } ]
  let cart = [];
  let _lastRecs = [];   // stash recommendations for going back from cart
  let _lastText = '';
  let _lastAge = 0;

  // ── screen navigation ──
  function goTo(name) {
    Object.values(screens).forEach(s => s?.classList.remove('active'));
    const target = screens[name];
    if (target) {
      target.classList.add('active');
      // re-trigger animation
      target.style.animation = 'none';
      target.offsetHeight; // reflow
      target.style.animation = '';
    }
    currentScreen = name;
    resetIdle();

    // focus management
    if (name === 'input') setTimeout(() => els.textArea?.focus(), 100);
  }

  // ── idle auto-reset ──
  function resetIdle() {
    idleStart = Date.now();
    if (els.idleBarFill) els.idleBarFill.style.width = '0%';
  }

  function tickIdle() {
    if (['welcome', 'loading', 'dispensing', 'complete'].includes(currentScreen)) {
      if (els.idleBarFill) els.idleBarFill.style.width = '0%';
      idleRaf = requestAnimationFrame(tickIdle);
      return;
    }
    const elapsed = (Date.now() - idleStart) / 1000;
    const pct = Math.min(100, (elapsed / IDLE_LIMIT) * 100);
    if (els.idleBarFill) els.idleBarFill.style.width = pct + '%';
    if (elapsed >= IDLE_LIMIT) {
      fullReset();
      return;
    }
    idleRaf = requestAnimationFrame(tickIdle);
  }

  function fullReset() {
    userAge = '';
    cart = [];
    _lastRecs = [];
    _lastText = '';
    _lastAge = 0;
    _shopInventory = [];
    _shopFrom = 'welcome';
    _updateCartBadge();
    _updateShopBadge();
    if (els.textArea) els.textArea.value = '';
    if (els.ageDisplay) els.ageDisplay.textContent = '';
    if (els.resultsBody) els.resultsBody.innerHTML = '';
    if (shopEls.search) shopEls.search.value = '';
    if (shopEls.body) shopEls.body.innerHTML = '';
    if (els.micStatus) { els.micStatus.textContent = ''; els.micStatus.classList.remove('mic-recording'); }
    goTo('warning');
  }

  // Touch / click resets idle
  document.addEventListener('pointerdown', resetIdle, { passive: true });
  document.addEventListener('keydown', resetIdle, { passive: true });

  // ── welcome ──
  $('#btnWarningNext')?.addEventListener('click', () => goTo('disclaimer'));

  // ── disclaimer ──
  $('#btnAgree')?.addEventListener('click', () => goTo('welcome'));
  $('#btnDisagreeBack')?.addEventListener('click', () => goTo('warning'));

  // ── welcome actions ──
  $('#btnAssess')?.addEventListener('click', () => goTo('input'));
  $('#btnViewMeds')?.addEventListener('click', () => {
    loadShopInventory();
    goTo('shop');
  });

  // ── input screen ──
  els.clearBtn?.addEventListener('click', () => {
    if (els.textArea) els.textArea.value = '';
    els.textArea?.focus();
  });

  els.nextToAge?.addEventListener('click', () => {
    const text = (els.textArea?.value || '').trim();
    if (!text) {
      els.textArea?.focus();
      shakeBtn(els.nextToAge);
      return;
    }
    userAge = '';
    if (els.ageDisplay) els.ageDisplay.textContent = '';
    goTo('age');
  });

  // ── age numpad ──
  $$('.numpad .btn[data-num]').forEach(btn => {
    btn.addEventListener('click', () => {
      const digit = btn.dataset.num;
      if (digit === 'clear') { userAge = ''; }
      else if (digit === 'back') { userAge = userAge.slice(0, -1); }
      else {
        if (userAge.length >= 3) return;
        userAge += digit;
      }
      if (els.ageDisplay) els.ageDisplay.textContent = userAge;
    });
  });

  els.ageBack?.addEventListener('click', () => goTo('input'));

  els.ageConfirm?.addEventListener('click', () => {
    const n = parseInt(userAge, 10);
    if (isNaN(n) || n < 0 || n > 120) {
      shakeBtn(els.ageConfirm);
      return;
    }
    submitAssessment(n);
  });

  // ── submit to backend ──
  async function submitAssessment(age) {
    goTo('loading');
    const text = (els.textArea?.value || '').trim();
    try {
      const res = await fetch(RECOMMEND_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, age, show_flow: false }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      renderResults(data, text, age);
    } catch (e) {
      renderError(e.message || String(e));
    }
  }

  // ── cough clarification re-submit ──
  async function submitWithCoughType(type, text, age) {
    goTo('loading');
    try {
      const res = await fetch(RECOMMEND_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, age, cough_type: type, show_flow: false }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
      renderResults(data, text, age);
    } catch (e) {
      renderError(e.message || String(e));
    }
  }

  // ── brand → image slug mapping ──
  function brandToSlug(brand) {
    return (brand || 'default')
      .toLowerCase()
      .replace(/\//g, '-').replace(/\(/g, '').replace(/\)/g, '')
      .replace(/\+/g, 'plus').replace(/\s+/g, '-')
      .replace(/-{2,}/g, '-').replace(/^-|-$/g, '');
  }

  function medImgSrc(brand) {
    const slug = brandToSlug(brand);
    return `/static/img/meds/${slug}.svg`;
  }

  function imgWithFallback(brand) {
    const src = medImgSrc(brand);
    return `<img class="rec__img" src="${src}" alt="${esc(brand)}" onerror="this.onerror=null;this.src='/static/img/meds/default.svg';">`;
  }

  function isPediatric(rec) {
    const name = String(rec?.brand || '').toLowerCase();
    if (/(kid|kids|child|children|pediatric|infant|baby)/.test(name)) return true;
    return false;
  }

  // ── stock / buy helpers ──
  let _posAvailable = false;

  function _stockBadge(r) {
    const s = r.stock;
    if (!s) return '';
    if (s.quantity <= 0) return '<span class="stock-badge stock-badge--out">Out of Stock</span>';
    if (s.low_stock) return `<span class="stock-badge stock-badge--low">Low (${s.quantity})</span>`;
    return `<span class="stock-badge stock-badge--in">In Stock</span>`;
  }

  function _renderBuySection(r, idx) {
    const s = r.stock;
    if (!_posAvailable || !s || !s.inventory_id) return '';
    const price = (s.unit_price || 0).toFixed(2);
    if (s.quantity <= 0) {
      return `<div class="rec__buy-section">
        <span class="rec__price">₱${price}</span>
        <button class="btn btn--buy btn--disabled" disabled>Out of Stock</button>
      </div>`;
    }
    // Check if already in cart
    const inCart = cart.find(c => c.stock.inventory_id === s.inventory_id);
    const cartQty = inCart ? inCart.qty : 0;
    return `<div class="rec__buy-section">
      <span class="rec__price">₱${price}</span>
      <div class="add-to-cart-controls" data-idx="${idx}">
        ${cartQty > 0
          ? `<div class="qty-controls">
              <button class="btn btn--icon qty-minus" data-cart-minus="${idx}">−</button>
              <span class="qty-display">${cartQty}</span>
              <button class="btn btn--icon qty-plus" data-cart-plus="${idx}">+</button>
            </div>`
          : `<button class="btn btn--buy btn--green" data-add-cart="${idx}">🛒 Add to Cart</button>`
        }
      </div>
    </div>`;
  }

  // ── cart helpers ──
  function _addToCart(rec) {
    const existing = cart.find(c => c.stock.inventory_id === rec.stock.inventory_id);
    if (existing) {
      if (existing.qty < rec.stock.quantity) existing.qty++;
    } else {
      cart.push({
        brand: rec.brand,
        dosage_form: rec.dosage_form || '',
        active_ingredients: rec.active_ingredients || '',
        stock: { ...rec.stock },
        qty: 1,
      });
    }
    _updateCartBadge();
  }

  function _removeFromCart(inventoryId) {
    const idx = cart.findIndex(c => c.stock.inventory_id === inventoryId);
    if (idx !== -1) {
      cart[idx].qty--;
      if (cart[idx].qty <= 0) cart.splice(idx, 1);
    }
    _updateCartBadge();
  }

  function _updateCartBadge() {
    const totalItems = cart.reduce((s, c) => s + c.qty, 0);
    if (cartEls.cartCount) cartEls.cartCount.textContent = totalItems;
    if (cartEls.viewCartBtn) {
      cartEls.viewCartBtn.style.display = totalItems > 0 ? '' : 'none';
    }
    // Hide "New Assessment" when cart has items to prevent accidental loss
    if (els.newAssess) {
      els.newAssess.style.display = totalItems > 0 ? 'none' : '';
    }
  }

  function _cartTotal() {
    return cart.reduce((s, c) => s + c.qty * (c.stock.unit_price || 0), 0);
  }

  // ── cart screen rendering ──
  function renderCartScreen() {
    const body = cartEls.cartBody;
    if (!body) return;
    body.innerHTML = '';

    if (!cart.length) {
      body.innerHTML = '<div class="text-muted" style="text-align:center;padding:32px 0;">Your cart is empty</div>';
      if (cartEls.cartTotal) cartEls.cartTotal.style.display = 'none';
      if (cartEls.cartProceed) cartEls.cartProceed.disabled = true;
      return;
    }

    const list = document.createElement('div');
    list.className = 'cart-list';

    cart.forEach((item, idx) => {
      const subtotal = (item.qty * (item.stock.unit_price || 0)).toFixed(2);
      const row = document.createElement('div');
      row.className = 'cart-item';
      row.innerHTML = `
        <div class="cart-item__info">
          ${imgWithFallback(item.brand)}
          <div>
            <div class="cart-item__brand">${esc(item.brand)}</div>
            <div class="cart-item__form">${esc(item.dosage_form)}</div>
            <div class="cart-item__price">₱${(item.stock.unit_price || 0).toFixed(2)} each</div>
          </div>
        </div>
        <div class="cart-item__right">
          <div class="qty-controls">
            <button class="btn btn--icon qty-minus" data-cidx="${idx}">−</button>
            <span class="qty-display">${item.qty}</span>
            <button class="btn btn--icon qty-plus" data-cidx="${idx}">+</button>
          </div>
          <div class="cart-item__subtotal">₱${subtotal}</div>
        </div>
      `;

      // Quantity controls
      row.querySelector('.qty-minus').addEventListener('click', () => {
        item.qty--;
        if (item.qty <= 0) cart.splice(idx, 1);
        _updateCartBadge();
        renderCartScreen();
      });
      row.querySelector('.qty-plus').addEventListener('click', () => {
        if (item.qty < item.stock.quantity) item.qty++;
        renderCartScreen();
      });

      list.appendChild(row);
    });
    body.appendChild(list);

    // Total
    const total = _cartTotal();
    if (cartEls.cartTotal) cartEls.cartTotal.style.display = '';
    if (cartEls.cartTotalAmount) cartEls.cartTotalAmount.textContent = `₱${total.toFixed(2)}`;
    if (cartEls.cartProceed) cartEls.cartProceed.disabled = false;
  }

  // ── payment screen rendering ──
  function renderPaymentScreen() {
    const summary = cartEls.paymentSummary;
    if (summary) {
      summary.innerHTML = cart.map(item => {
        const sub = (item.qty * (item.stock.unit_price || 0)).toFixed(2);
        return `<div class="payment-item">
          <span class="payment-item__name">${esc(item.brand)} × ${item.qty}</span>
          <span class="payment-item__price">₱${sub}</span>
        </div>`;
      }).join('');
    }
    const total = _cartTotal();
    if (cartEls.paymentTotalAmount) cartEls.paymentTotalAmount.textContent = `₱${total.toFixed(2)}`;
  }

  // ── batch dispense flow ──
  async function doBatchDispense() {
    goTo('dispensing');

    const items = cart.map(c => ({
      inventory_id: c.stock.inventory_id,
      brand: c.brand,
      quantity: c.qty,
    }));
    const total = _cartTotal();

    if (cartEls.dispenseTitle) cartEls.dispenseTitle.textContent = 'Processing payment…';
    if (cartEls.dispenseStatus) cartEls.dispenseStatus.textContent = 'Creating transaction…';
    if (cartEls.dispenseProgress) cartEls.dispenseProgress.innerHTML = '';

    try {
      const res = await fetch('/api/vend/batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          items,
          age: _lastAge,
          amount_tendered: total,
        }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || 'Purchase failed');

      // Show dispensing progress
      if (cartEls.dispenseTitle) cartEls.dispenseTitle.textContent = 'Dispensing your medicine…';

      const dispResults = d.dispense_results || [];
      const progressEl = cartEls.dispenseProgress;
      if (progressEl) {
        progressEl.innerHTML = dispResults.map(dr => {
          const icon = dr.dispensed ? '✅' : (dr.no_slot ? '📦' : '⚠️');
          const qty = dr.qty_dispensed || 0;
          return `<div class="dispense-item ${dr.dispensed ? 'dispense-item--ok' : 'dispense-item--warn'}">
            <span>${icon} ${esc(dr.brand)} × ${qty}</span>
            <span class="dispense-item__msg">${esc(dr.message)}</span>
          </div>`;
        }).join('');
      }

      if (cartEls.dispenseStatus) cartEls.dispenseStatus.textContent = 'Please collect your medicine below.';

      // Wait a moment then show complete screen
      setTimeout(() => {
        showCompleteScreen(d);
      }, 2500);

    } catch (e) {
      if (cartEls.dispenseTitle) cartEls.dispenseTitle.textContent = 'Error';
      if (cartEls.dispenseStatus) {
        cartEls.dispenseStatus.textContent = '❌ ' + (e?.message || 'Purchase failed');
        cartEls.dispenseStatus.style.color = 'var(--red)';
      }
      // Allow retry after 3s
      setTimeout(() => {
        goTo('payment');
      }, 4000);
    }
  }

  // ── order complete screen ──
  function showCompleteScreen(data) {
    const body = cartEls.completeBody;
    if (!body) { goTo('complete'); return; }

    const txn = data.transaction || {};
    body.innerHTML = `
      <div class="complete-ref">Ref: ${esc(txn.transaction_ref || '')}</div>
      <div class="complete-items">
        ${(txn.items || []).map(it =>
          `<div class="complete-item">
            <span>${esc(it.brand)} × ${it.quantity}</span>
            <span>₱${(it.subtotal || 0).toFixed(2)}</span>
          </div>`
        ).join('')}
      </div>
      <div class="complete-total">
        <span>Total Paid</span>
        <span>₱${(txn.total_amount || 0).toFixed(2)}</span>
      </div>
      <div class="complete-dispense-summary">
        ${(data.dispense_results || []).map(dr => {
          const icon = dr.dispensed ? '💊' : '📦';
          return `<div>${icon} ${esc(dr.brand)} × ${dr.qty_dispensed || 0} — ${esc(dr.message)}</div>`;
        }).join('')}
      </div>
    `;

    // Clear cart
    cart = [];
    _updateCartBadge();

    goTo('complete');
  }

  // ── render results ──
  function renderResults(data, text, age) {
    const body = els.resultsBody;
    if (!body) return goTo('results');
    body.innerHTML = '';
    _posAvailable = !!data.pos_available;
    _lastRecs = data.recommendations || [];
    _lastText = text;
    _lastAge = age;

    const clarify = data.clarify || {};
    const detected = data.detected_labels || [];
    const recs = data.recommendations || [];
    const filtered = data.age_filtered_out || [];

    // Detected symptoms chips
    const chipsHtml = detected.length
      ? detected.map(s => `<span class="chip chip--green">${esc(s)}</span>`).join('')
      : '<span class="chip chip--amber">No symptoms detected</span>';
    body.innerHTML += `<div class="chips">${chipsHtml}</div>`;

    // Cough clarification
    if (clarify.needed) {
      const card = document.createElement('div');
      card.className = 'clarify-card';
      card.innerHTML = `
        <div class="step-title" style="font-size:18px;">Clarification needed</div>
        <div class="step-sub text-amber">${esc(clarify.question || 'Is your cough dry or with phlegm?')}</div>
        <div class="btn-row" style="justify-content:center;">
          <button class="btn btn--amber btn--lg" data-cough="dry">🫁 Dry (walang plema)</button>
          <button class="btn btn--green btn--lg" data-cough="productive">💧 With phlegm (may plema)</button>
        </div>
      `;
      card.querySelectorAll('[data-cough]').forEach(b => {
        b.addEventListener('click', () => submitWithCoughType(b.dataset.cough, text, age));
      });
      body.appendChild(card);
      goTo('results');
      return;
    }

    // Recommendations — clickable cards with images
    if (recs.length) {
      const list = document.createElement('div');
      list.className = 'rec-list';

      const isAdultUser = Number(age) >= 18;
      const withFlags = recs.map(r => ({ ...r, _isPeds: isPediatric(r) }));
      const ordered = isAdultUser
        ? [...withFlags.filter(r => !r._isPeds), ...withFlags.filter(r => r._isPeds)]
        : withFlags;

      ordered.forEach((r, idx) => {
        const card = document.createElement('div');
        card.className = `rec${isAdultUser && r._isPeds ? ' rec--dim' : ''}`;
        card.setAttribute('role', 'button');
        card.setAttribute('tabindex', '0');

        // Category badge colour
        const catCls = _catClass(r.drug_category);

        card.innerHTML = `
          <div class="rec__summary">
            ${imgWithFallback(r.brand)}
            <div class="rec__info">
              <div class="rec__brand">
                ${esc(r.brand)}
                ${r.dosage_form ? `<span class="rec__form-pill">${esc(r.dosage_form)}</span>` : ''}
                ${_stockBadge(r)}
              </div>
              <div class="rec__meta">
                ${r.drug_category ? `<span class="rec__cat ${catCls}">${esc(r.drug_category)}</span>` : ''}
                ${isAdultUser && r._isPeds ? `<span class="rec__pill rec__pill--dim">Pediatric</span>` : ''}
              </div>
              <div class="rec__active">${esc(r.active_ingredients || '')}</div>
            </div>
            <div class="rec__chevron">▼</div>
          </div>
          <div class="rec__detail" id="rec-detail-${idx}">
            ${r.dosage ? `<div class="rec__section"><div class="rec__label">💊 Dosage (Age ${esc(age)})</div><div class="rec__dosage-text">${esc(r.dosage).replace(/\n/g, '<br>')}</div></div>` : ''}
            ${r.reason ? `<div class="rec__section"><div class="rec__label">🔍 Why recommended</div><div class="rec__reason-text">${esc(r.reason)}</div></div>` : ''}
            ${r.notes ? `<div class="rec__section"><div class="rec__label">📝 Notes</div><div class="rec__notes-text">${esc(r.notes).replace(/\n/g, '<br>')}</div></div>` : ''}
            ${_renderBuySection(r, idx)}
          </div>
        `;

        // Click/tap to expand/collapse (accordion behavior)
        const toggle = () => {
          const isOpen = card.classList.contains('rec--open');
          // close all first
          list.querySelectorAll('.rec--open').forEach(el => el.classList.remove('rec--open'));
          // open this one if it was closed
          if (!isOpen) card.classList.add('rec--open');
        };
        card.addEventListener('click', toggle);
        card.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });

        // Add-to-cart / quantity controls — stop propagation
        const addBtn = card.querySelector('[data-add-cart]');
        if (addBtn) {
          addBtn.addEventListener('click', e => {
            e.stopPropagation();
            _addToCart(r);
            // Re-render buy section in this card
            _refreshBuySection(card, r, idx);
          });
        }
        // Quantity +/- in results cards
        card.querySelectorAll('[data-cart-minus]').forEach(btn => {
          btn.addEventListener('click', e => {
            e.stopPropagation();
            _removeFromCart(r.stock.inventory_id);
            _refreshBuySection(card, r, idx);
          });
        });
        card.querySelectorAll('[data-cart-plus]').forEach(btn => {
          btn.addEventListener('click', e => {
            e.stopPropagation();
            _addToCart(r);
            _refreshBuySection(card, r, idx);
          });
        });

        list.appendChild(card);
      });

      body.appendChild(list);
    } else if (!clarify.needed) {
      body.innerHTML += '<div class="text-muted mt-16">No matching recommendations found for this combination.</div>';
    }

    // Filtered out by age
    if (filtered.length) {
      const names = filtered.map(f => f.brand).join(', ');
      body.innerHTML += `<div class="filtered-notice">⚠ Filtered out for age ${age}: ${esc(names)}</div>`;
    }

    goTo('results');
  }

  /** Map drug_category → CSS modifier class */
  function _catClass(cat) {
    if (!cat) return '';
    const c = cat.toLowerCase();
    if (c.includes('cold') || c.includes('flu') || c.includes('sinus')) return 'rec__cat--blue';
    if (c.includes('cough') || c.includes('expectorant') || c.includes('suppressant')) return 'rec__cat--purple';
    if (c.includes('pain') || c.includes('fever')) return 'rec__cat--red';
    if (c.includes('allergy')) return 'rec__cat--green';
    if (c.includes('diarrhea')) return 'rec__cat--amber';
    if (c.includes('probiotic') || c.includes('gi')) return 'rec__cat--teal';
    if (c.includes('antacid')) return 'rec__cat--amber';
    return 'rec__cat--default';
  }

  function renderError(msg) {
    if (els.resultsBody) {
      els.resultsBody.innerHTML = `
        <div class="step-sub text-muted" style="margin-bottom:0;">
          Something went wrong: ${esc(msg)}
        </div>`;
    }
    goTo('results');
  }

  // ── result actions ──
  els.newAssess?.addEventListener('click', fullReset);
  els.printBtn?.addEventListener('click', () => window.print());

  // ── _refreshBuySection — re-render just the buy section in a rec card ──
  function _refreshBuySection(card, rec, idx) {
    const existing = card.querySelector('.rec__buy-section')?.parentNode;
    if (!existing) return;
    const detail = card.querySelector('.rec__detail');
    if (!detail) return;
    // Remove old buy section
    const oldBuy = detail.querySelector('.rec__buy-section');
    if (oldBuy) oldBuy.remove();
    // Append new one
    const html = _renderBuySection(rec, idx);
    if (html) {
      const tmp = document.createElement('div');
      tmp.innerHTML = html;
      const newBuy = tmp.firstElementChild;
      detail.appendChild(newBuy);
      // Rebind events
      const addBtn = newBuy.querySelector('[data-add-cart]');
      if (addBtn) {
        addBtn.addEventListener('click', e => {
          e.stopPropagation();
          _addToCart(rec);
          _refreshBuySection(card, rec, idx);
        });
      }
      newBuy.querySelectorAll('[data-cart-minus]').forEach(btn => {
        btn.addEventListener('click', e => {
          e.stopPropagation();
          _removeFromCart(rec.stock.inventory_id);
          _refreshBuySection(card, rec, idx);
        });
      });
      newBuy.querySelectorAll('[data-cart-plus]').forEach(btn => {
        btn.addEventListener('click', e => {
          e.stopPropagation();
          _addToCart(rec);
          _refreshBuySection(card, rec, idx);
        });
      });
    }
  }

  // ── kiosk shop (browse & buy without AI) ──
  const shopEls = {
    body:       $('#shopBody'),
    search:     $('#shopSearch'),
    back:       $('#shopBack'),
    cartBtn:    $('#shopCartBtn'),
    cartCount:  $('#shopCartCount'),
    viewCart:   $('#shopViewCart'),
  };
  let _shopInventory = [];  // cached inventory data
  let _shopFrom = 'welcome';  // track where we came from

  async function loadShopInventory() {
    if (shopEls.body) shopEls.body.innerHTML = '<div class="spinner-wrap"><div class="spinner"></div><div class="text-muted" style="font-size:13px;">Loading inventory…</div></div>';
    try {
      const res = await fetch('/api/kiosk/inventory');
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to load inventory');
      _shopInventory = data;
      renderShopItems(_shopInventory);
    } catch (e) {
      if (shopEls.body) shopEls.body.innerHTML = `<div class="text-muted" style="text-align:center;padding:32px 0;">⚠️ ${esc(e.message || 'Could not load inventory')}</div>`;
    }
  }

  function renderShopItems(items) {
    const body = shopEls.body;
    if (!body) return;
    body.innerHTML = '';

    if (!items.length) {
      body.innerHTML = '<div class="text-muted" style="text-align:center;padding:32px 0;">No medicine available right now.</div>';
      return;
    }

    const list = document.createElement('div');
    list.className = 'rec-list';

    items.forEach((item, idx) => {
      const inCart = cart.find(c => c.stock.inventory_id === item.id);
      const cartQty = inCart ? inCart.qty : 0;
      const price = (item.unit_price || 0).toFixed(2);

      let stockBadge = '';
      if (item.stock_quantity <= 0) stockBadge = '<span class="stock-badge stock-badge--out">Out of Stock</span>';
      else if (item.low_stock) stockBadge = `<span class="stock-badge stock-badge--low">Low (${item.stock_quantity})</span>`;
      else stockBadge = '<span class="stock-badge stock-badge--in">In Stock</span>';

      const catCls = _catClass(item.category);

      const card = document.createElement('div');
      card.className = 'rec';
      card.setAttribute('role', 'button');
      card.setAttribute('tabindex', '0');

      const buySection = item.stock_quantity <= 0
        ? `<div class="rec__buy-section"><span class="rec__price">₱${price}</span><button class="btn btn--buy btn--disabled" disabled>Out of Stock</button></div>`
        : `<div class="rec__buy-section">
            <span class="rec__price">₱${price}</span>
            <div class="add-to-cart-controls">
              ${cartQty > 0
                ? `<div class="qty-controls">
                    <button class="btn btn--icon qty-minus shop-minus" data-shop-idx="${idx}">−</button>
                    <span class="qty-display">${cartQty}</span>
                    <button class="btn btn--icon qty-plus shop-plus" data-shop-idx="${idx}">+</button>
                  </div>`
                : `<button class="btn btn--buy btn--green shop-add" data-shop-idx="${idx}">🛒 Add to Cart</button>`
              }
            </div>
          </div>`;

      card.innerHTML = `
        <div class="rec__summary">
          ${imgWithFallback(item.brand)}
          <div class="rec__info">
            <div class="rec__brand">
              ${esc(item.brand)}
              ${item.dosage_form ? `<span class="rec__form-pill">${esc(item.dosage_form)}</span>` : ''}
              ${stockBadge}
            </div>
            <div class="rec__meta">
              ${item.category ? `<span class="rec__cat ${catCls}">${esc(item.category)}</span>` : ''}
            </div>
            <div class="rec__active">${esc(item.generic_name || '')}</div>
          </div>
          <div class="rec__chevron">▼</div>
        </div>
        <div class="rec__detail">
          ${buySection}
        </div>
      `;

      // Toggle expand/collapse
      const toggle = () => {
        const isOpen = card.classList.contains('rec--open');
        list.querySelectorAll('.rec--open').forEach(el => el.classList.remove('rec--open'));
        if (!isOpen) card.classList.add('rec--open');
      };
      card.addEventListener('click', toggle);
      card.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); } });

      // Add to cart
      const addBtn = card.querySelector('.shop-add');
      if (addBtn) {
        addBtn.addEventListener('click', e => {
          e.stopPropagation();
          _shopAddToCart(item);
          renderShopItems(_filterShopItems());
        });
      }
      // Qty minus
      card.querySelectorAll('.shop-minus').forEach(btn => {
        btn.addEventListener('click', e => {
          e.stopPropagation();
          _removeFromCart(item.id);
          renderShopItems(_filterShopItems());
        });
      });
      // Qty plus
      card.querySelectorAll('.shop-plus').forEach(btn => {
        btn.addEventListener('click', e => {
          e.stopPropagation();
          _shopAddToCart(item);
          renderShopItems(_filterShopItems());
        });
      });

      list.appendChild(card);
    });
    body.appendChild(list);
    _updateShopBadge();
  }

  function _shopAddToCart(item) {
    const existing = cart.find(c => c.stock.inventory_id === item.id);
    if (existing) {
      if (existing.qty < item.stock_quantity) existing.qty++;
    } else {
      cart.push({
        brand: item.brand,
        dosage_form: item.dosage_form || '',
        active_ingredients: item.generic_name || '',
        stock: {
          inventory_id: item.id,
          in_stock: item.stock_quantity > 0,
          quantity: item.stock_quantity,
          unit_price: item.unit_price,
          low_stock: item.low_stock,
        },
        qty: 1,
      });
    }
    _updateCartBadge();
    _updateShopBadge();
  }

  function _updateShopBadge() {
    const totalItems = cart.reduce((s, c) => s + c.qty, 0);
    if (shopEls.cartBtn) {
      shopEls.cartBtn.style.display = totalItems > 0 ? '' : 'none';
    }
    if (shopEls.cartCount) shopEls.cartCount.textContent = totalItems;
    if (shopEls.viewCart) {
      shopEls.viewCart.style.display = totalItems > 0 ? '' : 'none';
    }
  }

  function _filterShopItems() {
    const q = (shopEls.search?.value || '').trim().toLowerCase();
    if (!q) return _shopInventory;
    return _shopInventory.filter(it =>
      (it.brand || '').toLowerCase().includes(q) ||
      (it.generic_name || '').toLowerCase().includes(q) ||
      (it.category || '').toLowerCase().includes(q)
    );
  }

  // Search filter
  shopEls.search?.addEventListener('input', () => {
    renderShopItems(_filterShopItems());
  });

  // Shop navigation
  shopEls.back?.addEventListener('click', () => goTo('welcome'));
  shopEls.cartBtn?.addEventListener('click', () => {
    _shopFrom = 'shop';
    renderCartScreen();
    goTo('cart');
  });
  shopEls.viewCart?.addEventListener('click', () => {
    _shopFrom = 'shop';
    renderCartScreen();
    goTo('cart');
  });

  // ── cart navigation ──
  cartEls.viewCartBtn?.addEventListener('click', () => {
    _shopFrom = 'results';
    renderCartScreen();
    goTo('cart');
  });
  cartEls.cartBack?.addEventListener('click', () => {
    if (_shopFrom === 'shop') {
      renderShopItems(_filterShopItems());
      goTo('shop');
    } else {
      goTo('results');
    }
  });
  cartEls.cartProceed?.addEventListener('click', () => {
    if (!cart.length) return;
    renderPaymentScreen();
    goTo('payment');
  });
  cartEls.paymentBack?.addEventListener('click', () => {
    renderCartScreen();
    goTo('cart');
  });
  cartEls.paymentConfirm?.addEventListener('click', () => {
    if (!cart.length) return;
    doBatchDispense();
  });
  cartEls.completeDone?.addEventListener('click', fullReset);

  // ── offline STT (mic) ──
  let recording = false;
  let audioCtx = null, mediaStream = null, processor = null, sourceNode = null;
  let buffers = [], sampleRate = 44100;

  const supportsMic = () => !!navigator.mediaDevices?.getUserMedia;
  const isSecure = () => window.isSecureContext || ['localhost','127.0.0.1'].includes(location.hostname);

  function setMicStatus(txt, isRec) {
    if (!els.micStatus) return;
    els.micStatus.textContent = txt || '';
    els.micStatus.classList.toggle('mic-recording', !!isRec);
  }

  async function startRecording() {
    if (!supportsMic()) { setMicStatus('Mic not supported in this browser.'); return; }
    if (!isSecure()) { setMicStatus('Mic needs localhost or HTTPS.'); return; }
    try {
      setMicStatus('Requesting microphone…');
      mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      setMicStatus('Mic permission denied: ' + (e?.name || e?.message || e)); return;
    }
    buffers = [];
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    sampleRate = audioCtx.sampleRate || 44100;
    sourceNode = audioCtx.createMediaStreamSource(mediaStream);
    processor = audioCtx.createScriptProcessor(4096, 1, 1);
    processor.onaudioprocess = ev => buffers.push(new Float32Array(ev.inputBuffer.getChannelData(0)));
    sourceNode.connect(processor);
    processor.connect(audioCtx.destination);
    recording = true;
    if (els.micBtn) els.micBtn.classList.add('mic-orb--recording');
    setMicStatus('Recording…', true);
    // Show Siri overlay
    if (els.micOverlay) els.micOverlay.classList.add('active');
    if (els.micOverlayStatus) els.micOverlayStatus.textContent = 'Listening…';
  }

  async function stopRecording({ transcribe = true } = {}) {
    recording = false;
    if (els.micBtn) els.micBtn.classList.remove('mic-orb--recording');
    try { processor?.disconnect(); } catch {}
    try { sourceNode?.disconnect(); } catch {}
    try { processor && (processor.onaudioprocess = null); } catch {}
    try { mediaStream?.getTracks().forEach(t => t.stop()); } catch {}
    try { audioCtx?.close && await audioCtx.close(); } catch {}

    const samples = mergeBuffers(buffers);
    if (!transcribe) {
      if (els.micOverlay) els.micOverlay.classList.remove('active');
      setMicStatus(''); return;
    }
    if (!samples.length) {
      if (els.micOverlay) els.micOverlay.classList.remove('active');
      setMicStatus('No audio captured.'); return;
    }

    // Show transcribing state in overlay before closing
    if (els.micOverlayStatus) els.micOverlayStatus.textContent = 'Transcribing…';
    const wav = encodeWav16(samples, sampleRate);
    const fd = new FormData();
    fd.append('audio', wav, 'speech.wav');
    setMicStatus('Transcribing…');
    try {
      const res = await fetch(STT_URL, { method: 'POST', body: fd });
      const d = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(d.error || 'STT failed');
      const t = (d.text || '').trim();
      if (els.micOverlay) els.micOverlay.classList.remove('active');
      if (!t) { setMicStatus('No speech recognized.'); return; }
      const existing = (els.textArea?.value || '').trim();
      if (els.textArea) els.textArea.value = [existing, t].filter(Boolean).join(' ');
      setMicStatus('');
      els.textArea?.focus();
    } catch (e) {
      if (els.micOverlay) els.micOverlay.classList.remove('active');
      setMicStatus('STT error: ' + (e?.message || e));
    }
  }

  els.micBtn?.addEventListener('click', () => {
    if (!supportsMic()) return;
    recording ? stopRecording() : startRecording();
  });

  els.micOverlayStop?.addEventListener('click', () => {
    if (recording) stopRecording();
  });

  els.micOverlayCancel?.addEventListener('click', () => {
    if (recording) stopRecording({ transcribe: false });
    if (els.micOverlay) els.micOverlay.classList.remove('active');
  });

  function mergeBuffers(chunks) {
    const total = chunks.reduce((s, a) => s + a.length, 0);
    const out = new Float32Array(total);
    let off = 0;
    for (const c of chunks) { out.set(c, off); off += c.length; }
    return out;
  }

  function encodeWav16(samples, sr) {
    const clamp = v => Math.max(-1, Math.min(1, v));
    const pcm = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i++) pcm[i] = Math.round(clamp(samples[i]) * 0x7fff);
    const hdr = 44, ds = pcm.length * 2, buf = new ArrayBuffer(hdr + ds), dv = new DataView(buf);
    let p = 0;
    const w32 = v => { dv.setUint32(p, v, true); p += 4; };
    const w16 = v => { dv.setUint16(p, v, true); p += 2; };
    const ws = s => { for (let i = 0; i < s.length; i++) dv.setUint8(p++, s.charCodeAt(i)); };
    ws('RIFF'); w32(36 + ds); ws('WAVE'); ws('fmt '); w32(16); w16(1); w16(1);
    w32(sr); w32(sr * 2); w16(2); w16(16); ws('data'); w32(ds);
    let o = hdr;
    for (let i = 0; i < pcm.length; i++, o += 2) dv.setInt16(o, pcm[i], true);
    return new Blob([buf], { type: 'audio/wav' });
  }

  // ── helpers ──
  function esc(s) {
    const d = document.createElement('div');
    d.textContent = String(s ?? '');
    return d.innerHTML;
  }

  function shakeBtn(el) {
    if (!el) return;
    el.style.animation = 'none';
    el.offsetHeight;
    el.style.animation = 'shake .4s ease';
    setTimeout(() => { el.style.animation = ''; }, 500);
  }

  // shake keyframes (injected once)
  const style = document.createElement('style');
  style.textContent = `@keyframes shake{0%,100%{transform:translateX(0)}20%,60%{transform:translateX(-6px)}40%,80%{transform:translateX(6px)}}`;
  document.head.appendChild(style);

  // ── boot ──
  goTo('warning');
  idleRaf = requestAnimationFrame(tickIdle);
})();
