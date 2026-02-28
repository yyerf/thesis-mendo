# Training Guide (What to Train, Where It Plugs In)

This project is designed to work **without training** (rules + pretrained embeddings).
If you decide to train, this guide explains:
- what part is worth training,
- where it lives in the code,
- what data you need,
- and how to run it.

## Do you need training?

Usually **no**, if:
- expanding `mendo_core/step1.py` phrases + anchors in `mendo_core/step2.py` fixes most errors,
- you value explainability and deterministic behavior,
- you have limited labeled data.

You consider training when:
- you have many recurring paraphrases/slang that rules/anchors can’t cover cleanly,
- you have enough labeled examples,
- you want better semantic separation between similar symptoms.

## What to train (recommended order)

### 1) Train Step 2 semantic encoder (recommended)
**Train this:** the SentenceTransformer embedding model used by Step 2.

- Code that uses it: [mendo_core/step2.py](mendo_core/step2.py)
- Model type: Transformer sentence embedding model (BERT-style encoder)
- Default base model: `paraphrase-multilingual-MiniLM-L12-v2`

**Why train this?**
- Improves matching for local mixed-language phrasing.
- You still keep Step 1 rules + Step 3 safety constraints.

**How it plugs in**
After training, point runtime to your saved model directory:

```bash
export MENDO_SENTENCE_TRANSFORMER_MODEL=models/mendo-miniLM-finetuned
```

`mendo_core/step2.py` will automatically load that path instead of the base model.

### 2) (Optional) Train a supervised symptom classifier
This is a different approach (multi-label classification). It can outperform anchors, but:
- needs more labeled data,
- is less explainable,
- still requires safety rules.

For this repo, the easiest “classifier path” is not yet wired into the main pipeline.
If you want it, we can add a `step2_classifier.py` and swap it into the hybrid stage.

### 3) Do NOT “train” safety logic
Things like:
- age limits,
- negation (“wala akong fever”),
- cough clarification,
should stay rules/constraints.
Professional systems treat these as **hard constraints**, not learned guesses.

## What data you need for fine-tuning (Step 2)

You need a dataset of sentence pairs with similarity labels.

Format (JSONL), one per line:
```json
{"text1": "sinisipon ako", "text2": "my nose is running", "label": 1}
```

- `label=1` means same/very similar meaning for your symptom mapping.
- `label=0` means different.

Sample file provided:
- [data/datasets/st_pairs.sample.jsonl](data/datasets/st_pairs.sample.jsonl)

## How to run fine-tuning

Install:
```bash
python -m pip install sentence-transformers torch
```

Train:
```bash
python tools/train_sentence_transformer.py \
  --train data/datasets/st_pairs.sample.jsonl \
  --out models/mendo-miniLM-finetuned \
  --epochs 1
```

Use the fine-tuned model in the app:
```bash
export MENDO_SENTENCE_TRANSFORMER_MODEL=models/mendo-miniLM-finetuned
python app.py
```

## What you trained vs what you did NOT train

- ✅ If you run the script above: you **fine-tuned** the semantic embedding model.
- ❌ If you only added anchors/phrases/thresholds: that is **configuration**, not training.
- ❌ Step 1 dictionary is not training.

## Professional recommendation (how to present it)

A defensible production pattern is:
- **ML for candidate understanding** (semantic detection)
- **Rules/constraints for safety** (age, negation, contraindications)
- **Explainability** (traceable reasons)

That’s why this repo is hybrid by design.
