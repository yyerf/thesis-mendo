# Training Guide — Supervised ML Symptom Classifier

This guide explains how to train the thesis‑ready ML model in this folder, using the same symptom labels defined in Mendo core.

## What this adds
A **trained multi‑label classifier** (TF‑IDF + One‑Vs‑Rest Logistic Regression) that predicts symptom labels from text. This is a real ML component trained on your dataset (not just pretrained inference).

## Dataset format
Use JSONL with one object per line:
```json
{"id":"ex001","text":"Ubo at lagnat","labels":["cough","fever"]}
```

Labels must match the canonical list in [data/datasets/README.md](../data/datasets/README.md) and [mendo_core/symptom_models.py](../mendo_core/symptom_models.py).

## Quick start
You can run this from any folder. Paths are resolved relative to the workspace root.

1) Prepare/expand your dataset:
- Start with [data/datasets/symptom_eval.sample.jsonl](../data/datasets/symptom_eval.sample.jsonl)
- Grow it using [data/datasets/symptom_eval.template.jsonl](../data/datasets/symptom_eval.template.jsonl)

2) Train:
```
python training/train_symptom_classifier.py \
  --data data/datasets/symptom_eval.sample.jsonl \
  --model-out training/symptom_classifier.joblib
```

3) Outputs:
- Model file: `training/symptom_classifier.joblib`
- Metrics file: `training/symptom_classifier_metrics.json`

---

## Clean dataset (canonical labels only)
If your JSONL has unknown labels, clean it first:
```
python training/clean_dataset.py --data data/datasets/symptom_eval.sample.jsonl
```
This rewrites the file and creates a `.bak` backup.

---

## Generate more data
1) Prompt templates for AI generation are in [training/dataset_prompts.md](training/dataset_prompts.md)
2) Synthetic generator (canonical labels only):
```
python training/generate_synthetic_dataset.py --out data/datasets/symptom_eval.synthetic.jsonl --max 300
```

---

## Benchmark ML vs Mendo core
```
python training/benchmark_ml_vs_rules.py \
  --data data/datasets/symptom_eval.from_testing.jsonl \
  --model training/symptom_classifier.joblib
```
This prints metrics and saves JSON to `testing/benchmark/results/benchmark_ml_vs_rules.json`.

---

## Compare outputs (interactive)
```
python training/compare_models_cli.py --model training/symptom_classifier.joblib
```
Type any sentence to see **ML vs Mendo core** predictions.

## Interpreting results
- Look at **micro F1** (overall performance)
- Look at **macro F1** (performance across all labels)
- Compare against the **baseline_rules** (rule‑based) and **baseline_hybrid** (Step 3 hybrid) scores

## How to describe this in defense
- “We trained a supervised multi‑label classifier for symptom detection.”
- “The model uses TF‑IDF features and One‑Vs‑Rest Logistic Regression.”
- “We evaluated using precision, recall, and F1, and compared against our rule‑based baseline from Mendo core.”

## Next (optional)
- Replace TF‑IDF with a fine‑tuned multilingual transformer for higher accuracy.
- Integrate the trained classifier into Step 3 as a new ML stage before rules.
