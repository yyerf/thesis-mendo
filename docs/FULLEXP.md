# Full Simple Explanation (Thesis Guide)

## 1) What this system is (very simple)

Your project is a **hybrid symptom-to-OTC recommendation system**.

It does this flow:
1. User enters symptoms (Tagalog / Bisaya / English / Taglish)
2. System detects symptoms
3. System applies safety checks (age, allergy, risk rules)
4. System recommends OTC medicine
5. System shows explanation (why this medicine)

So your system is **AI + rules**, not AI-only.

---

## 2) Main technologies in your project

- **Flask**: web backend + routes + templates
- **Rule-based NLP**: dictionaries/regex for direct symptom matching
- **Sentence-Transformers**: semantic fallback when exact words are not matched
- **Trained ML classifier**: TF-IDF + One-vs-Rest Logistic Regression (multi-label)
- **Deterministic recommendation logic**: medicine ranking/filtering based on rules and dataset
- **Optional Whisper STT**: speech-to-text (offline)

---

## 3) PRISMA in your paper (why important)

**PRISMA** is for systematic literature review quality.

It proves that:
- you searched studies systematically,
- you filtered papers using clear criteria,
- your final model choices are evidence-based.

So PRISMA supports your **research methodology** and reduces selection bias.

---

## 4) Algorithm vs Model (easy distinction)

- **Algorithm** = learning method (example: Logistic Regression, SVM, BERT)
- **Model** = trained result after feeding data to an algorithm

Think:
- Algorithm = recipe
- Model = cooked food

---

## 5) What models you are actually using now

### A) Semantic fallback model
You are using:
- `paraphrase-multilingual-MiniLM-L12-v2` through Sentence-Transformers

This is used in Step 2 as a semantic matcher (embedding similarity), not full supervised retraining.

### B) Trained symptom classifier
You trained:
- **TF-IDF + One-vs-Rest Logistic Regression**

This is your true trained ML component for symptom detection.

### C) Recommendation engine
- Rule-based and deterministic
- Includes practical safety checks and explainable reasons

---

## 6) Is Sentence-Transformers better than BERT?

Short answer: **depends on task and resources**.

### When Sentence-Transformers is better
- You need sentence similarity/semantic matching quickly
- You want lower compute cost
- You want practical deployment
- You have limited labeled training data

### When fine-tuned BERT can be better
- You have enough high-quality labeled data
- You can train/tune properly (usually GPU)
- You optimize for maximum classification performance

So: no universal winner.
- For practical semantic matching: Sentence-Transformers is often best value.
- For top-end supervised classification: fine-tuned BERT can outperform.

---

## 7) Your actual benchmark result (no bias)

From your latest benchmark run on 100-case evaluation:

- **ML (trained classifier)**
  - micro-F1: **0.9407**
  - precision: **0.8880**
  - recall: **1.0000**

- **Hybrid baseline**
  - micro-F1: **0.8713**

- **Rules baseline**
  - micro-F1: **0.7619**

Interpretation:
- If your main metric is overall detection (micro-F1), **trained ML wins**.
- If your priority is strictness/precision, rules/hybrid can be stricter but miss more positives.

---

## 8) Best architecture for your thesis

The strongest thesis-ready architecture for your current project is:

1. **Primary symptom detector**: trained ML classifier (best detection performance)
2. **Safety layer**: rule-based constraints/clinical checks
3. **Recommendation layer**: deterministic logic from medicine dataset
4. **Explainability**: reason codes and optional model explanation (e.g., LIME/SHAP)

Why this is best:
- high performance,
- practical deployment,
- safer behavior,
- easier panel defense.

---

## 9) Defense-ready one-liner

> “We implemented a hybrid architecture: a trained multi-label symptom classifier for robust detection, combined with rule-based clinical safeguards and deterministic OTC recommendation for safety and interpretability.”

---

## 10) Very short answer if panel asks “Which is better?”

- In your benchmark, **your trained ML model is better** for symptom detection.
- In real healthcare-like use, **hybrid (ML + rules) is best overall** because it balances accuracy, safety, and explainability.
