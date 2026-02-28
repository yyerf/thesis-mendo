# Training — MendoVendo V3

This folder contains all **model training scripts** only. Benchmark and evaluation scripts are in [`benchmarks/`](../benchmarks/).

---

## Scripts

| Script | Purpose |
|---|---|
| `train_sentence_transformer.py` | Fine-tune `paraphrase-multilingual-MiniLM-L12-v2` on symptom sentence pairs |
| `train_symptom_classifier.py` | Train TF-IDF + One-vs-Rest Logistic Regression multi-label classifier |
| `clean_dataset.py` | Remove entries with unknown/invalid labels from JSONL datasets |
| `generate_synthetic_dataset.py` | Generate synthetic training entries from templates |
| `validate_dataset.py` | Validate JSONL format and label correctness |
| `convert_testing_csv_to_jsonl.py` | Convert CSV test cases to JSONL format |

---

## 1. Fine-Tune Sentence Transformer (Step 2)

Adapts `paraphrase-multilingual-MiniLM-L12-v2` to the Filipino medical symptom domain using CosineSimilarityLoss.

**Dataset:** `data/datasets/st_pairs.sample.jsonl` (252 sentence pairs, label=1 for same symptom, label=0 for different)

```bash
python training/train_sentence_transformer.py \
  --train data/datasets/st_pairs.sample.jsonl \
  --out models/mendo-miniLM-finetuned \
  --epochs 4 \
  --batch-size 16 \
  --warmup-steps 50
```

**Hyperparameters (for paper):**
- Loss: `CosineSimilarityLoss`
- Epochs: 4
- Batch size: 16
- Warmup steps: 50
- Optimizer: AdamW (library default)
- Learning rate: 2×10⁻⁵ (library default)

**Use the fine-tuned model:**
```bash
export MENDO_SENTENCE_TRANSFORMER_MODEL=models/mendo-miniLM-finetuned
python app.py
```

---

## 2. Train Symptom Classifier (ML Component)

Trains a supervised multi-label text classifier: **TF-IDF features + One-vs-Rest Logistic Regression**.

This is the "real ML" component for thesis requirements — a trained model, not just pretrained inference.

**Dataset format (JSONL):**
```json
{"id": "ex001", "text": "Ubo at lagnat", "labels": ["cough", "fever"]}
```

Labels must match the 15 canonical labels in [`mendo_core/symptom_models.py`](../mendo_core/symptom_models.py).

```bash
python training/train_symptom_classifier.py \
  --data data/datasets/symptom_eval.whole.jsonl \
  --model-out training/symptom_classifier.joblib
```

**Outputs:**
- `training/symptom_classifier.joblib` — trained model artifact
- `training/symptom_classifier_metrics.json` — precision/recall/F1 per label

---

## 3. Dataset Utilities

**Clean unknown labels:**
```bash
python training/clean_dataset.py --data data/datasets/symptom_eval.sample.jsonl
```

**Generate synthetic entries:**
```bash
python training/generate_synthetic_dataset.py \
  --out data/datasets/symptom_eval.synthetic.jsonl \
  --max 300
```

**Validate a dataset:**
```bash
python training/validate_dataset.py --data data/datasets/symptom_eval.whole.jsonl
```

**Convert CSV test cases to JSONL:**
```bash
python training/convert_testing_csv_to_jsonl.py \
  --in testing/testing.csv \
  --out data/datasets/symptom_eval.from_testing.jsonl
```

---

## Dataset Sizes (current)

| File | Entries | Description |
|---|---|---|
| `symptom_eval.whole.jsonl` | 2,170 | Full evaluation corpus |
| `symptom_eval.synthetic.jsonl` | 1,800 | Synthetic (negation, abbreviation, multi-symptom) |
| `symptom_eval.sample.jsonl` | 70 | Hand-curated seed |
| `symptom_eval.user_additions.jsonl` | 20 | Manual additions |
| `st_pairs.sample.jsonl` | 252 | Sentence-pair fine-tuning data |

---

## Thesis Defense Notes

- The **ML classifier** (TF-IDF + LogReg) satisfies the "supervised learning" requirement — it is trained on labeled data, not just using pretrained embeddings.
- The **fine-tuned MiniLM** satisfies the "domain adaptation" requirement — the pretrained model is further trained on Filipino medical sentence pairs.
- Both are complementary: rules handle safety-critical phrases, ML improves recall on paraphrased/noisy inputs.
