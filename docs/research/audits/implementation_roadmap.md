# Implementation Roadmap

This roadmap starts after the analysis phase. No refactor has been applied yet.

## Model Deployment Recommendations

### Realistic Raspberry Pi Local Models

Recommended local production stack:

1. Deterministic dictionary and safety rules.
2. Current MiniLM multilingual fallback.
3. Optional small embedding experiment, only after benchmarking.

Most realistic:

- `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
  - Already integrated.
  - Small enough for local CPU use.
  - Good baseline for multilingual paraphrase fallback.

Possible but must benchmark:

- `Qwen/Qwen3-Embedding-0.6B`
  - Modern multilingual embedding candidate.
  - Likely too slow unoptimized on Pi for every query, but may be acceptable with quantization and top-k caching.

Potentially heavy for Pi:

- `BAAI/bge-m3`
  - Strong multilingual retrieval model with dense, sparse, and multi-vector modes.
  - Benchmark CPU latency and memory before claiming local feasibility.

Likely server-side or optimized-runtime only:

- `jina-embeddings-v3`
  - Strong modern multilingual candidate, but should be validated for local CPU footprint.

Not recommended for local Pi production:

- Qwen3-Embedding-4B/8B
- Qwen3-Reranker-4B/8B
- Large cross-encoder rerankers over more than a tiny top-k

### Reranker Deployment

Pi-local:

- Avoid reranking by default.
- If tested, rerank only top 3 to top 5 candidates.
- Use Qwen3-Reranker-0.6B only as an experiment until latency is measured.

Server-side:

- Qwen3-Reranker-0.6B, 4B, or 8B can be evaluated for improved precision.
- Server results must still pass local deterministic safety filters.

## Quantization Approaches

Recommended order:

1. ONNX Runtime dynamic INT8 for encoder-style embedding models.
2. OpenVINO INT8 for CPU deployment if conversion is stable.
3. PyTorch dynamic quantization for linear layers as a fallback.
4. GGUF or llama.cpp-style runtimes only if the model architecture is supported and benchmarked.
5. Keep FP32/FP16 server versions for quality reference.

Benchmark each quantized model against the unquantized model:

- label exact match change
- per-label F1 change
- safety failure count
- latency improvement
- memory improvement

Do not adopt a quantized model if it creates any red-flag or contraindication safety regression.

## CPU-Only Feasible Setup

Suggested Pi runtime:

```text
Python app
  deterministic rules
  precomputed anchor embeddings
  MiniLM or quantized small embedding model
  SQLite
  serial hardware bridge
```

Recommended runtime controls:

- preload model once
- use one process unless memory allows more
- set model device to CPU
- precompute and cache candidate embeddings
- keep reranker disabled by default
- add a health endpoint for model readiness
- log p50/p95 query time

## Optional Server-Side Models

Use server-side inference only as an optional enhancement:

- Qwen3-Embedding-4B/8B
- Qwen3-Reranker-4B/8B
- BGE-M3 full pipeline
- Jina Embeddings v3

Server policy:

- server may return ranked labels or candidate scores only
- server may not return free-form medical advice
- local deterministic safety layer still runs before and after server results
- if server timeout occurs, use local fallback

## Benchmarking Methodology

### Environment Matrix

Run every major experiment on:

- development machine
- Raspberry Pi CPU
- optional server CPU/GPU

Record:

- CPU model
- RAM
- OS
- Python version
- package versions
- model revision
- quantization
- warm/cold setting

### Latency Protocol

For each model:

1. Measure cold load time.
2. Run 5 warmup queries.
3. Run the full evaluation set.
4. Record per-query latency.
5. Report p50, p90, p95, and max.
6. Report peak RAM.

### Quality Protocol

Use frozen datasets:

- current 288-case benchmark
- regression tests
- new gold multilingual JSONL
- red-flag safety set
- typo/noise set
- STT-noise set

Report:

- exact match
- micro F1
- macro F1
- per-language F1
- per-phenomenon F1
- safety failures
- no-match appropriateness
- clarification correctness

### Safety Protocol

For every experiment:

- run deterministic red-flag tests
- run contraindication tests
- run duration tests
- run age-filter tests
- run no-diagnosis output tests
- run hallucinated medicine tests

Any unsafe recommendation leakage is a release blocker.

## Evaluation Dataset Suggestions

Build these files:

```text
data/eval/
  mendo_symptom_gold_v1.jsonl
  mendo_red_flags_v1.jsonl
  mendo_negation_v1.jsonl
  mendo_typo_noise_v1.jsonl
  mendo_stt_noise_v1.jsonl
  mendo_recommendation_gold_v1.jsonl
```

Minimum target sizes:

- 500 symptom examples
- 150 red-flag examples
- 150 negation examples
- 150 typo/noise examples
- 100 STT-noise examples
- 200 recommendation examples

Each row should include:

- text
- labels
- language
- phenomenon tags
- expected action
- red flags
- age
- conditions
- recommendation expectations
- notes

## Multilingual Augmentation Strategy

Use controlled augmentation, not uncontrolled LLM medical generation.

Allowed augmentation:

- phrase substitution from reviewed lexicons
- word-order variation
- code-switch insertion
- common spelling variants
- jejemon character substitution
- vowel-dropping abbreviations
- keyboard-adjacent typos
- STT-like replacements

Human review required for:

- safety cases
- red flags
- contraindications
- recommendation labels
- locked test set

Keep augmented data tagged so results can be broken down by phenomenon.

## Refactor Roadmap

### Milestone 0: Safety Baseline

- Freeze current behavior.
- Run current regression suite.
- Save benchmark summary.
- Record current latency and memory.

Exit criteria:

- Current tests pass.
- Current benchmark is reproducible.

### Milestone 1: Cleanup Without Behavior Change

- Remove tracked generated files from source control.
- Archive `_For-Mendo/`.
- Move thesis docs into `docs/`.
- Keep active app paths unchanged.

Exit criteria:

- App still starts.
- Tests still pass.
- Git diff is understandable.

### Milestone 2: Restore Hardware Source

- Restore serial bridge source.
- Add config example.
- Add Arduino firmware.
- Add hardware simulator.
- Add tests for dispense command mapping.

Exit criteria:

- `import hardware.serial_bridge` works.
- Simulator can pass checkout/dispense tests.

### Milestone 3: Medicine SKU Schema

- Add SKU identity.
- Migrate inventory away from unique brand.
- Preserve all 24 JSON dataset rows.
- Map SKU to hardware slot.

Exit criteria:

- No dosage-form rows are collapsed.
- Recommendations can select inventory SKU.

### Milestone 4: NLP Interfaces

- Create `SymptomInterpreter` interface.
- Wrap current dictionary and MiniLM pipeline.
- Add TF-IDF baseline adapter.
- Add experiment config format.

Exit criteria:

- Current production output unchanged.
- Benchmarks can run multiple models.

### Milestone 5: Modern Retrieval Experiments

- Add Qwen3-Embedding adapter.
- Add BGE-M3 adapter.
- Add Jina v3 adapter.
- Add Qwen3-Reranker adapter.
- Add hybrid pipelines.

Exit criteria:

- All experiments run from one command.
- Reports include quality, safety, latency, and memory.

### Milestone 6: Pi Deployment Optimization

- Convert chosen model to ONNX/OpenVINO if feasible.
- Quantize.
- Precompute embeddings.
- Add model readiness endpoint.
- Add startup and runtime telemetry.

Exit criteria:

- Pi p95 latency meets thesis target.
- No safety regression.

## Recommended First Refactor After Docs

The safest first refactor is repository hygiene, not NLP logic.

Suggested first branch:

```text
cleanup/repo-hygiene
```

Scope:

- identify active source
- archive legacy code
- remove tracked generated files
- update `.gitignore`
- keep all runtime behavior unchanged

Avoid changing `mendo_core/step*.py` until tests and artifacts are clean.

## Sources

- Qwen3 Embedding model cards: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B and https://huggingface.co/Qwen/Qwen3-Embedding-8B
- Qwen3 Reranker model card: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
- BGE-M3 model card: https://huggingface.co/BAAI/bge-m3
- Jina Embeddings v3 documentation: https://jina.ai/news/jina-embeddings-v3-a-frontier-multilingual-embedding-model/
- Current MiniLM baseline: https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
