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
| Headache-type intake (free text → 14 types) | `python testing/test_headache_intake.py` |
| Duration Safeguard (Tier 5, 31 cases) | `python testing/test_duration.py` |
| Benchmark | `python _run_bench.py` (writes `_bench_output.txt`, gitignored) |
| Recommend (CLI) | `python -m mendo_core.step4_recommend --text "masakit ulo"` |

First run downloads the semantic model (~420 MB) to `~/.cache/huggingface/hub/`.

## Architecture — the 5-stage pipeline (`mendo_core/`)

User text → symptoms → medicines. Two entry functions matter:

- **Text → symptoms:** `mendo_core.step3_hybrid.extract_symptoms_hybrid(user_input, semantic_threshold=0.65, semantic_max_symptoms=2) -> list[str]` (UPPERCASE labels)
- **Symptoms → medicines:** `mendo_core.step4_recommend.recommend_medicine(symptoms, rows, red_flags, ...) -> dict` (`action`, `recommendations`, `clarify_type`)

| File | Role |
|------|------|
| `step1.py` | Stage 1: dictionary phrase matching (331 phrases, 13 labels, 5 languages); negation, contrastive splitting, cough-type tree, fuzzy rescue. `extract_symptoms(text)`. No ML. |
| `step2.py` | Stage 2: semantic fallback. `EmbeddingSymptomExtractor.analyze()` using `paraphrase-multilingual-MiniLM-L12-v2` (~33M params), cosine vs 118 anchor sentences, threshold 0.65. |
| `step3_hybrid.py` | Stages 0+3: red-flag triage (`detect_red_flags`), orchestrates Stage 1, falls back to Stage 2 **only when Stage 1 returns nothing** (precision-first), applies lexical guards + safety filters. Main detection entry point. |
| `headache_intake.py` | **Free-text headache-type intake**: deterministic multilingual tag matching (strong/weak per type) over the 14 clinical types in `headache_locations.py` (202 strong + 67 weak tags). Red-zone types (thunderclap/hypertension/spinal/post_traumatic/exertion) dominate and auto-refer. `classify_headache_text(text) -> dict`. Runs in `/api/analyze` when HEADACHE is detected from typed text (an explicit head-map click still wins). No ML. |
| `step4_recommend.py` | Stage 4: rule-based recommendation + safety (paracetamol overlap, opposing-mechanism, age filter, duration thresholds). `load_mendo_dataset(path)`, `recommend_medicine(...)`. |
| `symptom_models.py` | Baseline models (regex/rules) used only for the comparative benchmark. |
| `interaction_logger.py` | `log_interaction(...)` → appends JSON line to `logs/interactions.jsonl` (audit trail). |

**Model loading:** lazy singleton, loaded on first query needing semantics; `web/app.py` pre-warms it in a background daemon thread. Device via `MENDO_SEMANTIC_DEVICE` (default CPU).

## Web + POS

One Flask app. `app.py` → `web/app.py` (creates `app`, pre-warms model, registers 4 blueprints from `pos/`):

| Prefix | File | Purpose |
|--------|------|---------|
| `/consult` | `pos/routes_consultation.py` | Kiosk UI; `/api/analyze`, `/api/clarify`, `/api/context-clarify`, `/api/duration-check`, `/api/transcribe` (STT) |
| `/checkout` | `pos/routes_checkout.py` | Durable order/cart, simulator cash, Xendit payment (`/api/pay/xendit`, `/api/pay/verify`, webhook), reservation, and dispensing APIs. Anti-hoarding caps: 3 units/item, 5 distinct items. Real hardware remains behind the Phase 0 evidence gate. |
| `/shop` | `pos/routes_shop.py` | Retail catalog/cart |
| `/admin` | `pos/routes_admin.py` | Staff dashboard (inventory, transactions, users, hardware health, accounting, cashbox, and recovery); login decorator in `pos/auth.py` |

- `pos/__init__.py` exposes `init_pos(app)`.
- Templates: `web/templates/pos/` (main UI is `consultation.html`).
- DB: `pos/db.py` → SQLite at `data/mendo_pos.db` (WAL). Legacy tables remain (`admin_users`, `inventory`, `transactions`, `transaction_items`, `stock_logs`); additive order tables include `orders`, `order_items`, `cash_payment_sessions`, `cash_events`, `payment_attempts`, `motion_profiles`, `dispense_jobs`, `cashbox_sessions`, and `order_audit_events`. `init_db()` seeds default admin `admin / mendo2026`.

## Data files

- `data/Mendo-Datasets.json` — medicine DB (`Sheet1` array; fields: Brand, Generic, Category, symptoms, Min Age, Contraindications, Warnings, Max_Duration_Days, …).
- `data/mendo_pos.db` — SQLite (tracked, holds seeded inventory; do not delete).
- `data/datasets/symptom_eval.*.jsonl` — sample/template eval data.
- `testing/benchmark/testing.csv` — detection benchmark cases (288 rows; has a `tier` column).
- `testing/benchmark/duration_cases.csv` — Tier 5 Duration Safeguard cases (31 rows).

## Evaluation benchmark — the real, reproducible numbers (thesis-critical)

The structured benchmark is **319 cases across 5 tiers**, all reproducible:

| Tier | What | Cases | Runner |
|------|------|-------|--------|
| 1 Core Functional | symptom detection, multilingual, negation, clarification | 106 | `test_algorithm.py` |
| 2 Extended Robustness | code-switch, jejemon, misspellings, run-on, figurative | 94 | `test_algorithm.py` |
| 3 Adversarial | negation traps, false positives, gibberish, non-symptom | 64 | `test_algorithm.py` |
| 4 Triage Safety | red-flag/emergency presentations | 24 | `test_algorithm.py` |
| 5 Duration Safeguard | duration vs clinical threshold → OTC or refer | 31 | `test_duration.py` |

**Verified results (live, do not inflate):** detection Tiers 1–4 = **283/288 exact (98.3%)** with cough clarification, **234/288 (81.2%, micro-F1 0.852)** raw; Duration Tier 5 = **31/31 (100%)**. The 5 detection misses are adversarial NONE-expected probes (#207/#212/#222 genuine false positives; #275/#282 caught by the red-flag layer).

**Duration thresholds** (in `step4_recommend.py` `DURATION_THRESHOLDS`; `check_duration_safety()` refers when `days > threshold`): fever 3, diarrhea 2, sore throat 5, stomach/headache/body/rashes/allergy/nasal/runny-nose 7, cough 14. (Nasal/runny-nose tightened 10→7 per Dr. Cherrie's "refer if > 1 week"; Tier-5 cases #21–24 updated to the 7-day boundary.)

**HONESTY GUARD (defense-critical) —** the 288 detection cases are **LLM-generated synthetic** inputs authored by the team; treat the benchmark as a coverage/regression measure, not independent accuracy. **Never write "288/288 / 100%", "zero failures / never detected a wrong symptom", or cite the old 9-case / 80-case / Table 10 transformer results** — those were unreproducible and have been removed/reframed as planned Iteration-2 work. Independent accuracy comes from the Iteration-2 pharmacist-annotated field validation.

## Conventions & gotchas

- **Don't add nondeterminism to safety paths.** All clinical decisions (age, contraindication, duration, red-flag) are hard-coded rules by design — keep it that way (defended at length in the thesis).
- **Precision-first:** semantic layer activates only when the dictionary finds zero symptoms; a false positive is considered worse than a missed secondary symptom.
- Python 3.12.3. Deps in `requirements.txt` (dev) / `requirements.prod.txt` (CPU-only torch + gunicorn).
- `.env` holds secrets (`XENDIT_SECRET_KEY`, `XENDIT_WEBHOOK_TOKEN`, `MENDO_SECRET_KEY`) — gitignored.
- After changing detection rules, re-run `pytest testing/test_regressions.py` to catch regressions.

## Project notes

- **Fingerprint/biometric (AS608) was removed** by decision (checkout went 3 steps → 2: Cart → Payment). Do not reintroduce. The thesis does not include biometrics; the no-biometric design is now *defended* in the paper ("On User Verification and Anonymity" — RA 10173 / accessibility) in response to Emberda's panel comment. (Branch `latest-experiment-with-biometrics` is misnamed; no biometric code exists.)
- **Payment-only hardware phase:** read `CHECKPOINT.md`, `hardware/README.md`, and `docs/architecture/cash-order-integration.md` before changing hardware behavior. The measured D2/D3 cash paths can drive supervised real POS payment tests; payment atomically commits stock and never creates a dispense job. Medicine motors are compile-time disabled and PCA OE is held HIGH. Do not connect powered servos or route checkout back through `_dispatch_order` until motion receives its own calibration and approval.
- **June-30 defense revision (consultation UI):** added OLDCARTS safety-screening features in `consultation.html` — a clickable headache **head-map** (occipital/thunderclap → Emergency Triage), a rash **"difficulty breathing?"** screen → Emergency, a stomachache **before/after-eating** selector (maps to the existing acid-vs-cramp therapy split), and a **"Who is this for? (self/other)"** proxy-purchase step on the age panel (patient age flows to the age filter; `purchase_for` logged). These run as a flag-gated `startSafetyScreening()` phase before the duration flow. The 14 head-map types are **also reachable via typed free text** (`headache_intake.py`, deterministic, no ML): typing "sinus", "sinusitis", "worst headache ever", "high blood", "regla", etc. routes to the same type data (danger zone, prefer/avoid, referral) with zero extra UI steps.
- **Defense deliverables (repo root, June-30):** `RPIC-Latest (Revised - Highlighted).docx` = the revised thesis with all changes highlighted **yellow** for copy-paste (the 208 pre-existing highlights are invisible `white`); `Thesis (Comments_Suggestions) - Synced.docx` = the routing form with Diapana/Emberda actions filled and the diarrhea/runny-nose claims corrected. Built by scripts in the session scratchpad.
- `_For-Mendo/` is an archived copy of the old v1/v2 system — **legacy, gitignored, not the live code.** Ignore it.
- Thesis docs (`Revision_Thesis.docx`, various `*.md`) are working academic files at repo root.
- **Thesis defense paper trail** (in `~/Downloads/`): `Revision - [RPIC] June-29.docx` is the current thesis; `Thesis (Comments_Suggestions).docx` is the **panel routing form** (panel comments → action taken → page/paragraph → status) and also holds the defense transcript. The two must stay **in sync** — the routing form's Page/Paragraph cite where in the thesis each comment was addressed. `RPIC-Latest.docx` is the pre-edit snapshot used for change-highlighting. User **Diapana** owns the Fuzzy Rescue, Evaluation Methodology, and Benchmark Design comments. Page numbers from LibreOffice render ~1–2 pages short of MS Word — verify.
