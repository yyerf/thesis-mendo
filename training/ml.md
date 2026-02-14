# ML Component (Thesis Summary)

## What ML did we add?
We added a **supervised multi‑label text classifier** that predicts symptom labels directly from a sentence.

**Model:** TF‑IDF text features + One‑Vs‑Rest Logistic Regression (scikit‑learn).  
**Labels:** Canonical Mendo labels (15 symptoms).  
**Output:** One or more symptom labels per input.

This is a **trained** model (not just a pretrained encoder), so it satisfies the “real ML” requirement for a CS thesis.

---

## How it works (simple explanation)
1) Convert each sentence into a vector using **TF‑IDF** (word + phrase statistics).  
2) Train one classifier per label (One‑Vs‑Rest).  
3) For a new sentence, each classifier outputs a probability.  
4) If the probability ≥ threshold, that label is predicted.

In short: **“Text → TF‑IDF vector → Logistic Regression → Multi‑label symptoms.”**

---

## Why this is better (and how it complements Mendo core)
**Mendo core (rules) is strong** for common phrases and safety‑critical cases.  
**The ML model helps** when users use **slang, paraphrases, or unusual wording** that rules miss.

So the final design is a **hybrid**:
- **Rules first** = fast + predictable + safe
- **ML model** = better recall on flexible language

This matches a strong thesis argument: **robustness + interpretability**.

---

## Where the ML code lives
- Training: [training/train_symptom_classifier.py](training/train_symptom_classifier.py)
- Benchmark: [training/benchmark_ml_vs_rules.py](training/benchmark_ml_vs_rules.py)
- Interactive compare (ML vs Core): [training/compare_models_cli.py](training/compare_models_cli.py)

---

## How to explain it in defense (short script)
“We trained a supervised multi‑label classifier using TF‑IDF features and One‑Vs‑Rest Logistic Regression. It predicts symptom labels from free text. We compare it against our rule‑based Mendo core and show that ML improves recall on paraphrased or noisy inputs, while rules keep the system safe and interpretable.”
