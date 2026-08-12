/**
 * Mendo POS — Client-Side JavaScript
 * Professional POS interactions: shop, inventory, transactions, users.
 */

const POS = (() => {

  // ─── Utilities ─────────────────────────────────

  const fmt = (n) => '₱' + Number(n || 0).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ',');

  async function api(url, opts = {}) {
    const defaults = {
      headers: { 'Content-Type': 'application/json' },
    };
    const res = await fetch(url, {
      ...defaults,
      ...opts,
      headers: { ...defaults.headers, ...(opts.headers || {}) },
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.error || `Request failed (${res.status})`);
    }
    return data;
  }

  // ─── Toast Notifications ──────────────────────

  function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.innerHTML = `
      <span>${message}</span>
      <button onclick="this.parentElement.remove()">&times;</button>
    `;
    container.appendChild(toast);
    setTimeout(() => toast.classList.add('toast--show'), 10);
    setTimeout(() => {
      toast.classList.remove('toast--show');
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  // ─── Modals ───────────────────────────────────

  function openModal(id) {
    const el = document.getElementById(id);
    if (el) {
      el.classList.add('active');
      document.body.style.overflow = 'hidden';
    }
  }

  function closeModal(id) {
    const el = document.getElementById(id);
    if (el) {
      el.classList.remove('active');
      document.body.style.overflow = '';
    }
  }

  // Close modals on overlay click
  document.addEventListener('click', (e) => {
    if (e.target.classList.contains('modal-overlay') && e.target.classList.contains('active')) {
      if (e.target.id === 'hardwarePaymentModal') return;
      e.target.classList.remove('active');
      document.body.style.overflow = '';
    }
  });

  // Close modals on Escape
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-overlay.active').forEach(m => {
        if (m.id === 'hardwarePaymentModal') return;
        m.classList.remove('active');
      });
      document.body.style.overflow = '';
    }
  });

  // ═══════════════════════════════════════════════
  //  SHOP MODULE (Cashier View)
  // ═══════════════════════════════════════════════

  const shop = {
    products: [],
    cart: { items: [], total: 0, item_count: 0 },
    activeOrder: null,
    paymentPoll: null,
    checkoutKey: null,

    init() {
      this.loadProducts();
      this.loadCart();

      const searchInput = document.getElementById('shopSearch');
      if (searchInput) {
        searchInput.addEventListener('input', () => this.filterProducts(searchInput.value));
      }

      const clearBtn = document.getElementById('cartClearBtn');
      if (clearBtn) {
        clearBtn.addEventListener('click', () => this.clearCart());
      }

      const checkoutBtn = document.getElementById('checkoutBtn');
      if (checkoutBtn) {
        checkoutBtn.addEventListener('click', () => this.checkout());
      }

    },

    async loadProducts() {
      try {
        this.products = await api('/shop/api/products');
        this.renderProducts(this.products);
      } catch (err) {
        showToast('Failed to load products: ' + err.message, 'error');
      }
    },

    renderProducts(items) {
      const grid = document.getElementById('productGrid');
      if (!grid) return;

      if (!items.length) {
        grid.innerHTML = '<div class="text-center text-muted" style="grid-column:1/-1;padding:60px 0;">No products found</div>';
        return;
      }

      grid.innerHTML = items.map(p => `
        <div class="product-card ${p.available_quantity <= 0 ? 'product-card--oos' : ''}"
             onclick="${p.available_quantity > 0 ? `POS.shop.addToCart(${p.id})` : ''}"
             title="${p.generic_name || ''}">
          <div class="text-xs text-muted">Hardware slot #${p.hardware_slot}</div>
          <div class="product-card__name">${p.brand}</div>
          <div class="product-card__generic">${p.generic_name || ''}</div>
          <div class="product-card__meta">
            <span class="product-card__price">${fmt(p.unit_price)}</span>
            <span class="product-card__stock ${p.available_quantity <= 0 ? 'text-danger' : p.available_quantity <= p.min_stock_level ? 'text-warning' : ''}">${p.available_quantity <= 0 ? 'Out of stock' : p.available_quantity + ' available'}</span>
          </div>
          ${p.category ? `<span class="product-card__cat">${p.category}</span>` : ''}
        </div>
      `).join('');
    },

    filterProducts(q) {
      const term = q.toLowerCase().trim();
      if (!term) {
        this.renderProducts(this.products);
        return;
      }
      const filtered = this.products.filter(p =>
        p.brand.toLowerCase().includes(term) ||
        (p.generic_name || '').toLowerCase().includes(term) ||
        (p.category || '').toLowerCase().includes(term)
      );
      this.renderProducts(filtered);
    },

    async addToCart(inventoryId) {
      try {
        const data = await api('/shop/api/cart/add', {
          method: 'POST',
          body: JSON.stringify({ inventory_id: inventoryId, quantity: 1 }),
        });
        showToast(data.message || 'Added to cart', 'success');
        this.loadCart();
      } catch (err) {
        showToast(err.message, 'error');
      }
    },

    async loadCart() {
      try {
        this.cart = await api('/shop/api/cart');
        this.renderCart();
      } catch (err) {
        showToast('Failed to load cart', 'error');
      }
    },

    renderCart() {
      const container = document.getElementById('cartItems');
      const emptyMsg = document.getElementById('cartEmpty');
      const totalEl = document.getElementById('cartTotal');
      const checkoutBtn = document.getElementById('checkoutBtn');

      if (!container) return;

      if (!this.cart.items.length) {
        container.innerHTML = '';
        if (emptyMsg) {
          emptyMsg.style.display = 'flex';
          container.appendChild(emptyMsg);
        }
        if (totalEl) totalEl.textContent = '₱0.00';
        if (checkoutBtn) checkoutBtn.disabled = true;
        this.updateChange();
        return;
      }

      if (emptyMsg) emptyMsg.style.display = 'none';

      container.innerHTML = this.cart.items.map(ci => `
        <div class="cart-item">
          <div class="cart-item__info">
            <div class="cart-item__name">${ci.brand}</div>
            <div class="cart-item__price">${fmt(ci.unit_price)} each</div>
          </div>
          <div class="cart-item__controls">
            <button class="qty-btn" onclick="POS.shop.updateQty(${ci.inventory_id}, ${ci.quantity - 1})">−</button>
            <span class="qty-value">${ci.quantity}</span>
            <button class="qty-btn" onclick="POS.shop.updateQty(${ci.inventory_id}, ${ci.quantity + 1})">+</button>
          </div>
          <div class="cart-item__subtotal">${fmt(ci.subtotal)}</div>
          <button class="cart-item__remove" onclick="POS.shop.removeItem(${ci.inventory_id})" title="Remove">&times;</button>
        </div>
      `).join('');

      if (totalEl) totalEl.textContent = fmt(this.cart.total);
      if (checkoutBtn) checkoutBtn.disabled = false;
      this.updateChange();
    },

    async updateQty(inventoryId, newQty) {
      try {
        if (newQty <= 0) {
          await this.removeItem(inventoryId);
          return;
        }
        await api('/shop/api/cart/update', {
          method: 'POST',
          body: JSON.stringify({ inventory_id: inventoryId, quantity: newQty }),
        });
        this.loadCart();
      } catch (err) {
        showToast(err.message, 'error');
      }
    },

    async removeItem(inventoryId) {
      try {
        await api('/shop/api/cart/remove', {
          method: 'POST',
          body: JSON.stringify({ inventory_id: inventoryId }),
        });
        this.loadCart();
      } catch (err) {
        showToast(err.message, 'error');
      }
    },

    async clearCart() {
      if (!this.cart.items.length) return;
      if (!confirm('Clear all items from the cart?')) return;
      try {
        await api('/shop/api/cart/clear', { method: 'POST' });
        this.loadCart();
        showToast('Cart cleared', 'info');
      } catch (err) {
        showToast(err.message, 'error');
      }
    },

    updateChange() {
      const amountInput = document.getElementById('amountTendered');
      const changeEl = document.getElementById('changeAmount');
      if (!amountInput || !changeEl) return;
      const tendered = parseFloat(amountInput.value) || 0;
      const change = tendered - (this.cart.total || 0);
      changeEl.textContent = fmt(Math.max(0, change));
      changeEl.classList.toggle('text-danger', change < 0 && tendered > 0);
    },

    async checkout() {
      if (!this.cart.items.length) {
        showToast('Cart is empty', 'warning');
        return;
      }
      if (!confirm(`Start the cash acceptor for ${fmt(this.cart.total)}? This machine gives no change.`)) return;

      try {
        if (!this.checkoutKey) {
          this.checkoutKey = `cashier-ui-${Date.now()}-${Math.random().toString(36).slice(2)}`;
        }
        const result = await api('/shop/api/checkout', {
          method: 'POST',
          headers: { 'Idempotency-Key': this.checkoutKey },
          body: JSON.stringify({
            payment_method: 'cash',
            no_change_consent: true,
          }),
        });
        this.activeOrder = result.order || result;
        this.renderHardwarePayment(this.activeOrder, result.hardware || {});
        openModal('hardwarePaymentModal');
        clearInterval(this.paymentPoll);
        this.paymentPoll = setInterval(() => this.pollHardwarePayment(false), 750);
        this.pollHardwarePayment(false);
      } catch (err) {
        showToast('Checkout failed: ' + err.message, 'error');
      }
    },

    renderHardwarePayment(order, fallbackHardware = {}) {
      if (!order) return;
      const hardware = order.hardware || fallbackHardware || {};
      const due = document.getElementById('hardwareAmountDue');
      const inserted = document.getElementById('hardwareAmountInserted');
      const remaining = document.getElementById('hardwareAmountRemaining');
      const state = document.getElementById('hardwarePaymentState');
      const cancel = document.getElementById('hardwareCancelBtn');
      const simulator = document.getElementById('hardwareSimulatorControls');
      if (due) due.textContent = order.amount_due_display || fmt(order.amount_due || 0);
      if (inserted) inserted.textContent = order.received_cash_display || fmt(order.received_cash || 0);
      if (remaining) remaining.textContent = order.remaining_display || fmt(order.remaining || 0);
      if (simulator) simulator.style.display = hardware.simulator ? 'block' : 'none';
      if (cancel) cancel.style.display = Number(order.received_cash_centavos || 0) === 0 && order.payment_state === 'awaiting_cash' ? '' : 'none';
      if (state) {
        const label = hardware.mode_label || (hardware.simulator ? 'SIMULATOR' : 'REAL CONTROLLER');
        const eventCount = (order.cash_events || []).length;
        if (order.payment_state === 'manual_review' || order.fulfillment_state === 'manual_review') {
          state.innerHTML = `<strong style="color:#9a3e2f">Staff review required</strong><br>${order.failure_reason || 'The pulse evidence could not be credited safely.'}`;
        } else if (order.fulfillment_state === 'completed') {
          state.innerHTML = `<strong style="color:#23643d">Payment successful — stock updated</strong><br>${label} · ${eventCount} cash event${eventCount === 1 ? '' : 's'} recorded · no motor command sent`;
        } else {
          state.innerHTML = `<strong>Waiting for coins or bills…</strong><br>${label} · ${eventCount} cash event${eventCount === 1 ? '' : 's'} recorded`;
        }
      }
    },

    async pollHardwarePayment(showError = false) {
      if (!this.activeOrder?.order_ref) return;
      try {
        const order = await api(`/checkout/api/orders/${encodeURIComponent(this.activeOrder.order_ref)}`);
        this.activeOrder = order;
        this.renderHardwarePayment(order);
        if (order.fulfillment_state === 'completed') {
          clearInterval(this.paymentPoll);
          this.paymentPoll = null;
          await api('/shop/api/cart/clear', { method: 'POST' });
          closeModal('hardwarePaymentModal');
          this.showReceipt(order);
          this.cart = { items: [], total: 0, item_count: 0 };
          this.checkoutKey = null;
          this.loadCart();
          this.loadProducts();
        } else if (order.payment_state === 'manual_review' || order.fulfillment_state === 'manual_review') {
          clearInterval(this.paymentPoll);
          this.paymentPoll = null;
        }
      } catch (err) {
        if (showError) showToast(err.message, 'error');
      }
    },

    async simulateCash(centavos, source) {
      if (!this.activeOrder?.order_ref) return;
      try {
        const order = await api(`/checkout/api/orders/${encodeURIComponent(this.activeOrder.order_ref)}/cash/simulate`, {
          method: 'POST',
          body: JSON.stringify({ centavos, source }),
        });
        this.activeOrder = order;
        this.renderHardwarePayment(order);
        await this.pollHardwarePayment(false);
      } catch (err) {
        showToast(err.message, 'error');
      }
    },

    async cancelHardwarePayment() {
      if (!this.activeOrder?.order_ref) return;
      try {
        await api(`/checkout/api/orders/${encodeURIComponent(this.activeOrder.order_ref)}/cash/cancel`, { method: 'POST' });
        clearInterval(this.paymentPoll);
        this.paymentPoll = null;
        closeModal('hardwarePaymentModal');
        this.activeOrder = null;
        this.checkoutKey = null;
        this.loadProducts();
        showToast('Cash payment cancelled; no stock was deducted.', 'info');
      } catch (err) {
        showToast(err.message, 'error');
      }
    },

    showReceipt(txn) {
      const el = document.getElementById('receiptContent');
      if (!el) return;

      const order = txn.order || txn;
      const receiptItems = order.items || [];

      const now = new Date();
      const dateStr = now.toLocaleDateString('en-PH', { year: 'numeric', month: 'long', day: 'numeric' });
      const timeStr = now.toLocaleTimeString('en-PH', { hour: '2-digit', minute: '2-digit' });

      el.innerHTML = `
        <div class="receipt-header">
          <h4>MENDO VENDO</h4>
          <p>OTC Medicine Vending System</p>
          <p class="receipt-date">${dateStr} ${timeStr}</p>
          <p class="receipt-ref">Ref: ${order.transaction_ref || txn.transaction_ref || order.order_ref}</p>
        </div>
        <div class="receipt-divider"></div>
        <table class="receipt-items">
          <thead><tr><th>Item</th><th>Qty</th><th>Price</th><th>Subtotal</th></tr></thead>
          <tbody>
            ${receiptItems.map(i => `
              <tr>
                <td>${i.brand}</td>
                <td class="text-center">${i.quantity_ordered || i.quantity}</td>
                <td class="text-right">${fmt(i.unit_price)}</td>
                <td class="text-right">${fmt(i.subtotal)}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
        <div class="receipt-divider"></div>
        <div class="receipt-totals">
          <div class="receipt-total-row">
            <span>Total</span><strong>${fmt(order.amount_due || order.total_amount)}</strong>
          </div>
          <div class="receipt-total-row">
            <span>Inserted</span><span>${fmt(order.received_cash || 0)}</span>
          </div>
          <div class="receipt-total-row receipt-change">
            <span>Overpayment (no change)</span><strong>${fmt(order.overpayment || 0)}</strong>
          </div>
        </div>
        <div class="receipt-divider"></div>
        <p class="receipt-footer">Payment recorded · inventory updated<br>No medicine motor was activated in this test.</p>
      `;
      openModal('receiptModal');
    },
  };


  // ═══════════════════════════════════════════════
  //  INVENTORY MODULE
  // ═══════════════════════════════════════════════

  const inventory = {
    _restockId: 0,
    _adjustId: 0,

    init() {
      document.getElementById('restockSubmit')?.addEventListener('click', () => this.submitRestock());
      document.getElementById('adjustSubmit')?.addEventListener('click', () => this.submitAdjust());
    },

    filter(q) {
      const term = q.toLowerCase().trim();
      document.querySelectorAll('#invTable tbody tr[data-id]').forEach(row => {
        const search = row.dataset.search || '';
        row.style.display = search.includes(term) ? '' : 'none';
      });
    },

    openRestock(id, brand, current) {
      this._restockId = id;
      document.getElementById('restockBrand').textContent = brand;
      document.getElementById('restockCurrent').textContent = current;
      document.getElementById('restockQty').value = 10;
      openModal('restockModal');
    },

    async submitRestock() {
      const qty = parseInt(document.getElementById('restockQty').value) || 0;
      if (qty <= 0) {
        showToast('Enter a positive quantity', 'warning');
        return;
      }
      try {
        const data = await api(`/admin/api/inventory/${this._restockId}/restock`, {
          method: 'POST',
          body: JSON.stringify({ quantity: qty }),
        });
        closeModal('restockModal');
        showToast(`Restocked ${data.brand}: +${qty} units (now ${data.new_quantity})`, 'success');
        setTimeout(() => location.reload(), 800);
      } catch (err) {
        showToast(err.message, 'error');
      }
    },

    openAdjust(id, brand, current) {
      this._adjustId = id;
      document.getElementById('adjustBrand').textContent = brand;
      document.getElementById('adjustCurrent').textContent = current;
      document.getElementById('adjustQty').value = current;
      document.getElementById('adjustReason').value = '';
      openModal('adjustModal');
    },

    async submitAdjust() {
      const qty = parseInt(document.getElementById('adjustQty').value);
      const reason = document.getElementById('adjustReason').value.trim() || 'Manual adjustment';
      if (isNaN(qty) || qty < 0) {
        showToast('Enter a valid quantity (0 or more)', 'warning');
        return;
      }
      try {
        const data = await api(`/admin/api/inventory/${this._adjustId}/adjust`, {
          method: 'POST',
          body: JSON.stringify({ quantity: qty, reason }),
        });
        closeModal('adjustModal');
        showToast(`Stock adjusted for ${data.brand}: now ${data.new_quantity} units`, 'success');
        setTimeout(() => location.reload(), 800);
      } catch (err) {
        showToast(err.message, 'error');
      }
    },

    async toggleActive(id, currentlyActive) {
      const action = currentlyActive ? 'deactivate' : 'activate';
      if (!confirm(`Are you sure you want to ${action} this product?`)) return;
      try {
        await api(`/admin/api/inventory/${id}/details`, {
          method: 'POST',
          body: JSON.stringify({ is_active: !currentlyActive }),
        });
        showToast(`Product ${action}d`, 'success');
        setTimeout(() => location.reload(), 600);
      } catch (err) {
        showToast(err.message, 'error');
      }
    },
  };


  // ═══════════════════════════════════════════════
  //  TRANSACTIONS MODULE
  // ═══════════════════════════════════════════════

  const transactions = {
    async viewDetail(txnId) {
      const el = document.getElementById('txnDetailContent');
      if (!el) return;
      el.innerHTML = '<p class="text-center text-muted">Loading…</p>';
      openModal('txnDetailModal');

      try {
        const txn = await api(`/admin/api/transactions/${txnId}`);
        el.innerHTML = `
          <div class="detail-grid">
            <div><span class="text-secondary">Reference</span><strong class="mono">${txn.transaction_ref}</strong></div>
            <div><span class="text-secondary">Date</span><span>${txn.created_at}</span></div>
            <div><span class="text-secondary">Status</span><span class="badge badge--${txn.status === 'completed' ? 'success' : 'danger'}">${txn.status}</span></div>
            <div><span class="text-secondary">Cashier</span><span>${txn.cashier_name || 'System'}</span></div>
          </div>
          <table class="detail-items" style="margin-top: 16px;">
            <thead><tr><th>Item</th><th>Qty</th><th>Price</th><th>Subtotal</th></tr></thead>
            <tbody>
              ${(txn.items || []).map(i => `
                <tr>
                  <td>${i.brand}</td>
                  <td>${i.quantity}</td>
                  <td>${fmt(i.unit_price)}</td>
                  <td class="font-bold">${fmt(i.subtotal)}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
          <div class="detail-totals" style="margin-top: 16px;">
            <div><span>Total</span><strong>${fmt(txn.total_amount)}</strong></div>
            <div><span>Tendered</span><span>${fmt(txn.amount_tendered)}</span></div>
            <div><span>Change</span><span>${fmt(txn.change_amount)}</span></div>
          </div>
        `;
      } catch (err) {
        el.innerHTML = `<p class="text-center text-danger">Error: ${err.message}</p>`;
      }
    },

    async voidTxn(txnId, ref) {
      if (!confirm(`Void transaction ${ref}? This will restore stock quantities.`)) return;
      try {
        await api(`/admin/api/transactions/${txnId}/void`, { method: 'POST' });
        showToast(`Transaction ${ref} voided`, 'success');
        setTimeout(() => location.reload(), 800);
      } catch (err) {
        showToast(err.message, 'error');
      }
    },
  };


  // ═══════════════════════════════════════════════
  //  USERS MODULE
  // ═══════════════════════════════════════════════

  const users = {
    _changePassId: 0,

    init() {
      document.getElementById('createUserSubmit')?.addEventListener('click', () => this.createUser());
      document.getElementById('changePassSubmit')?.addEventListener('click', () => this.submitChangePassword());
    },

    async createUser() {
      const fullName = document.getElementById('newFullName')?.value.trim();
      const username = document.getElementById('newUsername')?.value.trim();
      const password = document.getElementById('newPassword')?.value;
      const role = document.getElementById('newRole')?.value || 'staff';

      if (!fullName || !username || !password) {
        showToast('All fields are required', 'warning');
        return;
      }
      if (password.length < 6) {
        showToast('Password must be at least 6 characters', 'warning');
        return;
      }

      try {
        const data = await api('/admin/api/users', {
          method: 'POST',
          body: JSON.stringify({ full_name: fullName, username, password, role }),
        });
        closeModal('createUserModal');
        showToast(data.message || 'User created', 'success');
        setTimeout(() => location.reload(), 800);
      } catch (err) {
        showToast(err.message, 'error');
      }
    },

    openChangePassword(uid, name) {
      this._changePassId = uid;
      document.getElementById('changePassName').textContent = name;
      document.getElementById('changePassInput').value = '';
      openModal('changePassModal');
    },

    async submitChangePassword() {
      const password = document.getElementById('changePassInput')?.value;
      if (!password || password.length < 6) {
        showToast('Password must be at least 6 characters', 'warning');
        return;
      }
      try {
        const data = await api(`/admin/api/users/${this._changePassId}/password`, {
          method: 'POST',
          body: JSON.stringify({ password }),
        });
        closeModal('changePassModal');
        showToast(data.message || 'Password updated', 'success');
      } catch (err) {
        showToast(err.message, 'error');
      }
    },

    async toggleActive(uid, name, currentlyActive) {
      const action = currentlyActive ? 'deactivate' : 'activate';
      if (!confirm(`${action.charAt(0).toUpperCase() + action.slice(1)} user "${name}"?`)) return;
      try {
        await api(`/admin/api/users/${uid}/toggle`, { method: 'POST' });
        showToast(`User ${action}d`, 'success');
        setTimeout(() => location.reload(), 800);
      } catch (err) {
        showToast(err.message, 'error');
      }
    },
  };


  // ─── Public API ────────────────────────────────

  return {
    showToast,
    openModal,
    closeModal,
    shop,
    inventory,
    transactions,
    users,
  };

})();
