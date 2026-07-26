# Mendo V3 Modernization Plan

This plan proposes modernization and refactoring opportunities after the read-only analysis. It does not implement changes.

## Non-Negotiable Design Rules

1. Deterministic safety rules must remain first-class and must override probabilistic model output.
2. The system must not diagnose diseases.
3. The system must only perform symptom interpretation, OTC assistance, and recommendation support.
4. Generative medical advice must not be exposed to users.
5. Every recommendation must be explainable through rules, sources, anchors, scores, and safety filters.
6. Raspberry Pi deployment must preserve a safe local fallback even if semantic models or network services fail.

## Target Architecture

Recommended module boundaries:

```text
mendo_core/
  nlp/
    normalization.py
    deterministic.py
    semantic.py
    reranking.py
    interfaces.py
  safety/
    triage.py
    negation.py
    duration.py
    contraindications.py
    policy_data/
  medicine/
    dataset.py
    recommendation.py
    sku.py
  hardware/
    serial_bridge.py
    fingerprint.py
    simulator.py
  evaluation/
    datasets.py
    metrics.py
    runners.py
    reports.py
  logging/
    interaction_logger.py
```

The active Flask app should call service interfaces instead of importing large step files directly.

## Refactor Priorities

### Phase 1: Repository Hygiene

Goal: separate active source from artifacts without changing runtime behavior.

Actions:

- Move `_For-Mendo/` into a clearly named `legacy/` area or remove it after archiving.
- Remove tracked `__pycache__`, `.pyc`, `.bak`, result HTML/CSV/JSON files, and local logs from git.
- Keep benchmark results in `artifacts/` or outside source control.
- Add explicit `.gitignore` rules for:
  - `logs/*.jsonl`
  - `testing/benchmark/results/*`
  - `*.bak`
  - local SQLite files
  - generated DOCX/PDF outputs
- Keep final thesis documents in a `docs/thesis/` folder only if they are intentionally versioned.

Why this matters:

- Refactors will otherwise show thousands of noisy changes.
- Reviewers cannot distinguish active source from generated artifacts.

### Phase 2: Restore Hardware Reproducibility

Goal: make the hardware stack source-controlled and testable.

Actions:

- Restore `hardware/serial_bridge.py` from source, not `.pyc`.
- Add `hardware/config.example.json` with slot mappings.
- Add Arduino Mega firmware source, preferably under `hardware/arduino/`.
- Add a `HardwareBridge` interface with:
  - `connect()`
  - `is_connected()`
  - `dispense(slot)`
  - `dispense_batch(slot_qty_map)`
  - `status()`
  - `reset()`
- Add a simulator implementation for tests.
- Add explicit transaction states:
  - `payment_pending`
  - `paid`
  - `dispensing`
  - `dispensed`
  - `dispense_failed`
  - `refunded_or_manual_review`

Why this matters:

- A thesis-grade vending system must be reproducible from source.
- Hardware behavior must be testable without physical devices.

### Phase 3: Medicine Data Normalization

Goal: move from brand-level inventory to SKU-level dispensing.

Current problem:

- JSON dataset has 24 rows.
- SQLite inventory has 20 rows because `inventory.brand` is unique.
- Duplicate brands can represent different dosage forms or indication rows.

Recommended data model:

```text
medicine_product
  id
  brand
  generic_name
  drug_category
  source_status

medicine_sku
  id
  product_id
  dosage_form
  strength
  package_size
  min_age
  barcode_or_slot_code
  unit_price
  stock_quantity
  hardware_slot

medicine_indication
  sku_id
  symptom_label
  approved_indication
  source

medicine_safety
  sku_id
  contraindications_json
  warnings_json
  interactions_json
  max_duration_days
  source
```

Why this matters:

- A dispensing machine dispenses physical SKUs, not abstract brands.
- Age rules, prices, dosage forms, and slots differ by SKU.

### Phase 4: Safety Rules as Data

Goal: make safety rules easier to review and defend.

Move these into versioned data files:

- Red-flag rules.
- Exclusion windows.
- Negation vocabulary.
- Duration thresholds.
- Condition contraindication mappings.
- Symptom display names.
- Cough/stomach/diarrhea clarification options.

Keep the engine deterministic, but load rule tables from reviewed files.

Benefits:

- Pharmacists and panelists can review policy without reading Python.
- Changes become diffable at the rule level.
- Safety tests can verify each rule row.

### Phase 5: NLP Experiment Interface

Goal: compare deterministic, TF-IDF, embedding, reranker, and hybrid systems fairly.

Recommended interface:

```python
class SymptomInterpreter:
    name: str

    def analyze(self, text: str) -> SymptomResult:
        ...
```

`SymptomResult` should include:

- detected labels
- confidence or score per label
- evidence spans or matched phrases
- retrieval candidates
- reranker scores
- safety overrides applied
- latency breakdown
- model metadata

Adapters:

- Deterministic dictionary.
- TF-IDF baseline, rebuilt from active datasets.
- MiniLM current baseline.
- Qwen3-Embedding.
- BGE-M3.
- Jina Embeddings v3.
- Qwen3-Reranker.
- Hybrid embedding + reranker.

### Phase 6: Frontend Decomposition

Goal: reduce the giant consultation template.

Current issue:

- `web/templates/pos/consultation.html` contains large inline CSS, UI state logic, consultation flow, checkout, fingerprint, and payment logic.

Recommended split:

- `consultation.html`: structure only.
- `web/static/css/consultation.css`
- `web/static/js/consultation/state.js`
- `web/static/js/consultation/api.js`
- `web/static/js/consultation/severity.js`
- `web/static/js/consultation/duration.js`
- `web/static/js/consultation/recommendations.js`
- `web/static/js/consultation/checkout.js`

No behavior should change in the first split.

## Modern Retrieval Modernization

Recommended pipeline:

```text
Input text
  -> normalization
  -> deterministic red-flag triage
  -> deterministic symptom extraction
  -> semantic retrieval only for missing/low-confidence cases
  -> optional reranking of top candidates
  -> deterministic safety and contraindication filters
  -> safe OTC recommendation
```

Key modernization principle:

The model can improve retrieval recall, but it must never override:

- red flags
- contraindications
- age limits
- duration limits
- inventory/SKU constraints
- no-diagnosis policy

## Dependency Modernization

Current production requirements include:

- `sentence-transformers`
- `torch`
- `transformers<4.37`

New Qwen3 model cards indicate newer Transformers support may be required. Before adding Qwen3 locally, create a separate experiment environment or lockfile so the current demo does not break.

Recommended setup:

- `requirements.txt`: active stable app.
- `requirements-experiments.txt`: Qwen/BGE/Jina benchmarking dependencies.
- `requirements-pi.txt`: Raspberry Pi CPU-only runtime.
- `requirements-dev.txt`: tests, linting, report generation.

## Benchmark Modernization

Add a benchmark harness that records:

- symptom exact match
- micro/macro F1
- per-label recall
- top-k retrieval recall
- MRR
- nDCG
- red-flag sensitivity
- safety override pass rate
- false recommendation rate
- latency p50/p95
- cold-start time
- RAM usage
- model size on disk
- CPU utilization on Raspberry Pi

Each run should save:

- git commit hash
- model name and revision
- dataset version hash
- threshold values
- device and quantization
- dependency versions

## Cleanup Strategy for "Trash Code and Docs"

Recommended order:

1. Do not delete anything until a branch is created and the active source map is confirmed.
2. Mark active vs legacy files.
3. Move legacy code to `legacy/` or external archive.
4. Remove generated files from git tracking.
5. Restore missing hardware source.
6. Split large modules without behavior changes.
7. Add regression tests after each split.
8. Only then modernize NLP experiments.

## Suggested Branch Plan

1. `cleanup/repo-hygiene`
2. `refactor/hardware-source-restore`
3. `refactor/medicine-sku-schema`
4. `refactor/nlp-interfaces`
5. `experiment/retrieval-reranker-baselines`
6. `deploy/pi-runtime-optimization`

## Sources

- Qwen3 Embedding model cards: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B and https://huggingface.co/Qwen/Qwen3-Embedding-8B
- Qwen3 Reranker model card: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
- BGE-M3 model card: https://huggingface.co/BAAI/bge-m3
- Jina Embeddings v3 documentation: https://jina.ai/news/jina-embeddings-v3-a-frontier-multilingual-embedding-model/
- Current MiniLM baseline: https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
