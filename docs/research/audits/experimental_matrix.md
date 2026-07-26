# Experimental NLP Comparison Matrix

Research goal: compare modern retrieval and reranking architectures for multilingual OTC symptom interpretation without allowing diagnosis or unrestricted medical advice.

## Research Question

Can modern multilingual embedding and reranking models improve symptom-intent retrieval for English, Filipino, Bisaya/Cebuano, and mixed-language OTC consultation inputs while preserving deterministic safety consistency and low-latency Raspberry Pi deployment?

## Task Definition

This is not disease diagnosis.

The task is:

- Input: user symptom text.
- Output: one or more allowed symptom intent labels.
- Optional output: evidence anchors, scores, and safe OTC recommendation candidates.
- Forbidden output: disease labels, diagnostic claims, unrestricted treatment advice.

## Baselines

| ID | Method | Runtime role | Notes |
| --- | --- | --- | --- |
| B0 | Deterministic dictionary | Primary safety-preserving baseline | Active `step1.py`; fastest and most explainable. |
| B1 | Legacy TF-IDF/SVM | Historical comparison | Present in `_For-Mendo/`; must be rebuilt into active harness for fair comparison. |
| B2 | TF-IDF cosine retrieval | Classical IR baseline | Build symptom anchor corpus and retrieve by TF-IDF cosine. |
| B3 | MiniLM multilingual embeddings | Current semantic fallback | Active `step2.py`; compare with current threshold 0.65. |

## Modern Candidate Models

| ID | Model | Role | Local Pi feasibility | Expected strength | Main risk |
| --- | --- | --- | --- | --- | --- |
| E1 | Qwen3-Embedding-0.6B | Embedding retrieval | Possible only with careful CPU quantization and small top-k | Strong multilingual semantic matching | Larger and slower than MiniLM. |
| E2 | Qwen3-Embedding-4B/8B | Embedding retrieval | Server-side preferred | Higher semantic quality | Not realistic for Pi-only latency. |
| R1 | Qwen3-Reranker-0.6B | Rerank top-k candidates | Possible for very small k, but benchmark first | Better precision after retrieval | Cross-encoder reranking latency. |
| R2 | Qwen3-Reranker-4B/8B | Rerank top-k candidates | Server-side only | High precision | Too heavy for local kiosk. |
| E3 | BGE-M3 | Dense/sparse/multi-vector retrieval | Potentially heavy but worth CPU benchmark | Multilingual, multi-function retrieval | More complex scoring modes and memory. |
| E4 | Jina Embeddings v3 | Embedding retrieval | Benchmark required; likely server or optimized CPU | Multilingual, long-context, task adapters | Model/runtime complexity for Pi. |
| H1 | MiniLM -> Qwen3-Reranker-0.6B | Hybrid | Maybe top-3 only | Keeps cheap retrieval, improves precision | Reranker latency. |
| H2 | Qwen3-Embedding-0.6B -> Qwen3-Reranker-0.6B | Hybrid | Pi experiment only; server likely better | Strong semantic + precision | Too slow locally unless quantized. |
| H3 | BGE-M3 -> Qwen3-Reranker | Hybrid | Server-side preferred | Robust multilingual retrieval plus rerank | Operational complexity. |
| H4 | Deterministic + MiniLM/Qwen/BGE/Jina fallback | Safety-first hybrid | Best practical thesis design | Deterministic precision plus semantic recall | Needs careful fallback triggers. |

## Candidate Pipelines

### Pipeline P0: Current Active System

```text
red-flag rules -> dictionary -> MiniLM semantic fallback -> lexical guard -> deterministic recommendation
```

Use as the main production baseline.

### Pipeline P1: Deterministic + TF-IDF

```text
red-flag rules -> dictionary -> TF-IDF anchor retrieval -> lexical guard -> deterministic recommendation
```

Purpose: classic IR baseline.

### Pipeline P2: Deterministic + Embedding Retrieval

```text
red-flag rules -> dictionary -> embedding top-k symptom retrieval -> threshold -> safety filters -> recommendation
```

Run with:

- MiniLM
- Qwen3-Embedding-0.6B
- BGE-M3
- Jina Embeddings v3

### Pipeline P3: Embedding + Reranker

```text
red-flag rules -> dictionary -> embedding top-k -> reranker -> threshold -> safety filters -> recommendation
```

Run with:

- MiniLM retrieval + Qwen3-Reranker-0.6B
- Qwen3-Embedding-0.6B + Qwen3-Reranker-0.6B
- BGE-M3 + Qwen3-Reranker-0.6B
- Jina v3 + Qwen3-Reranker-0.6B

### Pipeline P4: Safety-Gated Augmentation

```text
red-flag rules -> dictionary partial detection -> semantic retrieval only for missing secondary symptoms -> reranker -> safety filters
```

Purpose: test whether semantic models can add missed secondary symptoms without increasing false positives.

## Dataset Design

### Existing Datasets

- `testing/benchmark/testing.csv`: 288 labeled cases.
- `testing/test_regressions.py`: safety and behavior tests.
- `data/datasets/symptom_eval.sample.jsonl`: small lower-case label benchmark.

### Proposed Gold Dataset

Create `data/eval/mendo_symptom_gold_v1.jsonl`:

```json
{"id":"ceb_001","text":"labad kaayo akong ulo ug gihilantan ko","labels":["HEADACHE","FEVER"],"language":"ceb","phenomena":["bisaya","multi_symptom"],"red_flags":[]}
```

Required fields:

- `id`
- `text`
- `labels`
- `language`
- `phenomena`
- `red_flags`
- `expected_action`
- `age`
- `conditions`
- `notes`

Suggested split:

- 60 percent development
- 20 percent validation
- 20 percent locked thesis test

Do not tune thresholds on the locked test set.

## Evaluation Dimensions

Language and input quality:

- English
- Filipino/Tagalog
- Bisaya/Cebuano
- Taglish
- Bislish
- Jejemon/noisy text
- Typos and abbreviations
- STT transcription noise

Clinical safety phenomena:

- Red flags
- Negation
- Partial negation
- Blood-context disambiguation
- Pregnancy and proxy-purchase context
- Hypertension context
- Duration limits
- Age limits
- Contraindications

Retrieval phenomena:

- Direct symptom phrase
- Paraphrase
- Metaphor
- Multi-symptom
- Ambiguous cough
- Ambiguous stomach ache
- Ambiguous runny nose
- Low-resource regional variants

## Metrics

Symptom interpretation:

- exact match accuracy
- micro precision, recall, F1
- macro F1
- per-label recall
- false-positive rate
- false-negative rate
- top-k recall before reranking
- MRR
- nDCG@k

Recommendation:

- correct recommendation set recall
- inappropriate recommendation rate
- no-match appropriateness
- clarification appropriateness
- age-filter pass rate
- contraindication filter pass rate

Safety:

- red-flag sensitivity
- red-flag false negative count
- deterministic override pass rate
- unsafe OTC leakage count
- diagnosis leakage count, expected 0
- hallucinated medicine count, expected 0

Latency and deployment:

- cold start time
- warm p50 latency
- warm p95 latency
- peak RAM
- model size on disk
- CPU utilization
- tokens/second or pairs/second for rerankers

Explainability:

- evidence coverage rate
- matched phrase availability
- best anchor availability
- reranker score availability
- safety reason availability

## Experimental Matrix

| Exp | First-stage safety | Retrieval | Reranker | Candidate corpus | Primary metrics |
| --- | --- | --- | --- | --- | --- |
| X00 | On | Dictionary only | None | Dictionary phrases | Exact match, safety pass, latency |
| X01 | On | TF-IDF cosine | None | Symptom anchors | F1, typo robustness, latency |
| X02 | On | MiniLM | None | Symptom anchors | F1, multilingual robustness |
| X03 | On | Qwen3-Embedding-0.6B | None | Symptom anchors | F1, latency, Pi feasibility |
| X04 | On | BGE-M3 dense | None | Symptom anchors | F1, low-resource robustness |
| X05 | On | BGE-M3 hybrid modes | None | Symptom anchors | Recall, precision, explainability |
| X06 | On | Jina v3 | None | Symptom anchors | Multilingual robustness |
| X07 | On | MiniLM | Qwen3-Reranker-0.6B | Top 10 symptom candidates | Precision, latency |
| X08 | On | Qwen3-Embedding-0.6B | Qwen3-Reranker-0.6B | Top 10 symptom candidates | F1, latency, safety |
| X09 | On | BGE-M3 | Qwen3-Reranker-0.6B | Top 10 symptom candidates | Robustness, safety |
| X10 | On | Jina v3 | Qwen3-Reranker-0.6B | Top 10 symptom candidates | Robustness, rerank gain |
| X11 | On | MiniLM/Qwen fallback only if dictionary empty | Optional reranker | Symptom anchors | Production suitability |
| X12 | On | Semantic augmentation of partial dictionary result | Optional reranker | Missing-symptom anchors | Secondary symptom recall vs false positives |

## Candidate Corpus Design

Each candidate document should represent one symptom intent, not a disease.

Example:

```json
{
  "candidate_id": "SYMPTOM:COUGH_PRODUCTIVE",
  "label": "COUGH_PRODUCTIVE",
  "title": "cough with phlegm",
  "anchors": [
    "I have cough with phlegm",
    "ubo na may plema",
    "ubo na naay plema"
  ],
  "allowed_recommendation_scope": ["expectorant"],
  "forbidden_behavior": ["diagnose pneumonia", "diagnose TB"]
}
```

Medicine candidates should use approved indication snippets from the ASG dataset, not generated text.

## Benchmark Protocol

1. Freeze the dataset.
2. Freeze model revisions.
3. Precompute candidate embeddings.
4. Warm up each model before warm-latency measurements.
5. Measure cold start separately.
6. Run each experiment on:
   - development laptop
   - Raspberry Pi CPU
   - optional server GPU/CPU
7. Save all configs and metrics.
8. Compare using confidence intervals, bootstrap resampling, and McNemar tests for paired exact-match differences.

## Safety Consistency Test

Every model output must pass a final deterministic safety gate.

Required safety assertions:

- If red flag is detected, no OTC recommendation is emitted.
- If duration exceeds threshold, no OTC recommendation for that symptom is emitted.
- If age is below minimum age, that SKU is not recommended.
- If hypertension is detected, systemic decongestant products are blocked.
- If pregnancy is detected for the patient, OTC selection requires pharmacist guidance.
- If semantic model predicts a symptom contradicted by negation, the symptom is removed.
- No model may output diagnosis text.

## Low-Resource Language and Typo Augmentation

Generate controlled variants from each gold example:

- Cebuano/Bisaya substitutions.
- Tagalog substitutions.
- Code-switch insertion.
- Jejemon character noise.
- Common phone keyboard typos.
- Vowel-dropping abbreviations.
- STT homophone-like substitutions.
- Word-order changes.

All augmented data must preserve labels and safety flags through human review for the locked evaluation set.

## Reporting Template

Each experiment report should include:

- model and revision
- quantization/runtime
- candidate corpus version
- thresholds
- exact/micro/macro metrics
- per-language metrics
- per-phenomenon metrics
- safety failures
- p50/p95 latency
- RAM
- top failure examples
- recommendation impact

## Sources

- Qwen3 Embedding model cards: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B and https://huggingface.co/Qwen/Qwen3-Embedding-8B
- Qwen3 Reranker model card: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
- BGE-M3 model card: https://huggingface.co/BAAI/bge-m3
- Jina Embeddings v3 documentation: https://jina.ai/news/jina-embeddings-v3-a-frontier-multilingual-embedding-model/
- Current MiniLM baseline: https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
