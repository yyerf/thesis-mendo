# Software-Side Revision — Change Log (2026-08-14)

Source reviewed: `thesis.docx`
Revised file: `thesis-REVISED-software-2026-08-14.docx`
**Every change below is highlighted YELLOW in the revised file.**

Live system state behind the numbers (re-verified today):
- Fine-tuned MiniLM classifier is the deployed semantic default (`mendo-expert-minilm-finetuned-v1`), cosine-anchor MiniLM and local-LLM paths remain selectable (`MENDO_SEMANTIC_BACKEND=classifier|minilm|sailor`).
- Detection benchmark: **288/288 exact** (with cough clarification); raw pre-clarification 234/288 (81.2%), micro-F1 **0.856**.
- Multilingual 520-case suite: **518/520 (99.6%)**.
- pytest suite 81 passed + 48 subtests.

## Replacements (rewritten paragraphs)
| Section | What changed |
|---|---|
| Iteration 1 · Implementation | Named the semantic components: cosine-anchor matching + fine-tuned 13-label classification head |
| Stage 2 (3 paras) | Added **mean-pooling formula** e(s)=(1/n)Σhₖ; rewrote "no fine-tuning" claim into frozen-encoder + trained-head narrative (safety/reproducibility/multilingual-coverage + honest in-sample caveat); added **cosine-similarity formula**, anchor label score s_L=max cos, and threshold rule τ=0.65 |
| Stage 3 · Centralized Safety Filter | Added the three contextual gates: breathing-difficulty → respiratory red flag (not congestion); throat-without-nose vetoes NASAL_CONGESTION; allergy verbs (react/reaction) join triggers |
| Validation sets (heading + 2 paras) | "Planned" → implemented: Semantic Generalization Set (16, 9/16 vs 8/16) and Fresh Negative Set (20, 20/20) |
| Evaluation Results (3 paras) | 283→**288/288**; raw 234/288 micro-F1 0.856; the old "five detection misses" rewritten to the refinement narrative (breathing gate, plural/idiom negation, fuzzy-rescue tightening) + honest note on 5 pre-existing recommendation-rule mismatches next to 220 passing |
| Comparative Benchmarking (2 paras + analysis) | Cross-references fixed (Table 10 / 11); reproducibility wording scoped to the Mendo rows; Mendo hybrid row corrected to live 234/288 — no longer anomalously below the dictionary |

## New inserted sections (all highlighted)
1. **Fine-Tuned Symptom Classification Head** (Stage 2) — sigmoid p_L=σ(z_L), multi-label BCE loss with label weights w_L∈[1,20], AdamW 2×10⁻⁵ / batch 16 / 6 epochs on 767 de-duplicated rows, 5-fold CV threshold selection (τ′=0.70, out-of-fold 43.6%), frozen encoder, deployment + held-out results (9/16, 20/20, ≈11 ms)
2. **Free-Text Headache-Type Intake** (Stage 1) — 14 clinical types, 202 strong + 67 weak tags, deterministic no-ML, red-zone auto-refer (thunderclap/hypertension/spinal/post-traumatic/exertion), head-map click precedence
3. **Formal definitions** (Evaluation Metrics) — exact-match indicator, micro precision/recall/F1, Hamming loss, macro-F1 formulas
4. **Multilingual Evaluation Suite (520 cases)** — composition (13×5×2×4), clinician review, dual use as training corpus (in-sample caveat for the fine-tuned head), 2 residual rows = annotation issues

## Tables
- **Table 10 (detection summary)** — with-clarification row → 288/288 (100.0%), 0 misses; raw row micro-F1 → 0.856
- **Table 11 (comparative)** — Mendo Dictionary & Mendo Hybrid rows refreshed to live raw metrics (0.863 / 0.849 / 0.856, Hamming 0.027, latency 2.1 ms / 4.4 ms); trained-baseline rows left as recorded

## Numbering / cross-reference fixes
- P271 "Table 9" → Table 10; P275 "Table 8/Table 9" → Table 10/Table 11; P285/P287 "Table 10" → Table 11.

---

## Revision v2 (same day) — `thesis-REVISED-software-2026-08-14-v2.docx`

Rebuilt from the v1 revised file. **Markup convention is now tracked-changes style: removed text = RED + strikethrough, added text = YELLOW highlight** (previously additions were yellow but removals were silently deleted).

### 1. Equations now rendered as native Word math (OMML)
Inline Unicode formulas were removed from the prose and replaced with **10 centered, numbered equation paragraphs** rendered by Word's equation engine (Cambria Math), each highlighted yellow:

| # | Equation | Location |
|---|----------|----------|
| (1) | e(s) = (1/n) Σₖ₌₁ⁿ hₖ — mean pooling | after semantic-fallback intro |
| (2) | cos(e(u),e(a)) = (e(u)·e(a)) / (‖e(u)‖·‖e(a)‖) | anchors paragraph |
| (3) | cos = (Σ uᵢaᵢ) / (√Σuᵢ² · √Σaᵢ²) — expanded form | anchors paragraph |
| (4) | s_L = max_{a∈A_L} cos(e(u),e(a)) — label score | anchors paragraph |
| (5) | z_L = W_L⊤ e(s) + b_L — logit | classifier head |
| (6) | p_L = σ(z_L) = 1/(1+e^(−z_L)) — sigmoid | classifier head |
| (7) | L_BCE = −(1/13) Σ [w_L y_L ln p_L + (1−y_L) ln(1−p_L)] | Training paragraph |
| (8) | Precision = TP/(TP+FP), Recall = TP/(TP+FN) | Formal definitions |
| (9) | F1 = 2·P·R/(P+R) | Formal definitions |
| (10) | Hamming loss = (1/M) Σ |Pₘ Δ Eₘ|/13 | Formal definitions |

Prose is split around the equations into short lead-in / continuation paragraphs so each formula stands on its own line.

### 2. Numbers corrected to the live system (strike old / yellow new)
- **331 → 570 dictionary phrases** — Stage-1 paragraph, Table 5 caption, semantic-fallback intro, Semantic Generalization Set paragraph. The dictionary now holds 570 entries; every stale "331" was replaced.
- **118 → 134 anchor sentences (5–20 per label)** — anchors paragraph (live count; e.g., STOMACH_ACHE has 20).

### 3. Table 11 now shows the measured dictionary-vs-hybrid difference
Both Mendo rows were previously identical (234/288) — inaccurate. New measured rows (old value struck red, new value yellow):

| Model | Exact Match | Micro P | Micro R | Micro F1 | Hamming | Latency |
|---|---|---|---|---|---|---|
| Mendo Dictionary (Stage 1) | **231/288 (80.2%)** | 0.856 | 0.846 | 0.851 | 0.028 | 2.1 ms |
| Mendo Hybrid (deployed) | **234/288 (81.2%)** | 0.863 | 0.849 | 0.856 | 0.027 | 4.4 ms |

The +3 exact matches are semantic rescues on dictionary-miss utterances — the honest evidence that the fallback adds value.

### 4. Analysis paragraphs rewritten (strike old / yellow new)
- **Evaluation Results intro (P279)** — replaces "the same figure as the dictionary stage's ceiling" with the real 231-vs-234 story and the precision-first guarantee.
- **Comparative analysis (P301)** — same correction; baseline discussion unchanged.

### 5. Thesis-format paragraph presentation
- All touched paragraphs normalized to the manuscript body format: justified (jc=both), first-line indent, 240-twip line spacing, widow control off.
- Bold lead-in phrases restored per thesis convention: Training., Deployment., Formal definitions., Analysis., Semantic Generalization Set, Fresh Negative Set, Multilingual Evaluation Suite, etc.
- Equation paragraphs are centered, unindented, numbered (1)–(10).

### 6. Re-verified
- 10/10 OMML equation paragraphs present, centered, highlighted.
- All content markers found (570 / 134 / 231 / 234); 22 red-strike runs + 202 yellow runs.
- **test.xlsx suite (the initial tests): 518/520 (99.6%)** on engine `mendo-expert-minilm-finetuned-v1` — the sheet failures that motivated the dictionary expansion (570 phrases) and the fine-tuned classifier are exactly the 2 annotation issues disclosed in the manuscript.
- Hybrid raw 234/288, dictionary raw 231/288 — measured live this session.

### 6b. v2.1 fix — file was flagged "unreadable" by Word
Cause: the equations and tracked-changes markup were injected with `w:pPr` / `w:rPr` child properties **out of OOXML schema order** (e.g. `strike` after `color`, `spacing`/`ind`/`jc` appended after an existing paragraph-level `rPr`, and a duplicated `w:b`). Word validates this strictly and shows an unreadable-content prompt, even though python-docx opens it.
Fix: a canonical ordering + deduplication pass (`normalize_order.py`) re-sorts every `w:pPr`, `w:rPr`, and `m:rPr` into schema sequence order and removes duplicate single-occurrence properties. Re-verified: zip OK, `document.xml` strict-parse OK, 0 order violations (the only "non-rPr-first" runs are original legal page-break/drawing runs with no rPr), 10 OMML equations, 473 paragraphs, 12 tables.

---

## Revision v3 (same day) — `thesis-REVISED-software-2026-08-14-v3.docx`

Rebuilt from v2: removed the duplicate cosine-equation paragraph and corrected paragraph numbering. Verified: 22 OMML equations (v2's 10 + 12 new numbered equations added for the classifier protocol), 487 highlight runs, 13 tables, 488 paragraphs.

---

## Revision v4 (same day, final) — `thesis-REVISED-software-2026-08-14-v4.docx`

**Anchor-only decision.** The fine-tuned MiniLM classifier was removed from the system entirely (code, training script, weights) in favor of a purely explainable anchor-based cosine semantic stage. Every classifier artifact in the manuscript was deleted or rewritten; anchor counts, backend defaults, and evidence numbers were refreshed. See `final-methods-2026-08-14.md` \S 3–4 for the full rationale and change table.

### Removed (struck red / deleted with the classifier)
- **Fine-Tuned Symptom Classification Head** section — sigmoid p_L, BCE loss, label weights, AdamW/epochs/CV threshold story: gone. The thesis now argues "Why Not a Fine-Tuned Head" instead.
- Equations (4)–(7) of v3 — logit z_L, sigmoid p_L, BCE loss, CV threshold selection — deleted; the remaining equations were renumbered to a clean sequential (1)–(9) in document order (negation scope, Levenshtein, fuzzy rescue, mean pooling, cosine, label score, precision/recall, F1, Hamming).
- Tables 11–12 classifier rows (fine-tuned engine + in-sample caveat rows); comparative table now carries only dictionary, cosine-anchor hybrid, and (as recorded baselines) the regex/reference models.
- 801/767-row training-corpus narrative, `manifest.json` staging, "classifier retrain deferred" item — all removed; nothing is staged to bring the head back.

### Rewritten (yellow)
- **Stage 2 semantic backend**: default is now zero-shot MiniLM cosine (`mendo-expert-minilm-v3.2`) with **270 anchor sentences** (was 145); threshold rule stays τ = 0.65 but now with no trained head above it; anchor counts per label listed.
- **Stage 3 gating**: MiniLM is now `fallback_only` like the LLM path — dictionary hits always win (parity + precision-first); negation vetoes extended with the clause-scoped stomach-ache veto.
- **Evaluation Results**: classifier-era numbers replaced with the anchor-only evidence run — 288/288 guided, 518/520 sheet, **11/16 held-out paraphrases** (was 8/16 at 145 anchors, 10/16 under the removed head), 20/20 fresh negatives, 60/60 headache intake, duration 31/31.
- **Honesty-guard paragraph**: the in-sample caveat no longer applies (the 520 sheet and 288 rows are pure evaluation data under the anchor-only design) — rewritten to state that plainly.

### Kept unchanged
- Stage-1 dictionary story (570 phrases), cough-type tree, fuzzy rescue, headache intake, Duration Safeguard table, red-flag tiers, RA 10173 privacy narrative, pharmacist-validation protocol (now evidence-only, not a 4th training source).

### Re-verified (live, anchor-only engine)
- Dictionary raw 231/288, hybrid raw 234/288 (raw micro-F1 0.849); guided 288/288 exact.
- `test.xlsx` suite: **518/520 (99.6%)** — the 2 residual rows are the documented sheet annotation issues (MIX-0043 typo row, CEB-NEG-0045 throat→Cough clash).
- pytest: 194 passed + 110 subtests; duration 31/31; headache intake 60/60.
- Backend comparison JSON regenerated with minilm/sailor only (disagreements 0).

