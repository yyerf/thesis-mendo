# Benchmarks — MendoVendo V3

All evaluation and comparison scripts. Results are saved to `benchmarks/results/`.

---

## Scripts

| Script | What It Measures | Run From |
|---|---|---|
| `benchmark_full.py` | End-to-end pipeline accuracy (Steps 1–4): symptom detection + drug recommendation across 16 test levels | Project root |
| `benchmark_semantic_models.py` | Semantic model comparison: F1/recall at each cosine threshold (0.40–0.85) across MiniLM, LaBSE, MPNet, TF-IDF | Project root |
| `benchmark_ml_vs_rules.py` | ML classifier vs rule-based baseline: precision/recall/F1 per symptom label | Project root |
| `benchmark_pipeline.py` | Per-label symptom extraction metrics across all available models | Project root |
| `compare_models_cli.py` | Interactive CLI: type a sentence, see ML vs rule-based predictions side by side | Project root |

---

## 1. End-to-End Pipeline Benchmark

Tests all 16 difficulty levels from basic symptom detection to red flags, safety, negation, and contraindications.

```bash
python benchmarks/benchmark_full.py
```

**Output:** `benchmarks/results/benchmark_YYYYMMDD_HHMMSS.csv` + `benchmark_summary_*.json`

---

## 2. Semantic Model Comparison

Threshold sweep (0.40–0.85) to find the F1-maximizing cosine similarity cutoff. Core evaluation for thesis Section 3.7.

```bash
python benchmarks/benchmark_semantic_models.py \
  --dataset data/datasets/st_pairs.sample.jsonl \
  --th-start 0.40 --th-stop 0.85 --th-step 0.05

# Skip re-computing embeddings (use cached):
python benchmarks/benchmark_semantic_models.py \
  --dataset data/datasets/st_pairs.sample.jsonl \
  --skip-embeddings
```

**Latest results:**

| Model | Best F1 | Recall | Inference |
|---|---|---|---|
| MiniLM-L12-v2 | 0.409 | 0.460 | ~4.6ms |
| MPNet-base-v2 | 0.335 | 0.390 | ~14.5ms |
| LaBSE | 0.550 | 0.910 | ~13ms |

> MiniLM is used in production (RPi5 constraint: 90MB RAM vs LaBSE's ~1.8GB).

---

## 3. ML vs Rules Benchmark

Compares the TF-IDF + Logistic Regression classifier against the rule-based Mendo core.

```bash
python benchmarks/benchmark_ml_vs_rules.py \
  --data data/datasets/symptom_eval.from_testing.jsonl \
  --model training/symptom_classifier.joblib
```

**Output:** `benchmarks/results/benchmark_ml_vs_rules.json`

---

## 4. Per-Label Pipeline Benchmark

Runs precision/recall/F1 per symptom label for any model registered in `mendo_core/symptom_models.py`.

```bash
# Rules only
python benchmarks/benchmark_pipeline.py \
  --dataset data/datasets/symptom_eval.whole.jsonl \
  --model rules

# All registered models
python benchmarks/benchmark_pipeline.py \
  --dataset data/datasets/symptom_eval.whole.jsonl \
  --all-models
```

---

## 5. Interactive Model Comparison

Type any sentence to see predictions from both the ML classifier and Mendo core side-by-side.

```bash
python benchmarks/compare_models_cli.py \
  --model training/symptom_classifier.joblib
```

---

## Results Folder

`benchmarks/results/` contains all historical benchmark output CSVs and JSON summaries. File naming: `benchmark_YYYYMMDD_HHMMSS.csv`.
