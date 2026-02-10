# Models, Algorithms, and ML in the Current Flow

## High-level flow
1. Input text (typed or speech→text)
2. Hybrid symptom extraction
3. Rule-based OTC recommendation
4. UI output

---

## Step 1 — Deterministic rules (no ML)
**What it is:** Dictionary + regex matching, normalization, negation handling, and rule-based cough typing.

**Type:** Rule-based information extraction (no training).

**Where:** [mendo_core/step1.py](mendo_core/step1.py)

---

## Step 2 — Semantic embeddings (ML, no training)
**What it is:** Sentence embeddings + cosine similarity vs. “anchor” phrases per symptom.

**Model:** `SentenceTransformer` with `paraphrase-multilingual-MiniLM-L12-v2`.

**Type:** Pretrained Transformer encoder (deep learning) used only for inference.

**Where:** [mendo_core/step2.py](mendo_core/step2.py)

---

## Step 3 — Hybrid cascade (rules → ML fallback)
**What it is:** Run Step 1 first; only if it finds nothing, run Step 2.

**Type:** System design that mixes deterministic rules and ML.

**Where:** [mendo_core/step3_hybrid.py](mendo_core/step3_hybrid.py)

---

## Step 4 — Recommendation (no ML)
**What it is:** Rule-based scoring/filters over the OTC dataset; includes cough clarification.

**Type:** Deterministic recommender (not trained).

**Where:** [mendo_core/step4_recommend.py](mendo_core/step4_recommend.py)

---

## Optional ML: Offline Speech-to-Text
**What it is:** Whisper for speech transcription, then the same NLP pipeline.

**Type:** Deep learning ASR.

**Where:** [web/app.py](web/app.py), [tools/stt.py](tools/stt.py)

---

# Draft: Why We Add a Trained ML Model (Thesis Rationale)

Because this is a Computer Science thesis, we should include at least one **trained ML model** (not just a pretrained model used for inference). The best fit is a **supervised multi‑label symptom classifier** trained on our labeled sentences. This makes the system both academically credible and measurable.

## Proposed ML Component
**Model:** Multilingual transformer fine‑tuned for multi‑label classification (e.g., MiniLM/DistilBERT).  
**Input:** User sentence.  
**Output:** One or more symptom labels.  

This turns the pipeline into a true ML system because the model is trained on our dataset and evaluated with standard metrics.

## How It Fits the Current Flow
1. **ML classifier first** → predicts symptoms.  
2. **Rule‑based Step 1** → serves as a safety net for rare edge cases.  
3. **Recommendation** remains deterministic for safety and explainability.  

This keeps the system robust and interpretable while still meeting the “ML requirement.”

## Evaluation Plan (Defense‑ready)
- **Dataset split:** train/validation/test.  
- **Metrics:** precision, recall, F1 (multi‑label).  
- **Baseline:** current rule‑based pipeline.  
- **Claim:** the trained model improves recall on paraphrases and noisy input while rules preserve safety.

## Thesis Statement (Draft)
“We integrated a supervised multilingual symptom classifier into a hybrid pipeline. The model is trained on labeled symptom sentences, evaluated with multi‑label F1, and deployed with rule‑based safeguards to ensure safety and interpretability.”
