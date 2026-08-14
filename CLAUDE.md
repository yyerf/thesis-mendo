# CLAUDE.md — MendoVendo v3.0

Guidance for AI assistants working in this repo. Keep this file updated when architecture changes so future sessions don't have to re-explore.

## What this is

MendoVendo v3.0 — an **offline, multilingual (Tagalog/Bisaya/English/Taglish/Jejemon) symptom → OTC-medicine recommendation kiosk**. Undergrad thesis system. Core design value: **deterministic rules drive every safety-critical decision; ML (sentence embeddings) only assists language understanding.** Runs fully offline on a Raspberry Pi 5 (no GPU); privacy-sensitive (RA 10173 / PH Data Privacy Act) — patient data never leaves the device.

Detects **13 symptom labels**, recommends from **24 medicine entries** (19 brands) in `data/Mendo-Datasets.json`.

## Run / test commands

Always activate the venv first: `source .venv/bin/activate`

| Task | Command |
|------|---------|
| Dev server | `python app.py` → http://localhost:5000 (redirects to `/consult/`) |
| Production | `gunicorn wsgi:app --bind 0.0.0.0:8000` |
| Regression tests | `pytest testing/test_regressions.py` |
| Algorithm tests (detection, Tiers 1–4, 288 cases) | `python testing/test_algorithm.py` |
| Headache-type intake (free text → 19 types) | `python testing/test_headache_intake.py` |
| Duration Safeguard (Tier 5, 31 cases) | `python testing/test_duration.py` |
| Semantic-backend tests (MiniLM, mocked HTTP) | `pytest testing/test_sailor_semantic.py` |
| Semantic-partition audit tests | `pytest testing/test_semantic_partition.py` |
| **Evidence run (all suites, one report)** | `python testing/run_evidence.py` (writes `testing/benchmark/results/evidence.json` + `evidence_report.md`) |
| Pharmacist validation: export | `python testing/validation/export_validation_set.py --max 100 --seed 7` |
| Pharmacist validation: ingest | `python testing/validation/import_annotations.py --in annotated.csv` |
| Benchmark | `python _run_bench.py` (writes `_bench_output.txt`, gitignored) |
| Recommend (CLI) | `python -m mendo_core.step4_recommend --text "masakit ulo"` |
| Sailor2 live probe (needs Ollama) | `python -m mendo_core.sailor_semantic "masakit ulo"` |

First run downloads the semantic model (~420 MB) to `~/.cache/huggingface/hub/` when a MiniLM-family backend runs (default `minilm`); no Ollama is required for those. The default semantic engine is the **zero-shot MiniLM cosine-anchor path** (`MENDO_SEMANTIC_BACKEND=minilm`, step2, 270 anchor sentences, threshold 0.65); `sailor` selects the local-LLM path. The `sailor` path needs Ollama (v0.6+, schema-constrained `format`): `ollama serve` + `ollama pull sailor2:1b` (the app talks to `http://127.0.0.1:11434` over stdlib urllib). On Windows PowerShell, benchmark scripts need `$env:PYTHONIOENCODING='utf-8'` (they print ✓/✗).

## Architecture — the 5-stage pipeline (`mendo_core/`)

User text → symptoms → medicines. Two entry functions matter:

- **Text → symptoms:** `mendo_core.step3_hybrid.extract_symptoms_hybrid(user_input, semantic_threshold=0.65, semantic_max_symptoms=2) -> list[str]` (UPPERCASE labels)
- **Symptoms → medicines:** `mendo_core.step4_recommend.recommend_medicine(symptoms, rows, red_flags, ...) -> dict` (`action`, `recommendations`, `clarify_type`)

| File | Role |
|------|------|
| `step1.py` | Stage 1: dictionary phrase matching (570 phrases, 13 labels + TOOTHACHE, 5 languages); negation, contrastive splitting, cough-type tree, fuzzy rescue. `extract_symptoms(text)`. No ML. |
| `step2.py` | MiniLM embedding extractor — **zero-shot cosine path** (`MENDO_SEMANTIC_BACKEND=minilm`, **default**). `EmbeddingSymptomExtractor.analyze()`, cosine vs **270 anchor sentences**, threshold 0.65, `fallback_only=True`. No ML, no training. |
| `sailor_semantic.py` | **Local-LLM path** (`MENDO_SEMANTIC_BACKEND=sailor`, selectable, needs Ollama): Sailor2 1B `LLMSymptomExtractor`, same analyze() protocol as step2. Closed-vocabulary JSON decode (13 labels), temperature 0, max 120 tokens, fail-closed parsing (garbage → raises → caller treats semantic as unavailable), score = honest binary emission (1.0 emitted / 0.0 else), LRU response cache, `warmup()`. `fallback_only=True` (see step3 gating). Not deployed by default (see "Why Not an LLM" in the thesis + honesty guard). |
| `semantic_classifier.py` | **REMOVED 2026-08-14** — fine-tuned head deleted by decision (anchor-only thesis). Do not reintroduce; see docs/thesis changelog v4. |

| `step3_hybrid.py` | Stages 0+3: red-flag triage (`detect_red_flags`), orchestrates Stage 1, falls back to the semantic stage **only when Stage 1 returns nothing** (precision-first), applies lexical guards + negation vetoes + safety filters. `_get_semantic_extractor()` is the **backend factory** honoring `MENDO_SEMANTIC_BACKEND` (minilm default / sailor). All backends are `fallback_only`: the report path skips semantic when the dictionary hits (`skipped_reason: dictionary_hit_precision_first`). Includes the clause-scoped stomach-ache negation veto. Main detection entry point. |
| `headache_intake.py` | **Free-text headache-type intake**: deterministic multilingual tag matching (strong/weak per type) over the 14 clinical types in `headache_locations.py` (202 strong + 67 weak tags). Red-zone types (thunderclap/hypertension/spinal/post_traumatic/exertion) dominate and auto-refer. `classify_headache_text(text) -> dict`. Runs in `/api/analyze` when HEADACHE is detected from typed text (an explicit head-map click still wins). No ML. |
| `step4_recommend.py` | Stage 4: rule-based recommendation + safety (paracetamol overlap, opposing-mechanism, age filter, duration thresholds). `load_mendo_dataset(path)`, `recommend_medicine(...)`. |
| `symptom_models.py` | Baseline models (regex/rules) used only for the comparative benchmark. |
| `interaction_logger.py` | `log_interaction(...)` → appends JSON line to `logs/interactions.jsonl` (audit trail). |

**Semantic backend loading:** lazy singleton behind `_get_semantic_extractor()`; `web/app.py` pre-warms it in a background daemon thread (calls `warmup()` for the LLM backend — probes `/api/tags` + forces a tiny generation so the weights are hot; the MiniLM path does a throwaway encode). Backend env vars: `MENDO_SEMANTIC_BACKEND` (minilm\|sailor), `MENDO_LLM_URL`, `MENDO_LLM_MODEL` (default `sailor2:1b`), `MENDO_LLM_TIMEOUT`; MiniLM device via `MENDO_SEMANTIC_DEVICE`. `predict_symptoms` traces the active backend honestly (`engine_id` = `mendo-expert-minilm-v3.2` / `mendo-expert-sailor2-v1`, `semantic_score_type` = `cosine_similarity` / `constrained_decode_emission`). If the semantic stage is unavailable (Ollama down), it is recorded `available: false` and the system degrades to dictionary-only — the designed fail-closed path, never a hard error.

## Web + POS

One Flask app. `app.py` → `web/app.py` (creates `app`, pre-warms model, registers 4 blueprints from `pos/`):

| Prefix | File | Purpose |
|--------|------|---------|
| `/consult` | `pos/routes_consultation.py` | Kiosk UI; `/api/analyze`, `/api/clarify`, `/api/context-clarify`, `/api/duration-check`, `/api/transcribe` (STT). When nothing is detected, both `/api/pre-detect` and `/api/analyze` return `no_match_reason` (`negated_only` / `out_of_scope` / `nonsense` / `vague`, deterministic `classify_no_match()` in the routes file) so the UI shows distinct polite cards instead of one "Input not recognized" page. |
| `/checkout` | `pos/routes_checkout.py` | Cart + Xendit cashless payment (`/api/pay/xendit`, `/api/pay/verify`, webhook). Anti-hoarding caps: 3 units/item, 5 distinct items. |
| `/shop` | `pos/routes_shop.py` | Retail catalog/cart |
| `/admin` | `pos/routes_admin.py` | Staff dashboard (inventory, transactions, users); login decorator in `pos/auth.py` |

- `pos/__init__.py` exposes `init_pos(app)`.
- Templates: `web/templates/pos/` (main UI is `consultation.html`).
- DB: `pos/db.py` → SQLite at `data/mendo_pos.db` (WAL). Tables: `admin_users`, `inventory`, `transactions`, `transaction_items`, `stock_logs`. `init_db()` seeds default admin `admin / mendo2026`.

## Data files

- `data/Mendo-Datasets.json` — medicine DB (`Sheet1` array; fields: Brand, Generic, Category, symptoms, Min Age, Contraindications, Warnings, Max_Duration_Days, …).
- `data/mendo_pos.db` — SQLite (tracked, holds seeded inventory; do not delete).
- `data/datasets/symptom_eval.*.jsonl` — sample/template eval data.
- `testing/benchmark/testing.csv` — detection benchmark cases (288 rows; has a `tier` column).
- `testing/benchmark/duration_cases.csv` — Tier 5 Duration Safeguard cases (31 rows).
- `testing/benchmark/test_xlsx_cases.jsonl` — 520-case multilingual sheet (source of the 520 suite).
- `testing/benchmark/idiom_enrichment.jsonl` — 2026-08-14 idiom/figurative corpus (47 rows; evaluation-only under the anchor-only design; distinct from the held-out 16).
- `testing/benchmark/pharmacist_validated.jsonl` — Iteration-2 pharmacist annotations (created by `import_annotations.py`; 4th training source).
- `testing/benchmark/semantic_generalization.jsonl` — 16 held-out paraphrases (never trained on).
- `testing/benchmark/semantic_fresh_negatives.jsonl` — 20 held-out negatives (never trained on).
- `testing/validation/` — Iteration-2 pharmacist validation harness: `export_validation_set.py` (anonymized, sha256 ids), `import_annotations.py` (validate + ingest), `protocol.md` (annotation rules).

## Docs (2026-08-14 revision)

- `docs/thesis/final-methods-2026-08-14.md` — full final system methods, every formula, the change log, evidence table, deferred items.
- `docs/thesis/formulas.tex` — standalone LaTeX formula sheet (renders all equations).
- `docs/thesis/references.bib` — bibliography of works the system actually uses.

## Evaluation benchmark — the real, reproducible numbers (thesis-critical)

The structured benchmark is **319 cases across 5 tiers**, all reproducible:

| Tier | What | Cases | Runner |
|------|------|-------|--------|
| 1 Core Functional | symptom detection, multilingual, negation, clarification | 106 | `test_algorithm.py` |
| 2 Extended Robustness | code-switch, jejemon, misspellings, run-on, figurative | 94 | `test_algorithm.py` |
| 3 Adversarial | negation traps, false positives, gibberish, non-symptom | 64 | `test_algorithm.py` |
| 4 Triage Safety | red-flag/emergency presentations | 24 | `test_algorithm.py` |
| 5 Duration Safeguard | duration vs clinical threshold → OTC or refer | 31 | `test_duration.py` |

**Verified results (live, do not inflate):** detection Tiers 1–4 = **288/288 exact** with cough clarification — verified on the deployed 270-anchor MiniLM cosine default (`mendo-expert-minilm-v3.2`), and previously on the fail-closed dictionary-only and live Sailor2 paths, all 288/288 after the nasal-guard fix eliminated the last false positives (previously 283/288) and the cough-negation boundary fix restored 288/288 after the anchor expansion (was 287/288). The 520-case multilingual sheet suite = **518/520 (99.6%)** (the 2 remaining are an annotation typo row and the sheet's throat→Cough annotation clash with the product's SORE_THROAT label). Duration Tier 5 = **31/31 (100%)**, headache intake **60/60** (2026-08-14: +5 composite red-flag types: meningeal / stroke-like / sudden visual loss / syncope / pregnancy+headache), pytest suites **194 passed + 110 subtests**. **Pi 5 numbers NOT yet measured** — desktop dev machine shows ~4.4 ms/query full-pipeline mean with the encoder hot. M6 re-run on the Pi pending. Backend parity on the synthetic corpus is expected: precision-first gating means dictionary hits decide the answer and the backend only influences dictionary-miss cases. Held-out paraphrase set (2026-08-14 evidence, canonicalized BODY_ACHE→BODY_ACHES): **11/16** guarded pipeline (was 8/16 at 145 anchors, 10/16 under the removed classifier); fresh negatives 20/20. Full one-command reproduction: `python testing/run_evidence.py`.

**Side-by-side backend comparison** (`python testing/compare_backends.py` → `testing/benchmark/results/backend_comparison.json`): **two semantic backends, run live through the full pipeline** — zero-shot MiniLM cosine (`mendo-expert-minilm-v3.2`, **default**) and Sailor2 LLM (`mendo-expert-sailor2-v1`, optional, needs Ollama). Numbers (live run recorded in the JSON):

| backend | 288 synthetic | 16 paraphrases | 20 fresh negatives | mean s/query |
|---|---|---|---|---|
| **minilm (cosine, default)** | 288/288 | **11/16 (68.8%)** | 20/20 | 0.059 |
| sailor2 (optional) | 288/288 (dictionary-only when Ollama down; honest record) | 4/16 (semantic decided 0 — Ollama down at run time) | 20/20 | 0.074 |

The 16 paraphrase cases (`semantic_generalization.jsonl`) are where the semantic stage genuinely decides. **The 270-anchor zero-shot cosine path is the shipped default** (`MENDO_SEMANTIC_BACKEND=minilm`): explainable (every firing reports its best anchor sentence), zero training data, no external process (no Ollama), perfect negative precision (20/20), and it keeps the system fully dictionary+MiniLM (no LLM in the deployed path — consistent with the thesis's "Why Not an LLM" stance). The fine-tuned classifier previously shipped as default was **removed** (`mendo_core/semantic_classifier.py` + `train_semantic_classifier.py` + `data/models/semantic_classifier/` deleted) — its honest held-out numbers (9/16 raw, 10/16 canonicalized, 43.6% CV exact-match) were exceeded by the anchor expansion's 11/16 with none of the training-data caveats; see `docs/thesis/changelog-software-revision-2026-08-14.md` v4. Both live backends are 100% on the 20 fresh kiosk chit-chat negatives (`semantic_fresh_negatives.jsonl`) — nothing fires on "magkano ang biogesic". Guard vetoes are what keep the zero-shot backends' wrong guesses safe-by-design misses, never false positives.

**Duration thresholds** (in `step4_recommend.py` `DURATION_THRESHOLDS`; `check_duration_safety()` refers when `days > threshold`): fever 3, diarrhea 2, sore throat 5, stomach/headache/body/rashes/allergy/nasal/runny-nose 7, cough 14. (Nasal/runny-nose tightened 10→7 per Dr. Cherrie's "refer if > 1 week"; Tier-5 cases #21–24 updated to the 7-day boundary.)

**HONESTY GUARD (defense-critical) —** the 288 detection cases are **LLM-generated synthetic** inputs authored by the team; treat the benchmark as a coverage/regression measure, not independent accuracy. **Never write "288/288 / 100% accuracy", "zero failures / never detected a wrong symptom", or cite the old 9-case / 80-case / Table 10 transformer results** — the benchmark proves regression coverage on synthetic cases only, and the unreproducible legacy numbers have been removed/reframed as planned Iteration-2 work. Independent accuracy comes from the Iteration-2 pharmacist-annotated field validation. Benchmark output must record which backend ran (`engine_id` in `testing/benchmark/results/current.json`); a 288/288 run with Ollama down is the fail-closed dictionary-only result, not a Sailor2 result.

## Conventions & gotchas

- **Don't add nondeterminism to safety paths.** All clinical decisions (age, contraindication, duration, red-flag) are hard-coded rules by design — keep it that way (defended at length in the thesis). The LLM backend must stay deterministic by construction: closed-vocabulary decode, `temperature=0`, fail-closed parsing — never let its raw output bypass the lexical guards/safety filters.
- **Precision-first:** semantic layer activates only when the dictionary finds zero symptoms (all deployed backends — MiniLM cosine and Sailor2 — are `fallback_only`); a false positive is considered worse than a missed secondary symptom.
- Python 3.12.3. Deps in `requirements.txt` (dev) / `requirements.prod.txt` (CPU-only torch + gunicorn).
- `.env` holds secrets (`XENDIT_SECRET_KEY`, `XENDIT_WEBHOOK_TOKEN`, `MENDO_SECRET_KEY`) — gitignored.
- After changing detection rules, re-run `pytest testing/test_regressions.py` to catch regressions.

## Project notes

- **Fingerprint/biometric (AS608) was removed** by decision (checkout went 3 steps → 2: Cart → Payment). Do not reintroduce. The thesis does not include biometrics; the no-biometric design is now *defended* in the paper ("On User Verification and Anonymity" — RA 10173 / accessibility) in response to Emberda's panel comment. (Branch `latest-experiment-with-biometrics` is misnamed; no biometric code exists.)
- **June-30 defense revision (consultation UI):** added OLDCARTS safety-screening features in `consultation.html` — a clickable headache **head-map** (occipital/thunderclap → Emergency Triage), a rash **"difficulty breathing?"** screen → Emergency, a stomachache **before/after-eating** selector (maps to the existing acid-vs-cramp therapy split), and a **"Who is this for? (self/other)"** proxy-purchase step on the age panel (patient age flows to the age filter; `purchase_for` logged). These run as a flag-gated `startSafetyScreening()` phase before the duration flow. The 14 head-map types are **also reachable via typed free text** (`headache_intake.py`, deterministic, no ML): typing "sinus", "sinusitis", "worst headache ever", "high blood", "regla", etc. routes to the same type data (danger zone, prefer/avoid, referral) with zero extra UI steps.
- **2026-08-14 system revision (final, anchor-only):** the fine-tuned classifier was **removed by decision** (code + training script + weights deleted; see changelog v4) — the shipped semantic default is now the **zero-shot MiniLM cosine path, anchors expanded 145→270**, precision-first gating extended to MiniLM (`fallback_only=True`), dictionary `umoubo` + `nangangalay` + "body has been aching" additions, **cough-negation boundary fix** ("walang sore throat pero umuubo" — the 288-case regression found by the anchor expansion), **clause-scoped stomach-ache negation veto**, +5 composite red-flag headache types (meningeal, stroke_like, visual_loss, syncope, pregnancy — `RED_PRIORITY` extended, bare-`buntis` promote guard), Iteration-2 pharmacist-validation harness (`testing/validation/`), Windows temp-SQLite test-infra fixes, and the one-command evidence runner (`testing/run_evidence.py`). **Evening robustness pass:** the proposed "conjunction chunking" semantic enhancement was evaluated (`testing/semantic_chunk_sim.py`) and **rejected with data** — 0 gain on the 16 paraphrases (9/16→9/16), 20/20 negatives clean, but **20/170 spurious additions on exact-dict rows** (confusable-label pairs); whole-text scoring retained. `sinat` (common Tagalog "mild fever") pinned deterministically in the FEVER dictionary + fever negation regex + lexical-guard keywords (the removed classifier under-scored it at 0.280 even standalone; example now detects `['COUGH_GENERAL','FEVER']`); all suites re-verified unchanged. All documented in `docs/thesis/final-methods-2026-08-14.md` (+ `formulas.tex`, `references.bib`).
- **Defense deliverables (repo root, June-30):** `RPIC-Latest (Revised - Highlighted).docx` = the revised thesis with all changes highlighted **yellow** for copy-paste (the 208 pre-existing highlights are invisible `white`); `Thesis (Comments_Suggestions) - Synced.docx` = the routing form with Diapana/Emberda actions filled and the diarrhea/runny-nose claims corrected. Built by scripts in the session scratchpad.
- `_For-Mendo/` is an archived copy of the old v1/v2 system — **legacy, gitignored, not the live code.** Ignore it.
- Thesis docs (`Revision_Thesis.docx`, various `*.md`) are working academic files at repo root.
- **Thesis defense paper trail** (in `~/Downloads/`): `Revision - [RPIC] June-29.docx` is the current thesis; `Thesis (Comments_Suggestions).docx` is the **panel routing form** (panel comments → action taken → page/paragraph → status) and also holds the defense transcript. The two must stay **in sync** — the routing form's Page/Paragraph cite where in the thesis each comment was addressed. `RPIC-Latest.docx` is the pre-edit snapshot used for change-highlighting. User **Diapana** owns the Fuzzy Rescue, Evaluation Methodology, and Benchmark Design comments. Page numbers from LibreOffice render ~1–2 pages short of MS Word — verify.
