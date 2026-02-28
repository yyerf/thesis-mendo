# Mendo Symptom-to-OTC Pipeline (Step 1 → End)

This document describes the **models**, **algorithms**, and **ML / deep learning components** used end-to-end in this workspace, from deterministic symptom extraction (Step 1) through semantic fallback (Step 2/3), dataset-based recommendation (Step 4), and offline speech-to-text (Web).

## 0) High-level architecture

**Dataflow**

1. **Input text** (typed or offline speech-to-text)
2. **Step 3 Hybrid NLP**
   - Step 1 dictionary/rules first
   - Step 2 embeddings only when needed
3. **Step 4 recommender** (rule-based scoring over `data/datasets/Mendo-Datasets.json`)
4. **UI** renders detected symptoms + recommendations; may ask a clarifying question for cough type

Key code entrypoints:
- Web app launcher: [app.py](app.py)
- Flask server + offline STT endpoint: [web/app.py](web/app.py)
- Deterministic symptom extractor: [mendo_core/step1.py](mendo_core/step1.py)
- Semantic embeddings extractor: [mendo_core/step2.py](mendo_core/step2.py)
- Hybrid cascade (dictionary → semantic): [mendo_core/step3_hybrid.py](mendo_core/step3_hybrid.py)
- Dataset-driven recommendations: [mendo_core/step4_recommend.py](mendo_core/step4_recommend.py)

---

## 1) Step 1 — Deterministic symptom extraction (no ML)

Implemented in: [mendo_core/step1.py](mendo_core/step1.py)

### 1.1 Normalization algorithm
Step 1 is intentionally deterministic to be “defense-friendly”:

- Lowercase + trim
- **De-jejemize / leetspeak translation** (character mapping)
  - Examples: `s@k1t ul0` → `sakit ulo`
- Replace non-alphanumerics with spaces
- Collapse whitespace

This normalization is used before phrase matching so the system is robust to noisy text.

### 1.2 Phrase dictionary matching
Core structure:

- `SYMPTOM_DICTIONARY: Dict[str, List[str]]`
- Each symptom label (e.g., `HEADACHE`) has a list of phrases/keywords (English/Tagalog/Bisaya).

Matching logic:
- Multi-word phrases: substring match on the normalized text
- Single tokens: regex word-boundary match (`\bword\b`) to avoid accidental partial hits

This is **rule-based information extraction** (pattern matching), not ML.

### 1.3 Special cough typing algorithm (rule-based classifier)
Cough is split into:
- `COUGH_DRY`
- `COUGH_PRODUCTIVE`
- `COUGH_GENERAL`

Algorithm: `_extract_cough_type(normalized_text)`

- First, detect cough presence (`ubo`/`cough` + common variants)
- Then apply qualifier lists for dry vs wet
- Priority rule: **explicit DRY wins over WET**
  - Handles negated wet-cough strings like “walang plema” (contains token `plema` but implies dry)
- Additional regex catch: “wala (namang) plema” patterns

Also supported: **dry cough implied by itchy throat** even if user never says “ubo/cough”:
- Example: “makati ang lalamunan” → `COUGH_DRY`

This is effectively a small, transparent **rule-based intent classifier**.

### 1.4 Negation handling (rule-based)
Function: `_is_negated(normalized_text, normalized_phrase)`

- Detects negations like: `no`, `not`, `without`, `walang`, `walay`, `dili`, `di`
- Uses a limited window: negation word + up to 2 filler tokens before the phrase

Applied in dictionary scan for a subset of high-impact labels (e.g., fever/headache/diarrhea) and also via stronger overrides for fever.

### 1.5 Heuristic recall fixes (still deterministic)
Two targeted improvements were added to improve recall under real-world mixed phrasing:

- **Headache heuristic**: if text contains a head keyword (`head`/`ulo`) and a pain keyword (`sakit`, `labad`, `throbbing`, …), add `HEADACHE`, unless explicitly negated.
- **Fuzzy runny nose rescue**: a small bounded Levenshtein distance check for common `sipon` variants.
  - Example: `ssinisipown` → `RUNNY_NOSE`

The edit-distance implementation (`_levenshtein_within`) is used narrowly (only a few targets) to minimize false positives.

### 1.6 Nasal label inference (rule-based)
Function: `_infer_nasal_label(normalized_text, detected)`

- If user mentions `nose/ilong`, infer:
  - `RUNNY_NOSE` if runny cues exist (sipon/tulo)
  - `NASAL_CONGESTION` if blocked cues exist (barado/bara)
  - `ALLERGIC_RHINITIS` if allergy cues exist (bahing/makati/katol)

---

## 2) Step 2 — Semantic symptom extraction (ML model, no training)

Implemented in: [mendo_core/step2.py](mendo_core/step2.py)

### 2.1 Model used
- Library: `sentence-transformers`
- Encoder (default): `paraphrase-multilingual-MiniLM-L12-v2`

This is a **pre-trained transformer encoder** (deep learning) that maps a sentence to a dense embedding vector.

Important: the code **does not train/fine-tune** this model. It only performs inference.

### 2.2 Algorithm: anchor-based embedding similarity
Data:
- `SYMPTOM_ANCHORS: Dict[str, List[str]]`
  - For each symptom label, store a few anchor sentences (English/Tagalog/Bisaya).

Computation:
1. Encode user input to vector $u$
2. Encode each symptom’s anchors to vectors $a_1..a_k$ (pre-encoded once at init)
3. Compute cosine similarity:

$$\text{sim}(u, a_i) = \frac{u \cdot a_i}{\|u\|\,\|a_i\|}$$

4. For each symptom, take best anchor score; if score ≥ `threshold`, that symptom is detected

Output:
- Detected labels
- Diagnostics per symptom: best score + best anchor

This is a **retrieval-style semantic matcher** (embedding similarity search), not a classifier trained on labeled data.

---

## 3) Step 3 — Hybrid cascade (rules first, embeddings fallback)

Implemented in: [mendo_core/step3_hybrid.py](mendo_core/step3_hybrid.py)

### 3.1 Cascade strategy
The hybrid pipeline follows a strict order:

1. Run Step 1 deterministic extractor
2. If **any** symptom is found → return it (fast path)
3. If none found AND semantic fallback is enabled → run Step 2 embeddings

This keeps normal operation predictable and avoids embedding false positives when the dictionary already succeeded.

### 3.2 Lexical guard (reduces semantic false positives)
Function: `_semantic_lexical_guard(user_input, semantic_detected)`

Even if embeddings say a symptom is similar, the label is only allowed if the text contains a related **keyword family**.

Example families:
- headache: `head`, `ulo`, `labad`, `migraine`
- stomach: `tiyan`, `sikmura`, `stomach`, `hilab`
- cough: `ubo`, `cough`, `plema`

This is a cheap, explainable gating mechanism that significantly improves precision.

### 3.3 Symptom selection policy
After semantic scoring, the hybrid stage:
- keeps labels above `semantic_threshold`
- selects up to `semantic_max_symptoms` (top-N)

Default knobs (see CLI flags in [mendo_core/step3_hybrid.py](mendo_core/step3_hybrid.py)):
- `--semantic-threshold` (default 0.65)
- `--semantic-max-symptoms` (default 2)
- `--no-semantic` to disable semantic fallback

### 3.4 Explicit negation overrides (semantic-safe)
To avoid the semantic stage “re-adding” symptoms that the user explicitly denies:

- `_explicitly_negates_fever()` removes `FEVER` when phrases like “wala akong fever” appear
- `_explicitly_negates_headache()` removes `HEADACHE` when phrases like “not sakit ulo” appear

These overrides apply to both:
- `extract_symptoms_hybrid(...)`
- `extract_symptoms_hybrid_report(...)`

---

## 4) Step 4 — Dataset-driven OTC recommendation (rules, not ML)

Implemented in: [mendo_core/step4_recommend.py](mendo_core/step4_recommend.py)

### 4.1 Data source
- JSON dataset: `data/datasets/Mendo-Datasets.json`
- Loaded into `MedRow` records

### 4.2 Recommendation algorithm
Function: `recommend_from_dataset(symptoms, rows)`

This is a deterministic, explainable scoring system:

- If cough is ambiguous (`COUGH_GENERAL`), return `ask_clarify`
- Else compute candidates:
  - Match by symptom indicators in dataset fields (`Primary Symptom`, `Typical Symptoms Treated`, `Drug Category`)
  - Add weighted scores (e.g., dry cough match = 3)
- Merge results by brand, keep best score, merge reasons
- Return top-N recommendations

### 4.3 Age filtering
In the Flask layer ([web/app.py](web/app.py)), recommendations are filtered by `Minimum Age`:
- Parses `Minimum Age` into an integer threshold when possible
- Drops items where `age < min_age`

---

## 5) Web app + Offline Speech-to-Text (deep learning)

Implemented in: [web/app.py](web/app.py)

### 5.1 Offline STT model
The `/api/stt` endpoint transcribes a user-recorded WAV file using Whisper.

Preferred backend:
- `faster-whisper` (`faster_whisper.WhisperModel`)
  - Runs on CPU by default
  - Supports quantized compute types (default `int8`)

Fallback:
- `openai-whisper` (`whisper.load_model`)

Configuration via environment variables:
- `MENDO_WHISPER_MODEL` (default: `small`)
- `MENDO_WHISPER_DEVICE` (default: `cpu`)
- `MENDO_WHISPER_COMPUTE_TYPE` (default: `int8`)

This is **deep learning inference**, fully offline after the model is cached locally.

### 5.2 NLP + recommendation integration
The main web assessment uses:
- `extract_symptoms_hybrid_report(...)` for transparent stage-by-stage debugging
- `recommend_from_dataset(...)` for OTC suggestions

---

## 6) Benchmarking models (evaluation tooling)

Implemented in: [tools/benchmark.py](tools/benchmark.py) + [mendo_core/symptom_models.py](mendo_core/symptom_models.py)

These are separate from the Step1–Step4 pipeline and are used to compute accuracy metrics on labeled JSONL datasets.

Models in benchmarking module:
- `RuleRegexModel` (`rules`): regex patterns for canonical labels
- `EnglishOnlyRegexModel` (`english_rules`): English-only baseline

Metrics:
- exact match accuracy
- micro precision/recall/F1
- Hamming accuracy
- per-label precision/recall/F1

---

## 7) Legacy ML artifacts (optional / historical)

In [web/app.py](web/app.py) there is optional loading of legacy artifacts:
- `CountVectorizer`, `LabelEncoder`, and an SVM model loaded from local pickle files
- These are used by an older `/assess` workflow and are guarded by `LEGACY_MODEL_AVAILABLE`

The current “thesis pipeline” (Step 1–4) does **not** depend on these legacy models.

---

## 8) Model/algorithm summary table

| Stage | Component | Type | Where | Key idea |
|---|---|---|---|---|
| Step 1 | Phrase dictionary + rules | Rule-based IE | mendo_core/step1.py | Normalization + phrase matching + negation + cough typing |
| Step 1 | Cough typing | Rule-based classifier | mendo_core/step1.py | Dry vs wet qualifiers + negation priority |
| Step 1 | Fuzzy `sipon` rescue | String similarity (DP) | mendo_core/step1.py | Bounded Levenshtein for common typos |
| Step 2 | Sentence embeddings | Deep learning (Transformer) | mendo_core/step2.py | `SentenceTransformer` + cosine similarity to anchors |
| Step 3 | Hybrid cascade | System design (rules→ML) | mendo_core/step3_hybrid.py | Only run ML when rules fail |
| Step 3 | Lexical guard | Rule-based safety filter | mendo_core/step3_hybrid.py | Prevent absurd embedding matches |
| Step 4 | OTC recommendation | Rule-based ranking | mendo_core/step4_recommend.py | Dataset keyword match + scoring + cough clarification |
| Web | Offline STT | Deep learning (Whisper) | web/app.py | Local transcription (faster-whisper preferred) |

---

## 9) Practical tuning knobs

- Expand phrase coverage: edit `SYMPTOM_DICTIONARY` in [mendo_core/step1.py](mendo_core/step1.py)
- Adjust semantic strictness: `--semantic-threshold` in [mendo_core/step3_hybrid.py](mendo_core/step3_hybrid.py)
- Control semantic output size: `--semantic-max-symptoms`
- Disable semantic fallback (fully deterministic): `--no-semantic`
- Whisper STT speed/quality: `MENDO_WHISPER_MODEL`, `MENDO_WHISPER_DEVICE`, `MENDO_WHISPER_COMPUTE_TYPE`
