// Verify actual template handlers for consent, language changes and follow-ups.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('web/templates/pos/consultation.html', 'utf8');
for (const script of source.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)) {
  new vm.Script(script[1]);
}
function extract(start, end = '\n  };') {
  const a = source.indexOf(start);
  const b = source.indexOf(end, a);
  assert(a >= 0 && b >= 0, start);
  return source.slice(a, b + end.length);
}
const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    const classes = new Set(['hidden']);
    elements.set(id, { checked: false, disabled: false, textContent: '',
      classList: { add: x => classes.add(x), remove: x => classes.delete(x), contains: x => classes.has(x) },
      focus() {}, scrollTop: 100 });
  }
  return elements.get(id);
}
const ctx = vm.createContext({ document: { getElementById: element,
  querySelector: element, querySelectorAll: () => [] },
  selectedLanguage: 'en', selectedHeadacheLocation: null,
  openModal: id => element(id).classList.remove('hidden'),
  enterKioskFlow: () => { ctx.entered = true; },
});
ctx.window = ctx;
vm.runInContext(source.slice(source.indexOf('  const CONSENT_COPY ='), source.indexOf('  window.backToHome =')), ctx);
vm.runInContext(extract('  window.selectHeadacheType ='), ctx);
async function run() {
  for (const [language, proceed] of [['en', 'Proceed'], ['tl', 'Magpatuloy'], ['ceb', 'Padayon']]) {
    ctx.selectedLanguage = language;
    element('researchConsentCheck').checked = true;
    ctx.startKiosk();
    assert.equal(element('researchConsentCheck').checked, false, 'Every new consultation starts with logging off');
    assert.equal(element('consentProceed').textContent, proceed);
    assert(element('consentPrivacyTitle').textContent.includes('RA 10173'));
    assert(element('consentLawTitle').textContent.includes('RA 7581'));
    assert(element('consentResearch').textContent.length > 50);
  }
  assert.equal((source.match(/id="consentProceed"/g) || []).length, 1);
  assert(!source.includes('id="consentYes"') && !source.includes('id="consentNo"'));
  for (const consent of [false, true]) {
    ctx.entered = false;
    ctx.fetch = async (url, options) => {
      assert.equal(url, '/consult/api/research-consent');
      assert.equal(JSON.parse(options.body).consent, consent);
      assert(element('consentProceed').disabled && element('researchConsentCheck').disabled);
      return { ok: true };
    };
    await ctx.saveResearchConsent(consent);
    assert(ctx.entered, 'Both choices allow consultation');
    assert(!element('consentProceed').disabled);
  }
  ctx.entered = false;
  ctx.fetch = async () => ({ ok: false });
  await ctx.saveResearchConsent(true);
  assert(!ctx.entered && !element('consentError').classList.contains('hidden'));
  assert(!element('consentProceed').disabled && !element('researchConsentCheck').disabled);
  ctx.selectHeadacheType('tension');
  assert.equal(ctx.selectedHeadacheLocation, 'tension');
  assert.equal(element('confirmHeadLocFooter').disabled, false);
  assert(!source.includes('headacheDetailSidebar'));
  const clarify = source.slice(source.indexOf("    if (rec.action === 'ask_clarify')"), source.indexOf("    if (rec.action === 'no_match')"));
  assert(!clarify.includes("getElementById('exitBtn')"));
  assert(!clarify.includes("getElementById('assessAgainBtn')"));
  console.log('PASS: script syntax, translated consent, both logging choices, retry, headache selection and follow-up controls');
}
run().catch(error => { console.error(error); process.exitCode = 1; });
