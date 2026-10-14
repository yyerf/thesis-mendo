// Exercise the actual template functions with a small DOM and HTTP test double.
const { readFileSync } = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = readFileSync('web/templates/pos/consultation.html', 'utf8');
function extract(marker, closing = '\n  }') {
  const start = source.indexOf(marker);
  assert(start >= 0, marker);
  const end = source.indexOf(closing, start);
  assert(end >= 0, marker);
  return source.slice(start, end + closing.length) + (closing.endsWith(';') ? '' : '\n');
}
const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    const classes = new Set(['hidden']);
    elements.set(id, { innerHTML: '', childNodes: [{ textContent: '' }],
      classList: { add: c => classes.add(c), remove: c => classes.delete(c), contains: c => classes.has(c) } });
  }
  return elements.get(id);
}
const ctx = vm.createContext({
  document: { getElementById: element },
  completeLoadingProgress() {}, setTapReadyState() {},
  t: key => key, renderSummaryCard: () => '<div>Detected diarrhea</div>',
  getSymptomLabel: s => s, getClarifyQuestionText: () => 'Diarrhea question',
  getOptionIconClass: () => '', getContextOptionLabel: (_, s) => s,
  getContextOptionDesc: () => '', renderNoMatchCard: () => 'no symptoms',
  showToast: message => { throw Error(message); },
  analysisData: null, showingRecs: false, patientAge: 25, severity: 3, severityMap: {}, selectedLanguage: 'en',
  DURATION_SYMPTOMS: ['DIARRHEA'], durationQueue: [], durationCompleted: [],
  durationContextOverride: null, durationClarificationData: {}, durationBySymptom: {},
  askNextDuration() { ctx.durationAsked = true; },
});
ctx.window = ctx;
for (const marker of ['  function escHtml(', '  function renderRecommendations(',
                      '  function renderAnalysis(', '  function startDurationFlow(']) {
  vm.runInContext(extract(marker), ctx);
}
vm.runInContext(extract('  window.handleContextClarify = ', '\n  };'), ctx);
vm.runInContext(extract('  window.handleDurationAnswer = ', '\n  };'), ctx);
async function run() {
  ctx.analysisData = { symptoms: ['DIARRHEA'], recommendation: {
    action: 'no_match', recommendations: [], message: 'Consult a pharmacist.',
    safety_warnings: ['Use oral rehydration. <unsafe markup>'],
  }};
  element('viewRecsBtn').classList.remove('hidden');
  ctx.renderAnalysis(ctx.analysisData);
  assert(element('analysisResult').innerHTML.includes('Consult a pharmacist.'));
  assert(element('analysisResult').innerHTML.includes('oral rehydration'));
  assert(element('analysisResult').innerHTML.includes('&lt;unsafe markup&gt;'));
  assert(element('viewRecsBtn').classList.contains('hidden'));
  assert(!element('assessAgainBtn').classList.contains('hidden'));
  assert(!element('exitBtn').classList.contains('hidden'));
  assert.equal(ctx.showingRecs, false, 'Back must return to assessment rather than re-render the same advisory');

  const answer = 'DIARRHEA_NON_INFECTIOUS';
  ctx.analysisData = { symptoms: ['DIARRHEA'], recommendation: { action: 'ask_clarify' } };
  ctx.fetch = async () => ({ ok: true, json: async () => ({
    symptoms: ['DIARRHEA'], symptoms_display: ['DIARRHEA_NON_INFECTIOUS_CONTEXT'],
    recommendation: { action: 'recommend', recommendations: [{ brand: 'Loperamide' }] },
  }) });
  await ctx.handleContextClarify(answer, 'DIARRHEA_CONTEXT');
  assert.equal(ctx.durationContextOverride, answer);
  assert.equal(ctx.durationClarificationData.clarification, answer);
  assert(ctx.durationAsked);
  assert(element('assessAgainBtn').classList.contains('hidden'));
  assert(element('exitBtn').classList.contains('hidden'));

  ctx.fetch = async (url, options) => {
    assert.equal(url, '/consult/api/duration-check');
    const payload = JSON.parse(options.body);
    assert.equal(payload.context_override, answer);
    assert.equal(payload.clarification_data.clarification, answer);
    assert.deepEqual(payload.pending_durations, []);
    return { ok: true, json: async () => ({ safe: true, proceed: true,
      symptoms: ['DIARRHEA'], symptoms_display: ['DIARRHEA_NON_INFECTIOUS_CONTEXT'],
      recommendation: { action: 'recommend', recommendations: [{ brand: 'Loperamide' }] },
    }) };
  };
  await ctx.handleDurationAnswer('DIARRHEA', '1');
  assert.equal(ctx.analysisData._durationDone, true);
  assert(!element('viewRecsBtn').classList.contains('hidden'));
  assert(element('assessAgainBtn').classList.contains('hidden'));
  console.log('PASS: no-medicine advice, safe escaping, duration context and proceed button');
}
run().catch(error => { console.error(error); process.exitCode = 1; });
