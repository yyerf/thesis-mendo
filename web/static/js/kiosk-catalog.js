/* Public catalog: direct cart actions and separate product information. */
(function () {
  'use strict';
  let products = [], selected = null, age = null, adding = false;
  const el = id => document.getElementById(id);
  const text = key => window.kioskText(key);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const price = value => '₱' + (Number(value || 0) / 100).toFixed(2);
  const phrase = value => window.MendoI18n.phrase(value, window.getKioskLanguage());
  async function request(url, options) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || text('tryAgain'));
    return data;
  }
  function eligible(p) { return p.purchasable && age != null && age >= p.minimum_age; }
  window.startCatalogForAge = async function (value) {
    await request('/consult/api/catalog-age', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({age:value})});
    age = value;
    await window.showMedicineCatalog();
  };
  window.showMedicineCatalog = async function () {
    el('catalogScreen').classList.remove('hidden');
    el('catalogGrid').textContent = text('pleaseWait');
    el('catalogSearch').value = '';
    el('catalogNotice').textContent = '';
    try {
      products = (await request('/consult/api/catalog')).products;
      renderMedicineCatalog();
      await window.refreshKioskCart();
    } catch (_) {
      el('catalogGrid').innerHTML = `<p role="alert">${esc(text('tryAgain'))}</p><button class="btn" onclick="showMedicineCatalog()">${text('retry')}</button>`;
    }
  };
  window.renderMedicineCatalog = function () {
    const query = el('catalogSearch').value.toLowerCase().trim();
    const visible = products.filter(p => [p.brand,p.generic_name,p.category].join(' ').toLowerCase().includes(query));
    el('catalogGrid').innerHTML = visible.map(p => `<article class="medicine-tile"><div class="medicine-photo"><img src="${esc(p.image)}" alt="${esc(p.brand)} product reference" loading="lazy"></div><div class="medicine-tile-body"><strong>${esc(p.brand)}</strong><span class="generic">${esc(p.generic_name)}</span><div class="tile-purchase-info"><span class="tile-price">${price(p.price_centavos)}</span><span class="stock-tag ${p.purchasable ? '' : 'unavailable'}">${p.purchasable ? `${p.available_quantity} ${text('inStock')}` : text(p.is_supplement ? 'unavailable' : 'outOfStock')}</span></div>${p.purchasable && !eligible(p) ? `<p class="age-limit-note">${text('minimumAge')}: ${p.minimum_age}</p>` : ''}<div class="tile-actions"><button class="btn btn--primary tile-add" onclick="catalogAddItem(${p.id})" ${!eligible(p) || adding ? 'disabled' : ''}>${text('addToCart')}</button><button class="tile-info" onclick="openMedicineDetail(${p.id})" aria-label="${esc(text('productInfo'))}: ${esc(p.brand)}" title="${esc(text('productInfo'))}"><svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7v1"/></svg></button></div></div></article>`).join('') || `<p>${text('noProductsFound')}</p>`;
  };
  window.openMedicineDetail = function (id) {
    selected = products.find(p => p.id === id);
    if (!selected) return;
    renderDetail();
    el('medicineDetailModal').classList.remove('hidden');
  };
  function renderDetail() {
    const p = selected;
    if (!p) return;
    const list = values => (values || []).map(v => `<li>${esc(phrase(v))}</li>`).join('');
    el('medicineDetailBody').innerHTML = `<div class="medicine-detail-top"><img src="${esc(p.image)}" alt="${esc(p.brand)} product reference"><div><h2 id="medicineDetailTitle">${esc(p.brand)}</h2><p>${esc(p.generic_name)}</p><div class="detail-meta"><span>${esc(phrase(p.dosage_form))}</span><span>${price(p.price_centavos)} ${text('perUnit')}</span><span>${p.available_quantity} ${text('inStock')}</span>${p.minimum_age ? `<span>${text('minimumAge')}: ${p.minimum_age}</span>` : ''}</div></div></div><p>${esc(phrase(p.description))}</p><h4>${text('uses')}</h4><ul>${list(p.indications)}</ul><h4>${text('instructions')}</h4><p>${text('catalogInstructions')}</p><h4>${text('warnings')}</h4><ul>${list(p.warnings)}</ul>${p.contraindications.length ? `<h4>${text('askPharmacistIf')}</h4><ul>${list(p.contraindications)}</ul>` : ''}<p>${text('productPhotoNote')}</p>`;
  }
  window.catalogAddItem = async function (id) {
    const p = products.find(product => product.id === id);
    if (adding || !p) return;
    if (!eligible(p)) { el('catalogNotice').textContent = text('ageNotSuitable'); return; }
    adding = true;
    el('catalogNotice').textContent = '';
    renderMedicineCatalog();
    try {
      await request('/checkout/api/cart/add', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({brand:p.brand,quantity:1})});
      await window.refreshKioskCart();
      el('catalogNotice').textContent = p.brand + ' ' + text('cartAdded');
    } catch (error) { el('catalogNotice').textContent = phrase(error.message); }
    finally { adding = false; renderMedicineCatalog(); }
  };
  window.refreshMedicineCatalogLanguage = function () {
    if (!el('catalogScreen').classList.contains('hidden')) renderMedicineCatalog();
    if (!el('medicineDetailModal').classList.contains('hidden')) renderDetail();
  };
  window.resetMedicineCatalog = function () { age = null; selected = null; products = []; adding = false; };
})();
