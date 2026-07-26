# Mendo Retrieval Benchmark Suite

This directory is an isolated research benchmark suite for thesis experiments. It does not change the production Mendo V3 kiosk flow.

## Purpose

Compare symptom interpretation and retrieval pipelines for multilingual OTC assistance:

- deterministic dictionary baseline
- TF-IDF cosine retrieval
- current MiniLM hybrid fallback
- optional modern embedding models
- optional embedding + reranker pipelines

The benchmark keeps safety deterministic. Models only propose symptom labels; red flags, contraindications, age, duration, and recommendation rules remain rule-based.

## Quick Start

Run lightweight baselines that do not download large models:

```bash
python3 experiments/retrieval_benchmark/run_benchmark.py \
  --models dictionary,tfidf_word,tfidf_char \
  --dataset testing/benchmark/testing.csv
```

Run with cough clarification simulation, matching the older thesis benchmark style:

```bash
python3 experiments/retrieval_benchmark/run_benchmark.py \
  --models dictionary,tfidf_word,tfidf_char \
  --dataset testing/benchmark/testing.csv \
  --apply-clarification
```

Output is written to:

```text
experiments/retrieval_benchmark/results/run_YYYYMMDD_HHMMSS/
  summary.json
  predictions.csv
  report.md
```

## Optional Modern Models

These can download large models and may be slow on CPU:

```bash
python3 experiments/retrieval_benchmark/run_benchmark.py \
  --models dictionary,tfidf_char,minilm \
  --dataset testing/benchmark/testing.csv \
  --limit 30
```

Modern model registry names:

- `minilm`: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- `qwen3_embedding_0_6b`: `Qwen/Qwen3-Embedding-0.6B`
- `bge_m3`: `BAAI/bge-m3`
- `jina_v3`: `jinaai/jina-embeddings-v3`
- `minilm_qwen3_rerank`: MiniLM retrieval + `Qwen/Qwen3-Reranker-0.6B`

Use modern models on a small `--limit` first. If a model cannot load, the runner skips it and records the reason.

Detailed experiment notes:

- [Model dictionary](docs/model_dictionary.md)
- [Experiment diary](docs/experiment_diary.md)

## Metrics

The suite reports:

- exact match accuracy
- micro precision, recall, F1
- macro F1
- per-language accuracy and F1
- per-category F1
- per-label precision, recall, F1
- latency p50/p95
- recommendation action counts
- red-flag override leakage count
- top failures

## Important Thesis Note

There are two valid benchmark modes:

1. Raw NLP mode: do not pass `--apply-clarification`.
2. Clarified flow mode: pass `--apply-clarification` to simulate the user answering cough clarification.

Report both when possible. Raw mode is fairer for pure model comparison. Clarified mode is fairer for the full Mendo kiosk workflow.

If the CSV includes a `language` column, reports include per-language metrics. Without that column, examples are grouped under `unspecified`.

## Safety Policy

Every adapter returns only approved symptom labels. It cannot output diagnosis text or invented medicines. The runner passes detected red flags into the existing deterministic recommendation engine, so red-flag cases should never produce OTC recommendations.
