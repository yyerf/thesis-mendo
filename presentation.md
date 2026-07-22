# PRISMA Results & Discussion → Presentation Script (Mapped to Our System)

Use this as **slide content + speaker notes**. The goal is to explain the PRISMA findings in plain language, then show how our implemented pipeline directly responds to the gaps identified in the literature.

---

## Slide 1 — What the literature says (big picture)

**Slide bullets**
- Two main approaches for understanding symptom text
  - Traditional: TF‑IDF / bag‑of‑words
  - Modern: BERT-style contextual embeddings
- High reported accuracy ≠ safe recommendations
- Newer systems shift toward hybrid decision pipelines

**Speaker notes (explain it simply)**
Most prior systems start with the same problem we have: users do not speak in medical terms. They say things like “parang binugbog katawan ko” instead of “myalgia.”

The literature splits into two groups:
- TF‑IDF approaches: treat text like “word counts” (fast, simple, but shallow)
- BERT/embeddings: represent meaning, so they can match lay phrases to clinical concepts (more robust)

But our review highlights: **accuracy alone is not enough**, because recommending OTC drugs has safety consequences.

---

## Slide 2 — TF‑IDF vs BERT: what it means in practice

**Slide bullets**
- TF‑IDF = “keyword frequency signal”
  - Works when users use expected words
  - Fails on paraphrases / mixed languages / slang
- BERT embeddings = “meaning-based similarity”
  - Better at paraphrases
  - Higher risk of plausible but wrong matches without constraints

**Speaker notes**
TF‑IDF is like: if the input contains “sipon” a lot, then it’s probably runny nose. It struggles when users write short, noisy, or unusual phrases.

BERT-style embeddings are stronger because they compare meaning. However, they can also produce confident guesses that sound reasonable but are wrong—especially in short inputs—so you need safety checks and guardrails.

---

## Slide 2.1 — “Did we use BERT?” (defense-friendly clarification)

**Slide bullets**
- We use a **BERT-style Transformer encoder** via SentenceTransformers
- Model used: `paraphrase-multilingual-MiniLM-L12-v2`
- Why not “raw BERT”?
  - Raw BERT is not optimized for sentence-to-sentence similarity without fine-tuning
  - SentenceTransformers are trained specifically for semantic similarity (cosine matching)

**Speaker notes**
If the panel asks “Did you use BERT?”, the accurate answer is: **we use a BERT-style transformer architecture** (MiniLM/SentenceTransformer), not the original BERT masked-language-model directly.

For our design, SentenceTransformers are usually better than “plain BERT” because our Step 2 algorithm is **embedding + cosine similarity**. Classic BERT would require additional fine-tuning or special pooling strategies to achieve the same quality for semantic similarity.

So the claim is:
- We used a **pretrained multilingual transformer optimized for sentence embeddings**, which is the most practical choice for semantic matching without training.

Standard BERT embeddings are not optimized for cosine similarity tasks out-of-the-box. I used SentenceTransformers (SBERT) because it utilizes a Siamese Network architecture to derive semantically meaningful sentence embeddings. This allows the system to accurately measure the distance between the user's spoken intent and the medical anchor phrases without requiring a massive labeled dataset for fine-tuning.

---

## Slide 3 — Popularity Bias (key risk)

**Slide bullets**
- Many systems implicitly recommend what is “most reviewed / most liked”
- Popularity ≠ clinical appropriateness
- Bias becomes dangerous in OTC: wrong drug can harm certain users

**Speaker notes**
Popularity Bias means a model can drift toward recommending brands that appear more often in data (reviews, sales, ratings). That may look accurate in retrospective evaluation, but it is not the same as being clinically correct for the user’s actual symptom profile.

In OTC contexts, “popular” can be actively unsafe for some users (children, contraindications, etc.).

---

## Slide 4 — Our design response: hybrid pipeline (why we built it this way)

**Slide bullets**
- We implement a **hybrid decision pipeline**
  1) Deterministic rules first
  2) Deep learning only as fallback
  3) Recommendation is constrained by dataset fields + safety filters

**Speaker notes (tie directly to our system)**
This maps exactly to our implemented architecture:

1) **Step 1 deterministic extraction** (rule/dictionary matching)
- Transparent and predictable for common phrases
- Handles mixed Tagalog/Bisaya/English with normalization and negation rules

2) **Step 2 semantic embeddings** only when Step 1 fails
- We use a pretrained multilingual SentenceTransformer and anchor sentences
- This gives paraphrase robustness without fully trusting the model

3) **Step 3 lexical guards + negation overrides**
- Even if embeddings suggest a symptom, we require relevant keywords to be present
- We also respect explicit negation like “wala akong fever” or “not sakit ulo”

4) **Step 4 recommendation** is not “most popular drug”
- It is dataset-driven and rule-scored by indication signals
- Then filtered by minimum age
- And it asks a clarifying question when cough type is ambiguous

---

## Slide 5 — “Persistence of Safety Gaps” (what the review criticizes)

**Slide bullets**
- Many studies equate “accurate classification” with “safe recommendation”
- Safety constraints are often optional or missing
- Defensible systems treat safety as a **hard constraint**

**Speaker notes**
Our review calls this the persistence of safety gaps:
- A classifier can be accurate but still recommend unsafe options.
- Safety must be treated like a gate: if a medicine fails a safety rule, it must be excluded.

---

## Slide 6 — How our system enforces safety (what we currently do)

**Slide bullets**
- Safety layer (implemented now)
  - Age filtering using dataset “Minimum Age”
  - Cough clarification (dry vs productive) before recommending
  - Negation handling (prevents recommending for symptoms the user denies)
- Safety layer (future work)
  - Pregnancy/breastfeeding constraints
  - Drug–drug interaction screening
  - Allergy/contraindication checks

**Speaker notes**
In our implementation today, safety is already a required step, not an optional feature:
- If the user’s age is below the minimum age, that medicine is filtered out.
- If cough is ambiguous, the system pauses and asks a clarifying question rather than guessing.
- If the user explicitly denies fever/headache, we suppress those symptoms to prevent wrong recommendations.

We also clearly present the future expansion points: pregnancy and DDI screening, which the literature identifies as essential for clinical defensibility.

---

## Slide 7 — Explainability: trust + misuse prevention

**Slide bullets**
- Explainability is a safety feature
- Not “social proof” (reviews), but traceable clinical logic
- We provide:
  - Detected symptoms
  - Reason codes (“why this medicine”)
  - Optional extraction flow (dictionary hits + semantic scores)

**Speaker notes**
In OTC recommendation, explainability is not just for user trust; it prevents misuse.

Instead of saying “this is popular,” we show:
- which symptom class was detected
- which rule bucket matched (e.g., dry cough match)
- and—when needed—step-by-step flow showing how the text was interpreted

This is especially important for kiosk/dispensing systems: software errors can cause physical harm.

---

## Slide 8 — Evaluation: beyond Accuracy/F1

**Slide bullets**
- Standard ML metrics (Accuracy/F1) measure prediction quality
- Safety-aware evaluation must include:
  - Unsafe recommendation rate
  - Contraindication rejection rate
  - Clarification correctness (when ambiguity exists)
  - User understanding of limitations

**Speaker notes**
The PRISMA review argues that typical metrics are incomplete.

For our system, the correct evaluation question is not only:
- “Did we label the symptom correctly?”

But also:
- “Did we block unsafe medicines?”
- “Did we ask a question instead of guessing?”
- “Does the user understand what the system can/cannot do?”

This aligns with a decision-support framing rather than a pure prediction framing.

---

## Slide 9 — Where each model/algorithm appears in our pipeline (quick technical mapping)

**Slide bullets**
- Step 1: deterministic rules (no ML)
- Step 2: transformer embeddings (deep learning, pretrained)
- Step 3: hybrid cascade + lexical guards (risk control)
- Step 4: rule-based dataset recommender + safety filters
- Offline STT: Whisper (deep learning)

**Speaker notes**
This slide lets you answer panel questions like: “What ML do you actually use?”

We use deep learning in two places:
- semantic fallback for symptom detection (SentenceTransformers)
- offline speech-to-text (Whisper)

But we intentionally surround those models with rule-based constraints because the PRISMA review shows safety gaps when systems rely on ML confidence alone.

---

## Slide 10 — One-sentence takeaway (good closing line)

**Slide bullets**
- Our system is not a “popularity-based recommender.”
- It is a **hybrid decision-support pipeline**: meaning-aware NLP + safety constraints + explainable rules.

**Speaker notes**
A strong final line:

We designed the system based on evidence from the literature: we combine deterministic rules and embedding-based understanding, but recommendations are only produced after safety constraints and explainable indication matching—so the system behaves like decision support, not a “most-popular-medicine predictor.”
