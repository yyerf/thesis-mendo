# Mendo V3 Architecture Analysis

Date: 2026-05-13

This report is a read-only architecture analysis of the current repository. No code has been refactored in this pass.

## Executive Summary

The active application is a Flask-based kiosk/POS system with a modular core for multilingual symptom interpretation and deterministic OTC recommendation support. The main runtime path is:

1. Flask app startup in `app.py` -> `web/app.py`
2. POS and consultation blueprints registered from `pos/__init__.py`
3. Consultation endpoints in `pos/routes_consultation.py`
4. NLP and safety logic in `mendo_core/step1.py`, `step2.py`, `step3_hybrid.py`, and `step4_recommend.py`
5. Medicine data from `data/Mendo-Datasets.json`
6. Stock and transactions in SQLite at `data/mendo_pos.db`

The active NLP pipeline is deterministic rules plus semantic fallback. The repository also contains legacy TF-IDF/SVM work under `_For-Mendo/`, but that code is untracked and not part of the active Flask runtime. This is important because the project description says the current pipeline includes TF-IDF cosine similarity; the active root code does not currently expose a TF-IDF cosine stage.

The safety architecture is stronger than a typical prototype: red-flag triage, negation handling, blood-context filters, duration safeguards, condition-aware contraindication filters, age filtering, duplicate paracetamol warnings, and cough/stomach/diarrhea clarification gates are all implemented. The weakest architecture area is hardware integration: `pos/routes_shop.py` expects `hardware.serial_bridge.VendoBridge`, but the source file is missing. Only `.pyc` cache files remain, and `import hardware.serial_bridge` fails in the current tree.

## Repository Structure

Active runtime:

- `app.py`: legacy-compatible launcher that imports `web.app`.
- `web/app.py`: Flask app factory-like module, blueprints, session config, and semantic model preload thread.
- `pos/`: POS, checkout, consultation, admin, auth, and SQLite database modules.
- `mendo_core/`: NLP, safety, recommendation, and interaction logging.
- `data/Mendo-Datasets.json`: authoritative medicine metadata used by the recommender.
- `data/mendo_pos.db`: SQLite POS inventory and transaction database.
- `web/templates/pos/consultation.html`: large kiosk UI containing consultation, severity, duration, cart, fingerprint, and payment flows.
- `web/static/js/pos.js`: cashier POS JavaScript.
- `testing/`: benchmark and regression tests.
- `tools/`: STT proof of concept and small benchmark harness.

Legacy or cleanup candidates:

- `_For-Mendo/`: untracked legacy app with MySQL, TF-IDF/SVM, old templates, old test scripts, package files, and model artifacts.
- `web/templates/_archive/` and `web/static/_archive/`: archived UI.
- Tracked generated files: `__pycache__`, `.pyc`, `.bak`, benchmark HTML/CSV/JSON results, DOCX/PDF thesis outputs, and SQLite database.
- `.venv/`: ignored but very large at about 7.5 GB.

## Active Application Architecture

`web/app.py` creates a Flask app, configures session cookie settings, initializes the POS subsystem, starts a background semantic model preload, and redirects `/` to `/consult/`.

Blueprints:

- `admin_bp` under `/admin`: login, dashboard, inventory, transactions, users.
- `shop_bp` under `/shop`: cashier shop/cart/checkout flow.
- `consultation_bp` under `/consult`: kiosk symptom analysis, clarification, duration, transcription.
- `checkout_bp` under `/checkout`: kiosk cart, simulated fingerprint auth, Xendit payment, payment verification.

The application is not currently built as a factory function. Importing `web.app` creates the app, initializes SQLite, and starts the semantic preload thread. This is simple for a thesis demo but makes tests, multi-worker deployment, and controlled startup harder.

## NLP Pipeline

### Stage 0: Red-Flag Safety Layer

Implemented in `mendo_core/step3_hybrid.py`.

This stage runs before symptom extraction and detects cases where OTC recommendation should be blocked. It uses:

- Co-occurrence rules with token windows.
- Local exclusion windows to prevent over-triage.
- Special handlers for pregnancy, hyperthermia, severe dehydration, direct dengue terms, seizure, loss of consciousness, and hypertension context.
- Blood-context suppression so blood near head/nose/stool/cough does not become headache, runny nose, diarrhea, or cough.

Examples of covered red flags include:

- Blood in stool
- Blood in vomit
- Chest pain
- Difficulty breathing
- Dengue warning
- Stroke warning
- Severe dehydration
- Pregnancy contraindication
- High fever at or above 40 C
- Seizure
- Loss of consciousness
- Severe allergic reaction
- Head, nose, ear, cough, or urine blood contexts
- Hypertension risk

Design note: red flags do not fully short-circuit symptom extraction. The system still extracts symptoms for benchmark visibility, but `step4_recommend.py` blocks OTC recommendations when red flags are passed to the recommendation stage.

### Stage 1: Deterministic Dictionary and Heuristics

Implemented in `mendo_core/step1.py`.

Core structures:

- `SYMPTOM_DICTIONARY`: uppercase symptom label -> multilingual phrase list.
- `CONDITION_LABELS`: condition label -> phrases for contraindication context, especially hypertension and pregnancy.
- `_normalize`: lowercasing, leetspeak/jejemon mapping, punctuation removal, whitespace collapse.
- `_is_negated`: deterministic negation window for English, Filipino, and Bisaya negators.
- `_extract_cough_type`: cough classifier for dry, productive, and general cough.
- `_levenshtein_within`: bounded fuzzy rescue for selected high-value typo cases.

Strengths:

- Very explainable.
- Fast enough for Raspberry Pi.
- Good thesis-defense traceability.
- Handles Tagalog, English, Bisaya/Cebuano, mixed input, and selected jejemon/noisy text.
- Includes cough-type disambiguation before generic matching.

Weaknesses:

- The file is large at 1,472 lines and combines vocabulary, normalization, negation, fuzzy matching, and heuristics.
- Many rules are embedded in code rather than data files, making review and versioning harder.
- The logic is precision-focused, but growing it further will become brittle unless vocabularies and rules are separated.

### Stage 2: Semantic Embedding Fallback

Implemented in `mendo_core/step2.py`.

Current model:

- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`

Core structures:

- `SYMPTOM_ANCHORS`: symptom label -> multilingual anchor sentences.
- `EmbeddingSymptomExtractor`: encodes user input and compares against pre-encoded anchors using cosine similarity.
- `SemanticMatch`: symptom, score, and best anchor for explainability.

Current default threshold in the active pipeline:

- `semantic_threshold=0.65`
- `semantic_max_symptoms=2` in main consultation flow, sometimes 3 in benchmarks.

Important behavior:

- Semantic fallback runs only if dictionary extraction finds no symptoms.
- It is retrieval-style semantic matching, not diagnosis and not generative medical advice.
- It has explainable evidence: best anchor and cosine score.

### Stage 3: Hybrid Orchestration

Implemented in `mendo_core/step3_hybrid.py`.

Flow:

1. Detect red flags.
2. Run dictionary extraction and condition extraction.
3. Apply cough negation and blood-context filters.
4. If dictionary produced symptoms, return dictionary result.
5. If no dictionary result and semantic fallback is enabled, load the semantic extractor lazily.
6. Run embedding similarity.
7. Apply lexical guard and semantic safety filters.
8. Select top-N semantic labels.
9. Return a structured report for UI and benchmarks.

The lexical guard is important. It rejects semantic false positives unless the text contains symptom-family keywords. This is a good safety compromise: embeddings help with paraphrase recall, but deterministic gates preserve precision.

### Stage 4: OTC Recommendation

Implemented in `mendo_core/step4_recommend.py`.

Core structures:

- `MedRow`: normalized medicine row from `Mendo-Datasets.json`.
- `DURATION_THRESHOLDS`: symptom -> safe duration threshold.
- `_DURATION_OPTIONS`: UI duration choices.
- Context clue lists for diarrhea, stomach ache, runny nose, headache, allergy, and cold-weather contexts.

Flow:

1. If red flags exist, return `action="triage"` with no medicine recommendations.
2. If no symptoms, return `action="no_match"`.
3. Normalize condition labels such as hypertension and pregnancy.
4. Ask clarifying questions for ambiguous cough, diarrhea context, stomach context, or runny-nose context when needed.
5. Score dataset rows using symptom-specific deterministic rules.
6. Merge by brand.
7. Filter contraindications and condition risks.
8. Return top recommendations plus warnings.

Safety rules include:

- Red-flag triage gate.
- COUGH_GENERAL clarification.
- Food-poisoning diarrhea clarification and loperamide avoidance.
- Acidic vs cramping stomach clarification.
- Runny-nose allergy vs cold-weather clarification.
- Duration safeguard.
- Condition filter for hypertension and decongestants.
- Age filtering in `pos/routes_consultation.py`.
- Multiple paracetamol warning.
- Expectorant plus cough suppressant warning.

## Retrieval Flow

The active retrieval-like pieces are:

- Rule retrieval: phrase patterns map text to symptom labels.
- Semantic symptom retrieval: user text embedding is compared to symptom anchor embeddings.
- Medicine retrieval: symptom labels retrieve candidate medicines by deterministic scoring over dataset text fields.

There is no active vector index such as FAISS or HNSW. The anchor set is small enough that brute-force cosine is fine.

There is no active TF-IDF cosine stage in the root runtime. TF-IDF/SVM artifacts and scripts are present in `_For-Mendo/`, especially `train_model.py`, `benchmark_models.py`, and `app.py`.

## Data Structures

Symptom data:

- `SYMPTOM_DICTIONARY` in `step1.py`
- `SYMPTOM_ANCHORS` in `step2.py`
- Lowercase benchmark labels in `mendo_core/symptom_models.py`
- Uppercase active labels in `step1`, `step2`, `step3`, and `step4`

Safety data:

- `RED_FLAG_MESSAGES`
- `_TRIAGE_RULES`
- condition phrase lists
- duration thresholds
- contextual clue lists
- contraindication keyword logic

Medicine data:

- `data/Mendo-Datasets.json`
- Top-level key: `Sheet1`
- Current rows: 24
- Main fields: brand, generic/main use, drug category, primary symptom, typical symptoms, dosage form, minimum age, notes, approved indications, contraindications, warnings, interactions, max duration, source fields.

POS database:

- `admin_users`
- `inventory`
- `transactions`
- `transaction_items`
- `stock_logs`

Logging:

- `logs/interactions.jsonl`
- Includes input, extracted symptoms, pipeline stages, action, recommendations, red flags, clarification, severity, age, and session.

## Medicine Database Structure

The JSON dataset has 24 medicine entries across 19-20 unique brands depending on how duplicates are counted. Multiple entries share the same brand for different dosage forms or indication rows, for example Biogesic, Advil, Cetirizine, Solmux, and Symdex-D.

The SQLite inventory table enforces `brand TEXT UNIQUE NOT NULL`. During seeding, the system inserts one inventory row per unique brand and skips duplicates. Current observed counts:

- JSON dataset rows: 24
- SQLite inventory rows: 20

Risk: dosage-form variants can be lost in POS inventory. For a medicine dispenser, this matters because a syrup, tablet, and capsule may require different slots, age rules, packaging dimensions, price, and dispensing actuator behavior.

Recommendation: the future schema should use `medicine_id` or SKU-level identity instead of `brand` as the unique key.

## Multilingual Handling

The system intentionally avoids language detection. It treats input as mixed-language text and searches for symptom evidence across English, Filipino/Tagalog, and Bisaya/Cebuano.

Mechanisms:

- Normalization and leetspeak mapping.
- Multilingual dictionary phrases.
- Multilingual semantic anchors.
- Mixed-language negation handling.
- UI language support for English, Filipino, and Cebuano/Bisaya.
- STT endpoint and tool code exist, with Whisper/Google fallback options.

Strength: this matches real kiosk input where users code-switch.

Weakness: language-specific morphology, misspellings, and regional variants are scattered across rule code. Scaling to more dialects will require a structured lexicon and augmentation workflow.

## Model Loading Strategy

Current strategy:

- `web/app.py` starts a daemon thread on import.
- The thread calls `_get_semantic_extractor()` from `step3_hybrid.py`.
- `_get_semantic_extractor()` uses a module-level singleton `_SEMANTIC_EXTRACTOR`.
- `EmbeddingSymptomExtractor` loads SentenceTransformer on `MENDO_SEMANTIC_DEVICE` or CPU by default.
- Anchors are pre-encoded at model initialization.
- A warmup query runs after preload.

Strengths:

- First user query should avoid cold-start delay.
- If preload fails, the first real query can retry.
- If semantic dependencies are missing, the pipeline fails safe to deterministic output.

Weaknesses:

- The background thread starts at import time, including test imports.
- In multi-worker Gunicorn, each worker loads its own model copy.
- There is no explicit model readiness endpoint.
- Dependency versions are pinned for the current MiniLM stack, not for newer Qwen3 model cards that may require newer Transformers.
- Model loading, retrieval, and fallback behavior are not abstracted behind an experiment-friendly interface.

## Hardware Communication Architecture

The active source tree does not currently contain a usable hardware bridge source file.

Observed state:

- `pos/routes_shop.py` optionally imports `hardware.serial_bridge.VendoBridge`.
- The import currently fails because `hardware/serial_bridge.py` is missing.
- Only `hardware/__pycache__/serial_bridge.cpython-312.pyc` exists.
- String inspection of the `.pyc` suggests a previous `VendoBridge` class with serial commands such as `PING`, `STATUS`, `DISPENSE:N`, `BATCH`, `TEST:N`, and `RESET`.
- No `hardware/config.json` slot mapping is present.
- No Arduino `.ino` firmware is present.
- Kiosk fingerprint auth in `pos/routes_checkout.py` is simulated and always succeeds after button click.

Conclusion: hardware integration is architecturally intended but not reproducible from source. This must be fixed before a thesis-grade deployment claim.

## Testing and Validation

Existing assets:

- `testing/benchmark/testing.csv`: 288 test cases plus header.
- `testing/test_algorithm.py`: benchmark runner that writes CSV/HTML/JSON results.
- `testing/test_regressions.py`: regression unittest suite, including triage, negation, recommendation, context clarification, and duration safeguards.
- Latest saved benchmark summary: `testing/benchmark/results/test_summary_20260409_180056.json`
  - total tests: 288
  - exact matches: 283
  - failures: 5
  - exact accuracy: 0.983

Testing weaknesses:

- Saved results are tracked in git, creating repository noise.
- Benchmarks mutate result directories by design.
- The active benchmark focuses on label exact match more than latency, memory, model cold start, calibration, or safety override pass rate.
- There is no experiment harness for modern embedding/reranker comparisons.

## Weakness Analysis

1. Active vs legacy ambiguity

The repo contains a current Flask/POS app and a legacy `_For-Mendo/` app with separate models, database assumptions, and templates. This makes it hard to know what is authoritative.

2. Missing hardware source

The source for `hardware.serial_bridge` is absent, so dispensing cannot be reproduced from the tracked code. Fingerprint auth is simulated.

3. Large rule files

`step1.py`, `step3_hybrid.py`, and `step4_recommend.py` are large and contain mixed concerns: vocabulary, policy, normalization, extraction, safety, and presentation strings.

4. Medicine SKU collapse

The inventory schema is brand-unique, but the JSON dataset has duplicate brand rows. This collapses dosage-form and possibly age-specific variants.

5. Documentation drift

Some docs describe older or aspirational architecture, including TF-IDF and hardware, while the active code differs.

6. Test artifact and cache pollution

Tracked `.pyc`, `__pycache__`, `.bak`, logs, benchmark outputs, SQLite DB, DOCX, and PDF files make refactoring risky and noisy.

7. Dependency drift

Production requirements pin `transformers<4.37`, while newer embedding models such as Qwen3 model cards may require newer library support.

8. Payment and authentication demo shortcuts

Fingerprint auth is simulated. Payment verification is session-based and webhook handling is mostly logged rather than a source of truth for order completion.

## Bottleneck Analysis

CPU and latency:

- Dictionary and red flags are fast.
- Semantic encoding is the main NLP latency cost.
- Preloading reduces first-query latency but increases startup memory.
- Rerankers would be significantly slower than embedding retrieval on Raspberry Pi, especially cross-encoder rerankers.

Memory:

- The current virtual environment is about 7.5 GB.
- Each Flask/Gunicorn worker would load its own model copy.
- Qwen3 4B/8B-scale embedding or reranker models are not realistic for local Pi inference without aggressive quantization and tight limits.

Data:

- Brute-force anchor comparison is fine now.
- If anchors and medicine indications grow, a vector index and precomputed cache will be needed.

Database:

- SQLite is acceptable for kiosk/POS prototype use.
- Concurrent writes and payment/dispense recovery would need careful transaction boundaries.

Frontend:

- `consultation.html` is very large and contains extensive inline CSS/JS. This is a maintainability bottleneck.

## Scalability Analysis

Symptom expansion:

- Adding a symptom currently requires changes across dictionary phrases, anchors, lexical guard, duration thresholds, recommendation rules, display labels, UI logic, tests, and dataset rows.
- This is manageable for 13-20 symptoms but will become error-prone at larger scope.

Medicine expansion:

- Every medicine needs contraindications, warnings, interactions, age rules, duration, price, stock, source references, and hardware slot mapping.
- The current brand-unique POS table does not scale to SKU-level dispensing.

Language expansion:

- Rule expansion alone will not scale well to more regional language variants.
- A controlled augmentation and annotation process is needed.

Deployment expansion:

- Local-only kiosk deployment is feasible.
- Multi-kiosk deployment would need centralized inventory sync, audit logs, user privacy policy, and payment reconciliation.

## Safety-Risk Analysis

High-value safety features already present:

- Red-flag triage before recommendation.
- Deterministic safety overrides.
- No generative diagnosis.
- Explainable symptom and recommendation evidence.
- Age filtering.
- Duration gating.
- Condition-aware contraindication filtering.
- Multiple paracetamol warning.
- Opposing cough mechanism warning.
- Interaction logging for expert review.

Residual risks:

- Missing hardware bridge source means dispensing cannot be audited or validated from code.
- Simulated fingerprint auth gives false confidence if described as deployed biometric authentication.
- Brand-level inventory could dispense the wrong form if multiple forms share one brand.
- Condition filters currently focus heavily on hypertension and pregnancy; broader contraindications are stored but not fully structured.
- Severity gate warns but may still allow display flow complexity that needs careful UX validation.
- Recommendation rules are deterministic but embedded in code, making expert review harder than data-driven policy tables.
- STT can introduce transcription errors; the pipeline needs STT-specific tests.
- Logs may contain health-related user text and need privacy controls.

## Modernization Opportunities

Near-term:

- Restore `hardware/serial_bridge.py`, `hardware/config.json`, and Arduino firmware source.
- Split active and legacy code clearly.
- Move generated docs/results/logs/caches out of tracked source.
- Normalize medicine data into SKU-level records.
- Extract safety rules and symptom lexicons into versioned data files.
- Add a model adapter interface for deterministic, TF-IDF, embedding, reranker, and hybrid experiments.
- Add latency/memory benchmarks.

Mid-term:

- Build a local vector store over symptom anchors and approved indication snippets.
- Add reranking only after deterministic safety gates.
- Add experiment tracking with frozen datasets and signed model configurations.
- Add a hardware simulator for CI.
- Add a payment/order state machine with recovery after crash or network failure.

Long-term:

- Move to a modular package layout:
  - `mendo_core/nlp/`
  - `mendo_core/safety/`
  - `mendo_core/medicine/`
  - `mendo_core/hardware/`
  - `mendo_core/evaluation/`
- Add expert annotation workflow.
- Add privacy-preserving telemetry and dataset curation pipeline.
- Support optional server-side model inference while keeping deterministic local fallback.

## Source Notes

Local code inspected:

- `web/app.py`
- `pos/*.py`
- `mendo_core/*.py`
- `tools/*.py`
- `testing/*.py`
- `data/Mendo-Datasets.json`
- `data/mendo_pos.db`
- `_For-Mendo/*`

External primary sources used for model modernization context:

- Qwen3 Embedding model cards: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B and https://huggingface.co/Qwen/Qwen3-Embedding-8B
- Qwen3 Reranker model card: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
- BGE-M3 model card: https://huggingface.co/BAAI/bge-m3
- Jina Embeddings v3 announcement/model documentation: https://jina.ai/news/jina-embeddings-v3-a-frontier-multilingual-embedding-model/
- Current MiniLM baseline model card: https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
