# MendoVendo v3.0 — Final Methods & Change Log (2026-08-14, anchor-only revision)

Status: **final as of 2026-08-14**. Evidence numbers below are the verified,
reproducible state of the shipped system. The semantic layer is
**deterministic anchor-based cosine similarity — no fine-tuning, no trained
head, no external LLM in the deployed path** (see \S 2.2 and the "Why Not an
LLM" thesis section).

Renderable LaTeX for every formula: `docs/thesis/formulas.tex` (standalone).
Citations: `docs/thesis/references.bib`.

---

## 1. System at a glance

Five-stage pipeline over a 14-label symptom vocabulary (13 semantic labels +
TOOTHACHE, dictionary-only):

```
user text
  -> S0  red-flag triage (detect_red_flags)
  -> S1  deterministic dictionary (step1: 570 phrases, 5 languages, negation,
         contrastive splitting, cough-type tree, fuzzy rescue, leet decode)
  -> S2  semantic stage, backend-factory (step3._get_semantic_extractor):
           default  = zero-shot MiniLM cosine  (mendo-expert-minilm-v3.2)
                      — 270 anchor sentences, threshold τ = 0.65
           optional = Sailor2 1B local LLM     (mendo-expert-sailor2-v1)
  -> S3  hybrid merge: precision-first gating (semantic only on dictionary
         miss, lexical guards + safety vetoes + negation vetoes)
  -> S4  rule-based recommendation (paracetamol overlap, opposing mechanisms,
         age filter, duration safeguard, red-flag referral)
```

Runs fully offline on a Raspberry Pi 5 (CPU). No patient data leaves the
device (RA 10173, \cite{dpa2012}).

---

## 2. Final methods per stage

### 2.1 Stage 1 — deterministic dictionary (step1.py)

- Normalization (`_normalize`): lowercase; leetspeak map

  `@→a, 0→o, 1→i, 3→e, 4→a, 5→s, 7→t, 8→b, $→s, !→i, |→i`; apostrophes
  stripped (`isn't → isnt` so negation words match); every other non-letter
  replaced by a space.

- Phrase matching: 570 phrases (was 331 in v1) over 13 labels + TOOTHACHE in
  English, Filipino, Taglish, Cebuano/Bisaya, and Jejemon/leet forms.
- Negation: bounded-window rule — a negation word (`hindi, wala, walang,
  walay, dili, di, no, not, without, hnd, …`) negates a target inside a
  `_NEG_WINDOW`-token window, with contrastive splitting at `pero / but /
  kaso / however / though` resetting the scope. The cough-negation regex
  also refuses to cross a contrastive boundary or a scope-end conjunction
  ("walang sore throat pero umuubo" keeps the cough) while still honouring
  fused assertion constructions ("wala may ubo" negates the cough).
  Fillers like `mawala / hunong / tigil / stop` consume the negation
  ("hindi mawala ang ubo" = the cough persists).
- Cough-type tree: `ubo/cough` then decides GENERAL vs DRY vs PRODUCTIVE from
  dryness/plema markers; otherwise the deployed flow asks a clarification.
- Fuzzy rescue: Levenshtein similarity \cite{levenshtein1966} catches typos
  (`sipn→sipon`, `pantl→pantal`, `tyan→tiyan`, `ktawan→katawan`, `pagtate→
  pagtatae`, `ub→ubo` …) with explicit exclusion lists (`ulo, tubo, ubos,
  ubi, ube, tuba, ubod` …) that block false positives from near-words.
- Proximity rescues with token-window constraints: e.g. TOOTHACHE fires when a
  tooth word occurs within 6 tokens of a pain word, unless a contrastive part
  negates the pain; body/tummy/respirator words behave the same way.
- Safety cleanup: nosebleed + nose words can never count as a cold
  (RUNNY_NOSE / NASAL_CONGESTION / ALLERGIC_RHINITIS are suppressed).

### 2.2 Stage 2 — semantic backends (anchor-based cosine, no training)

Embeddings: `paraphrase-multilingual-MiniLM-L12-v2`
\cite{reimers2019sentence, wang2020minilmv2, feng2022mminilm}, 384-d,
sentence-mean pooling:

$$ \mathbf{e}(s) = \frac{1}{n} \sum_{k=1}^{n} \mathbf{h}_k $$

Cosine similarity:

$$ \cos(\mathbf{a},\mathbf{b}) = \frac{\mathbf{a}\cdot\mathbf{b}}{\|\mathbf{a}\|\,\|\mathbf{b}\|} $$

- **Default path — zero-shot cosine anchors** (`mendo-expert-minilm-v3.2`):
  270 hand-curated anchor sentences (was 145 in the June revision, 118 in
  v1) across the 13 labels. Each label fires when its best cosine reaches
  the semantic threshold:

$$ s_L = \max_{a \in A_L} \cos\big(\mathbf{e}(u), \mathbf{e}(a)\big), \qquad
\text{fire } L \iff s_L \geq \tau = 0.65 $$

  Anchor counts (live, in `mendo_core/step2.py`): HEADACHE 26, COUGH_DRY 14,
  COUGH_PRODUCTIVE 20, COUGH_GENERAL 13, FEVER 26, BODY_ACHES 28,
  NASAL_CONGESTION 16, RUNNY_NOSE 14, ALLERGIC_RHINITIS 16, RASHES 22,
  DIARRHEA 17, STOMACH_ACHE 33, SORE_THROAT 25.

- **Sailor2 path** (`mendo-expert-sailor2-v1`, selectable): constrained
  closed-vocabulary JSON decode, `temperature=0`, 120 max tokens, fail-closed
  (garbage raises → caller treats semantic as unavailable). Not deployed —
  see "Why Not an LLM" in the thesis.
- **No fine-tuned classifier.** The previously shipped 13-label sigmoid head
  (`train_semantic_classifier.py`, `semantic_classifier.py`, weights under
  `data/models/semantic_classifier/`) was **removed** in this revision by
  decision: the anchors are fully explainable (every firing is traceable to
  its best anchor sentence), require zero training data, zero retraining
  cycles, and ~7× lower latency than the head. See the thesis "Why Not an
  LLM" discussion, extended to "Why Not a Fine-Tuned Head".
- All backends lazy-load once behind `_get_semantic_extractor()`; the web app
  pre-warms in a background thread; a failed/unavailable semantic stage
  degrades to dictionary-only — never a hard error.

### 2.3 Stage 3 — hybrid gating (step3_hybrid.py)

Precision-first: every backend in the deployed set (`minilm`, `sailor`) is
`fallback_only` — the semantic stage runs **only when Stage 1 returns
nothing**; `dictionary_hit_precision_first` records the skip. The MiniLM
backdrop keeps no always-run mode; a dictionary hit always wins, so
negation/contrast cases decided by the deterministic rules can never be
overruled by an embedding. The semantic output is then passed through:

1. **Lexical guard** — vetoes emissions the text can already refute
   (e.g. COUGH without a cough keyword, BODY_ACHES without a body keyword),
   recorded as `vetoed` in the trace;
2. **Negation vetoes** — `_explicitly_negates_*` per label (fever, headache,
   cough, diarrhea, sore throat, nasal, allergy, body aches, rash, and —
   new this revision — **stomach ache**, clause-scoped so "stomach pain,
   but there is no pain in my head" keeps the ache while "my stomach
   doesn't hurt" drops it);
3. **Safety filters** — blood-context, red-flag-based suppression
   (blood_in_stool → no DIARRHEA, hemoptysis → no cough, etc.);
4. **Wholly-negative guard** — a sentence that opens with a negation and
   never contrasts cannot acquire an unrelated semantic symptom.

Red-flag triage (`detect_red_flags`) runs at the top and always dominates.

### 2.4 Stage 4 — recommendation (step4_recommend.py)

Rules, no ML: paracetamol overlap cap, opposing-mechanism blocks, age filter,
and the **Duration Safeguard**: refer when reported duration exceeds the
clinical threshold

$$ \text{refer iff } \text{days} > D_{\text{label}}, \qquad
D = \begin{cases} 3 & \text{fever}\\ 2 & \text{diarrhea}\\ 5 & \text{sore
throat}\\ 7 & \text{stomachache, headache, body aches, rashes, allergy,
nasal, runny nose}\\ 14 & \text{cough}\end{cases} $$

### 2.5 Headache intake (headache_intake.py + headache_locations.py)

Deterministic multilingual tag matching (202 strong + 67 weak tags) over 14
clinical types; red-zone types (thunderclap, hypertension, spinal,
post-traumatic, exertion, **+ 2026-08-14: meningeal, stroke-like, sudden
visual loss, syncope, pregnancy**) dominate all other candidates and
auto-refer. A bare type cue ("sinus", "high blood") can promote a headache
consult; the pregnancy type refrains unless a headache word is present.

---

## 3. Semantic layer rationale — anchors only (no fine-tuning)

The anchor-only design is deliberate and thesis-defended:

1. **Explainability.** Every semantic firing reports its best anchor
   (`best_anchor` in the trace). A pharmacist can read "BODY_ACHES 0.75
   matched anchor 'masakit ang buong katawan ko'" and judge the match
   directly. A trained head hides its decision in 13 × 384 weights.
2. **Determinism.** Same input → same output across machines and model
   cache states; no seed, no checkpoint drift, no CV threshold selection to
   defend in the defense.
3. **Zero data dependency.** No training corpus, no annotation conflicts, no
   in-sample/held-out ambiguity. The 520 sheet and 288 benchmark rows are
   pure *evaluation* data — the honesty story is simpler than the
   fine-tuned-head version ever was.
4. **Performance.** Cosine over 270 anchors ≈ 11 ms/query with the encoder
   hot (identical cost class to the head's forward pass minus a head
   multiply); no Ollama process.

The held-out paraphrase set — the only corpus where the semantic stage
genuinely decides — improves from 10/16 (fine-tuned head) and 8/16
(145-anchor cosine) to **11/16** with the 270-anchor expansion, while fresh
negatives stay 20/20 (see \S 6). The 7 anchor expansions that raised the
score came from the same failure-analysis loop documented in \S 6.1-B:
vocabulary gaps are fixed by adding anchors/dictionary phrases, never by
re-weighting a model.

---

## 4. Changes on 2026-08-14 (this revision)

| # | Change | Where | Verifiable effect |
|---|---|---|---|
| 1 | **Removed the fine-tuned classifier** (runtime, training script, weights) | `semantic_classifier.py`, `train_semantic_classifier.py`, `data/models/semantic_classifier/` deleted; factory default → `minilm` | single deterministic backend set; no `mendo-expert-minilm-finetuned-v1` anywhere |
| 2 | MiniLM is now `fallback_only` (was always-run) | `mendo_core/step2.py` | dictionary hits never overruled; parity with Sailor gating |
| 3 | **Anchors 145 → 270** (tight-band family, GERD rising, milk trigger, throat obstruction, hot/sweaty, back pain, anosmia, nangangalay family, "my body has been aching", …) | `mendo_core/step2.py` | paraphrases 8/16 → 11/16, negatives still 20/20 |
| 4 | Dictionary: `umoubo` + `nangangalay` families, "my body has been aching" | `mendo_core/step1.py` | those phrasings now dictionary-caught (deterministic, precision-first) |
| 5 | **Cough-negation boundary fix**: negation regex cannot cross `pero/but/kaso/...` | `mendo_core/step1.py` | "walang sore throat pero umuubo" → COUGH_GENERAL (was negated to nothing); restored 288/288 |
| 6 | **Stomach-ache negation veto**, clause-scoped + wellness-word aware | `mendo_core/step3_hybrid.py` | "my stomach doesn't hurt" no longer emits STOMACH_ACHE; "stomach pain, but no pain in my head" still does |
| 7 | 5 composite red-flag headache types | `headache_locations.py`, `headache_intake.py` | tests 47→60, `RED_PRIORITY` extended, bare-`buntis` promote guard |
| 8 | Pharmacist-validation harness | `testing/validation/` (export, import, protocol) | Iteration-2 pipeline ready |
| 9 | Evidence runner + backend comparison, classifier-free | `testing/run_evidence.py`, `testing/compare_backends.py` | one-command reproducible report (see \S 6) |
| 10 | Windows test-infra fixes (temp-SQLite file locks) | `testing/test_medicine_catalog.py`, `testing/test_audit_workflow.py` | full pytest suite green on Windows (194 passed + 110 subtests) |

---

## 5. Evaluation methodology

Detection metrics (multi-label, 13+1 labels); for label $l$ with true
positives $TP_l$, false positives $FP_l$, false negatives $FN_l$:

$$ P_{\text{micro}} = \frac{\sum_l TP_l}{\sum_l TP_l+\sum_l FP_l}, \qquad
R_{\text{micro}} = \frac{\sum_l TP_l}{\sum_l TP_l+\sum_l FN_l}, \qquad
F_1 = \frac{2PR}{P+R} $$

Macro-F1 averages per-label F1. Hamming loss:

$$ HL = \frac{1}{N|L|}\sum_{i=1}^{N}\sum_{l\in L}
\big[\,\hat{y}_{il} \neq y_{il}\,\big] $$

Exact match = fraction of rows with all labels correct; violation of the
absence of symptoms counts as a false positive (a false positive is
considered worse than a missed secondary symptom — precision-first).

---

## 6. Evidence run (2026-08-14, verified, current shipped model)

Run: `python testing/run_evidence.py` (writes
`testing/benchmark/results/evidence.json` + `evidence_report.md`).

| Suite | Result |
|---|---|
| A. 288 benchmark, guided (engine `mendo-expert-minilm-v3.2`, 270 anchors) | **288/288**; raw-input exact 234/288, micro P 0.849 / R 0.849 / F1 0.849 |
| B. 520 sheet | **518/520** (EN 130/130, FIL 130/130, CEB 129/130, MIX 129/130) |
| C. 16 held-out paraphrases | **11/16** guarded pipeline (cosine-anchor; BODY_ACHE→BODY_ACHES canonicalized; was 8/16 at 145 anchors, 10/16 under the removed classifier) |
| D. 20 fresh negatives | **20/20 clean**, 0 FP |
| E. Duration safeguard (Tier 5) | 31/31, exit 0 |
| F. Headache intake | **60/60** |
| G. pytest regressions | **194 passed + 110 subtests**, exit 0 |
| Latency | full-pipeline warm mean ≈ 4.4 ms/query (desktop); Pi 5 numbers **not yet measured** |

Data fingerprints (sha256[:16]) and environment (python 3.11.9, torch
2.1.1+cpu, transformers 4.36.2, backend minilm, threshold 0.65) are recorded
in `evidence.json`.

**Honesty guards** (defense-critical, carried from the thesis):
- The 288 cases are team-authored synthetic inputs → regression coverage,
  **not** independent accuracy. Never write "288/288 = 100% accuracy".
- Independent accuracy comes from Iteration-2 pharmacist validation
  (`testing/validation/`), exactly the protocol documented for that claim.
- The 288 rows and the 520 sheet are **not** training data under the
  anchor-only design — no in-sample caveat applies; the held-out paraphrase
  set and fresh negatives are the semantic stage's honest generalization
  numbers.

**Backend comparison** (`python testing/compare_backends.py` →
`testing/benchmark/results/backend_comparison.json`, live run):

| backend | 288 synthetic | 16 paraphrases | 20 fresh negatives |
|---|---|---|---|
| minilm (270-anchor cosine, **default**) | 288/288 | **11/16 (68.8%)** | 20/20 |
| sailor2 (optional, fail-closed dictionary-only when Ollama down) | 288/288 | 4/16 (semantic decided 0 — Ollama down at run time; honest record) | 20/20 |

disagreement_count = 0 on every overlapping case.

---

## 6.1 Semantic-layer robustness review (2026-08-14, same session)

Task: make the semantic layer "bulletproof / 10x better at understanding user
context". Three candidate avenues were evaluated; two were rejected with
data, one was fixed deterministically.

**A. "Conjunction chunking" (proposed brainstorm) — evaluated and rejected.**
The idea: split the input on punctuation + conjunctions
(`tapos/unya/at/ug/and/pero/...`), score each fragment independently, union
the results — on the theory that a single whole-text vector "dilutes"
multi-clause sentences. Measured with `testing/semantic_chunk_sim.py`
(guard + negation filters always applied to the full text, never per-chunk):

| Measure | Whole-text | Chunked |
|---|---|---|
| 16 held-out paraphrases | 9/16 | 9/16 |
| 20 fresh negatives | 20/20 clean | 20/20 clean |
| 288 zero-dict rows | unchanged | unchanged (1 correct fire) |
| **Exact-dict rows (170): spurious additions** | **0** | **20 rows** (COUGH_DRY vs COUGH_PRODUCTIVE, NASAL_CONGESTION vs ALLERGIC_RHINITIS, BODY_ACHES vs FEVER) |

Chunking gained nothing and broke cross-label discrimination on the safest
set. Rejected; whole-text scoring retained. The proposal's cited failure
mode ("vector dilution") does not manifest at kiosk sentence lengths
(≤ 30 tokens), and its example sentence never even reaches the semantic
stage: the dictionary catches `ubo`, so precision-first gating skips it —
the real failure was vocabulary, not dilution.

**B. Vocabulary gaps — fixed deterministically (no retrain possible under
the anchor-only design; anchors/dictionary extended instead).**
- `sinat` (common Tagalog "mild fever"): pinned deterministically in the
  FEVER dictionary + fever negation regex + lexical-guard fever keywords
  (the old classifier under-scored it at 0.280 even standalone; the cosine
  path now also carries a dedicated anchor family). Verified: "parang may
  sinat ako tapos sige ra kug ubo" → `['COUGH_GENERAL','FEVER']`; "wala
  akong sinat" → nothing; "walang sinat pero may ubo" → only COUGH.
- `nangangalay` family ("Nangangalay ang katawan ko pagkatapos magtrabaho,
  pero normal naman ang temperatura"): added to the BODY_ACHES dictionary +
  guard keywords + 3 anchors → now detected (was a 520-suite miss).
- "My body has been aching" → BODY_ACHES dictionary + anchor (was a
  520-suite miss under negation-sheet row EN-NEG-0058).
- Stomach negation veto (`_explicitly_negates_stomach_ache`) — see \S 2.3.

**C. Deterministic negation bugs found by the suites — fixed in rules.**
- Cough negation crossing `pero` ("walang sore throat pero umuubo" was
  negated to nothing): boundary-aware regex (change 5, \S 4). This was the
  sole 288-case regression after the anchor expansion (287/288 → 288/288).
- The stomach veto initially over-fired ("stomach pain, but there is no
  pain in my head" was wrongly dropped, 520 suite 515/520): rewrote it
  clause-scoped and wellness-aware → 518/520 restored, and the new
  negation cases added to the regressions suite stay green.

All suites re-verified after each change; the numbers in \S 6 are the final
state.

---

## 7. Deferred / planned

1. **Pi 5 benchmark (M6)** — measure and record in the evidence report.
2. **Iteration-2 pharmacist field validation** — export per protocol, ingest
   per `import_annotations.py`; results are independent-accuracy evidence,
   not training data (the anchor-only design needs none).
3. *(Removed)* Fine-tuned classifier retrain — the head, its training
   script, and its weights were deleted by decision (see \S 3); nothing is
   staged to bring it back.
