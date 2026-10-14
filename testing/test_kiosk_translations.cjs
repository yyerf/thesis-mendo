const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('web/templates/pos/consultation.html', 'utf8');
const translations = fs.readFileSync('web/static/js/kiosk-translations.js', 'utf8');
const checkoutSource = fs.readFileSync('web/static/js/kiosk-checkout.js', 'utf8');
const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    const classes = new Set(['hidden']);
    const el = { value: '7', dataset: {}, childNodes: [{ textContent: '' }],
      classList: { add: x => classes.add(x), remove: x => classes.delete(x),
        contains: x => classes.has(x), toggle(x, on) { on ? classes.add(x) : classes.delete(x); } },
      querySelectorAll: () => [], _nodes: [],
    };
    Object.defineProperty(el, 'innerHTML', { set(html) {
      this._html = html;
      this._nodes = [...html.matchAll(/>([^<>]+)</g)].map(m => ({ nodeValue: m[1] }));
    }, get() { return this._html || ''; } });
    Object.defineProperty(el, 'textContent', { set(text) { this._nodes = [{ nodeValue: text }]; },
      get() { return this._nodes.map(n => n.nodeValue).join(' '); } });
    elements.set(id, el);
  }
  return elements.get(id);
}
const staticCopy = [...source.matchAll(/data-i18n="([^"]+)"/g)].map(m => ({ dataset: { i18n: m[1] } }));
const ctx = vm.createContext({ selectedLanguage: 'en', languagePickedExplicitly: false,
  currentStep: 0, analysisData: null, recognition: null, severityQueue: [],
  symptomInput: element('symptomInput'), symptomTitleEl: element('symptomTitle'),
  document: { getElementById: element, documentElement: {},
    querySelector: element,
    querySelectorAll: selector => selector === '[data-i18n]' ? staticCopy : [],
    createTreeWalker(root) { let i = 0; return { nextNode: () => root._nodes[i++] }; },
  }, updatePain() {}, renderResearchConsentCopy() {},
  renderSeveritySlider(symptom, value) { ctx.sliderValue = value; },
  renderAnalysis() { ctx.analysisRendered = true; },
  renderDurationQuestion() {}, renderRecommendations() {}, runAnalysis() {},
});
ctx.window = ctx;
vm.runInContext(translations, ctx);
function extract(marker, ending = '\n  };') {
  const a = source.indexOf(marker), b = source.indexOf(ending, a);
  assert(a >= 0 && b >= 0, marker);
  return source.slice(a, b + ending.length);
}
vm.runInContext(source.slice(source.indexOf('  const UI_COPY ='), source.indexOf('  function clearIdleTimers()')), ctx);
for (const marker of ['  function getSpeechRecognitionLocale(', '  function askNextSeverity(']) {
  vm.runInContext(extract(marker, '\n  }'), ctx);
}
for (const marker of ['  window.setLanguage =', '  window.pickLanguage =', '  window.handleLanguageSelectChange =']) {
  vm.runInContext(extract(marker), ctx);
}
ctx.syncInputLanguage('sakit akong ulo ug naa koy hilanat');
assert.equal(ctx.selectedLanguage, 'ceb');
assert.equal(element('symptomTitle').textContent, 'Unsa imong gibati?');
assert.equal(ctx.document.documentElement.lang, 'ceb');
assert(staticCopy.find(el => el.dataset.i18n === 'back').textContent === 'Balik');
assert(staticCopy.find(el => el.dataset.i18n === 'detecting').textContent.includes('Gisusi'));
for (const input of ['naa koy ubo', 'naglabad akong ulo', 'gikapoy ko', 'kalibanga']) {
  ctx.selectedLanguage = 'en';
  assert.equal(ctx.detectLanguageFromText(input), 'ceb', input);
}
ctx.syncInputLanguage('masakit ang ulo ko');
assert.equal(ctx.selectedLanguage, 'tl');
ctx.syncInputLanguage('maybe I have a headache');
assert.equal(ctx.selectedLanguage, 'en', 'may must not match inside maybe');
ctx.pickLanguage('ceb');
ctx.syncInputLanguage('I have a headache and a fever');
assert.equal(ctx.selectedLanguage, 'ceb', 'Explicit home selection wins over input language');
ctx.pickLanguage('en');
ctx.syncInputLanguage('sakit akong ulo ug naa koy hilanat');
assert.equal(ctx.selectedLanguage, 'en');
ctx.handleLanguageSelectChange('tl');
ctx.syncInputLanguage('naa koy ubo');
assert.equal(ctx.selectedLanguage, 'tl', 'Modal/dropdown selections are explicit too');
ctx.pickLanguage('invalid');
assert.equal(ctx.selectedLanguage, 'tl');
ctx.pickLanguage('auto');
ctx.syncInputLanguage('naa koy ubo');
assert.equal(ctx.selectedLanguage, 'ceb', 'Auto can be restored after an explicit language choice');
ctx.currentStep = 3;
ctx.severityQueue = ['HEADACHE'];
ctx.severityHints = {}; ctx.severityMap = {};
ctx.pickLanguage('ceb');
assert.equal(ctx.sliderValue, 7, 'Changing language keeps the current pain rating');
assert.equal(ctx.severityQueue.length, 1);
assert.equal(ctx.getClarifyQuestionText('RASHES_BREATHING', 'English backend question'), 'Lisod usab ang imong pagginhawa?');
assert.equal(ctx.getContextOptionLabel('RASHES_BREATHING_YES', 'Yes / Breathing difficulty'), 'Oo, lisod pagginhawa');
assert.equal(ctx.MendoI18n.flag({ flag: 'chest_pain', message: 'English warning' }, 'ceb'), 'Sakit o paghuot sa dughan');
assert(ctx.MendoI18n.flag({ flag: 'headache_location', message: '', message_ceb: '' }, 'ceb').includes('Kinahanglan ipasusi'));
const foodWarning = ctx.MendoI18n.notice('⚠ Possible food poisoning or infection suspected.', 'ceb');
assert(foodWarning.includes('Dili girekomenda ang loperamide') && foodWarning.includes('oral rehydration') && foodWarning.includes('dugo sa tae'));
assert.equal(ctx.MendoI18n.product('pain & fever', 'ceb'), 'Kasakit ug hilanat');
for (const values of Object.values(ctx.MendoI18n.ui)) assert(values.length === 3 && values.every(Boolean));
for (const el of staticCopy) assert.notEqual(ctx.t(el.dataset.i18n), el.dataset.i18n, el.dataset.i18n);
// Run the real checkout renderer and translator for cart/payment/receipt states.
Object.assign(ctx, { cart: [], step: 1, selectedPayment: 'cash', noChange: false,
  cashStartPending: false, el: element, esc: String, money: n => '₱' + (n / 100).toFixed(2),
  getKioskLanguage: () => ctx.selectedLanguage,
});
vm.runInContext(checkoutSource.slice(checkoutSource.indexOf('  function stepDots()'), checkoutSource.indexOf('  async function createOrder(')), ctx);
ctx.render();
assert.equal(element('checkoutTitle').textContent, 'Imong cart');
assert(element('checkoutBody').textContent.includes('Walay sulod ang cart'));
ctx.step = 2; ctx.render();
assert.equal(element('checkoutTitle').textContent, 'Pagbayad');
assert(element('checkoutBody').textContent.includes('Walay ihatag nga sukli'));
ctx.step = 3; ctx._mendoOrder = { amount_due_centavos: 1000 }; ctx.render();
assert(element('checkoutBody').textContent.includes('Isulod ang imong kuwarta'));
ctx.step = 4; ctx._mendoOrder = { payment_state: 'manual_review' }; ctx.render();
assert(element('checkoutBody').textContent.includes('Ayaw na pagsulod og kuwarta'));
ctx.selectedLanguage = 'en'; ctx.render();
assert.equal(element('checkoutTitle').textContent, 'Staff review required');
for (const script of [translations, checkoutSource]) new vm.Script(script);
console.log('PASS: typed language detection, strict selections, static copy, rash prompts, safety notices, retained pain rating and checkout translations');
