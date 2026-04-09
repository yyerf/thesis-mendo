# FULL SYSTEM DATA — MendoVendo v3.0
## For Thesis Methodology Chapter Completion

> **PURPOSE:** This document contains the COMPLETE and ACCURATE technical data of the MendoVendo v3.0 system as it exists in the codebase. Use this to write/fix the Materials & Methods chapter. Everything here is verified against actual source code — no hallucination, no aspirational features.

---

## ⚠️ CRITICAL DISCREPANCIES: Current Methodology Docx vs Actual System

The existing `Thesis-current-methodology.docx` has several claims that **do NOT match the actual codebase**. These MUST be corrected:

### 1. WRONG: "15 symptom labels"
**Docx says:** "15 clinically meaningful symptom labels (HEADACHE, FEVER, COUGH_DRY, COUGH_PRODUCTIVE, COUGH_GENERAL, RUNNY_NOSE, NASAL_CONGESTION, SORE_THROAT, STOMACH_ACHE, NAUSEA, VOMITING, DIARRHEA, BODY_ACHES, DIZZINESS, FATIGUE)"

**Actual system has 13 labels (12 unique + COUGH_GENERAL as ambiguous):**
HEADACHE, FEVER, COUGH_DRY, COUGH_PRODUCTIVE, COUGH_GENERAL, RUNNY_NOSE, NASAL_CONGESTION, SORE_THROAT, STOMACH_ACHE, DIARRHEA, BODY_ACHES, ALLERGIC_RHINITIS, RASHES

**NAUSEA, VOMITING, DIZZINESS, FATIGUE do NOT exist in the codebase.** Remove them.

### 2. WRONG: "Fine-tuning was performed"
**Docx says:** "Embedding Model Fine-Tuning: Domain-specific adaptation of paraphrase-multilingual-MiniLM-L12-v2 was performed on 252 sentence-pair similarity samples using CosineSimilarityLoss, with batch size 16, 4 epochs, 50 warmup steps, and the AdamW optimizer at the library default learning rate of 2×10⁻⁵."

**ACTUAL:** No fine-tuning was performed. The model is used in inference-only mode (pre-trained weights, no training). The code (`step2.py`) loads the model directly:
```python
self._model = SentenceTransformer(model_name, device=chosen_device)
```
There is NO training loop, NO loss function, NO fine-tuning anywhere in the codebase. **This entire paragraph must be removed or rewritten to say "pre-trained inference only, no fine-tuning."**

### 3. WRONG: "1,039 utterances annotated by pharmacist"
**Docx says:** "Real-World Style Dataset Construction: A corpus of 1,039 realistic patient-style utterances" and "Licensed pharmacist annotates the 1,039-entry corpus"

**ACTUAL:** The system uses a hand-crafted dictionary of ~260+ phrases across 13 symptom labels (in `step1.py`). The benchmark test set is 288 CSV rows (in `testing/benchmark/testing.csv`). There is no 1,039-entry annotated corpus in the codebase. The pharmacist annotation tool (mendo.diapana.dev) was planned but the domain expert did not complete the annotation — this is why the project adopted the ASG (Authoritative-Source-Grounded) framework using package inserts and MIMS Philippines instead.

### 4. WRONG: "522 curated phrases across 15 symptom labels"
**ACTUAL:** 331 phrases across 13 symptom labels (verified from `SYMPTOM_DICTIONARY` in `step1.py`).

### 5. WRONG: "26 OTC drugs"
**Docx says:** "knowledge graph for 26 drugs" and "up to 26 OTC drugs"

**ACTUAL:** 24 medicine entries (19 unique brands) in `data/Mendo-Datasets.json`. Not 26.

### 6. WRONG: "Threshold sweep on 2,170-entry corpus"
**Docx says:** "threshold sweep analysis (0.40 to 0.85) was conducted on a 2,170-entry symptom evaluation corpus"

**ACTUAL:** The threshold is hardcoded at 0.65 in the codebase. There is no 2,170-entry corpus. The benchmark is 288 rows. This appears to be aspirational or from an earlier plan. Remove or replace with actual threshold rationale.

### 7. WRONG: "Knowledge graph"
**Docx says:** "OTC medication knowledge graph" and "knowledge graph constraints"

**ACTUAL:** The system uses a flat JSON dataset (`Mendo-Datasets.json`) with 15 fields per medicine entry. It is NOT a graph database (no nodes, edges, or graph traversal). It is a rule-based lookup table. Call it a "structured medicine dataset" or "rule-based lookup table," not a "knowledge graph."

### 8. WRONG: "4-stage pipeline"
**Docx says:** four-stage cascaded pipeline

**ACTUAL:** The pipeline is 5 stages (including triage):
- Stage 0: Triage / Red-Flag Safety Layer
- Stage 1: Dictionary-Based Extraction
- Stage 2: Semantic Fallback
- Stage 3: Hybrid Merge + Lexical Guards + Safety Filters
- Stage 4: ASG Recommendation Engine

### 9. WRONG: Iteration 2 describes annotation and fine-tuning
**Docx says:** Iteration 2 involves expert annotation, fine-tuning, and threshold optimization.

**ACTUAL:** The project followed Plan B (ASG framework) because the pharmacist could not complete annotation. Iteration 2 should describe: dictionary expansion, negation handling implementation, fuzzy rescue development, contrastive boundary logic, and initial benchmark creation.

---

## ACTUAL SYSTEM ARCHITECTURE (Ground Truth)

### Project: MendoVendo v3.0
- **Purpose:** AI-enabled multilingual OTC medicine recommendation kiosk for Philippine pharmacies
- **Deployment Target:** Raspberry Pi 5-based physical vending kiosk
- **Framework:** Flask (Python 3.12.3)
- **ML Model:** `paraphrase-multilingual-MiniLM-L12-v2` (33M parameters, pre-trained, inference-only, CPU-safe)
- **No fine-tuning, no training, no custom model**

### File Structure (Core Pipeline)
```
mendo_core/
├── __init__.py          (2 lines — package marker)
├── step1.py             (1,343 lines — Dictionary-based extraction)
├── step2.py             (320 lines — Semantic fallback)
├── step3_hybrid.py      (1,636 lines — Hybrid merge + triage + safety)
├── step4_recommend.py   (936 lines — Recommendation engine)
└── symptom_models.py    (207 lines — Benchmark protocol)

data/
└── Mendo-Datasets.json  (24 medicine entries, 15 fields each)

testing/
├── test_algorithm.py    (719 lines — Benchmark runner)
└── benchmark/
    └── testing.csv      (288 test cases, 60 categories)

web/
├── app.py               (Flask app factory)
└── templates/           (HTML templates)

pos/
├── routes_consultation.py (305 lines — Consultation API)
├── routes_shop.py         (Shop/cart routes)
├── routes_admin.py        (Admin dashboard)
├── auth.py                (Authentication)
└── db.py                  (SQLite database)
```

---

## STAGE 0: TRIAGE / RED-FLAG SAFETY LAYER

**File:** `mendo_core/step3_hybrid.py` (lines 36–157)

**Purpose:** Detect medical emergencies BEFORE symptom extraction. If a red flag is found, the system responds with "CONSULT A DOCTOR" instead of recommending OTC medicine.

**18 unique Red-Flag Types across 19 triage rules with multilingual co-occurrence patterns:**

| # | Category | Example Triggers | Medical Reason |
|---|----------|-----------------|----------------|
| 1 | `blood_in_stool` | "may dugo sa dumi", "bloody stool" | GI hemorrhage |
| 2 | `blood_vomit` | "nagsusuka ng dugo", "vomiting blood" | Upper GI bleed |
| 3 | `chest_pain` | "masakit ang dibdib", "chest pain", "sakit sa dughan" | Possible cardiac event |
| 4 | `difficulty_breathing` | "hirap huminga", "shortness of breath", "lisod ginhawa" | Respiratory emergency |
| 5 | `dengue_warning` | "lagnat at pantal", "fever with rashes" | Dengue / viral hemorrhagic risk |
| 6 | `stroke_warning` | "manhid ang mukha", "paralysis", "speech loss" | Neurological event |
| 7 | `severe_dehydration` | "nagtatae walang ihi", "diarrhea no urine" | Acute kidney injury risk |
| 8 | `pregnancy_contraindication` | "buntis", "pregnant", "naglilihi" | Fetal harm risk from OTCs |
| 9 | `high_fever_prolonged` | "lagnat na 41 degrees", "fever of 40 degrees" | Temperature ≥40°C |
| 10 | `seizure` | "seizure", "kombulsyon", "atake" | Neurological emergency |
| 11 | `loss_of_consciousness` | "nahimatay", "fainted", "nawalan ng malay" | Requires medical evaluation |
| 12 | `severe_allergic_reaction` | "namamaga ang lalamunan", "swollen throat" | Anaphylaxis risk |
| 13 | `head_bleeding` | "nagdurugo ang ulo", "head bleeding" | Head trauma |
| 14 | `nose_bleeding` | "nagdurugo ang ilong", "nosebleed" | May indicate serious condition |
| 15 | `ear_bleeding` | "nagdurugo ang tenga", "ear bleeding" | Ruptured eardrum / head trauma |
| 16 | `hemoptysis` | "nagdudugo ang ubo", "coughing blood" | Serious lung condition |
| 17 | `blood_in_urine` | "may dugo sa ihi", "blood in urine" | Hematuria |
| 18 | `hypertension_risk` | "high blood", "hypertension" | Consult before OTC self-medication |

**Key design decision:** Uses LIGHT normalization (lowercase + whitespace only) instead of full de-jejemize normalization because `_normalize()` converts digits (0→o, 4→a) which would destroy temperature values like "40 degrees" → "ao degrees".

**Does NOT short-circuit the pipeline** — symptoms are still extracted for benchmark validation. The triage gate activates at Stage 4 to suppress OTC recommendations.

---

## STAGE 1: DICTIONARY-BASED EXTRACTION

**File:** `mendo_core/step1.py` (1,343 lines)

### 1.1 Symptom Dictionary
13 symptom labels with 331 multilingual phrases:

| Label | Phrase Count | Languages | Key Examples |
|-------|-------------|-----------|--------------|
| HEADACHE | 42 | Tag/Bis/Eng | "masakit ang ulo", "labad akong ulo", "headache", "bumbunan ko" |
| FEVER | 43 | Tag/Bis/Eng | "lagnat", "nilalagnat", "hilanat", "init akong lawas" |
| BODY_ACHES | 39 | Tag/Bis/Eng | "masakit katawan", "binugbog", "bug at akong lawas" |
| STOMACH_ACHE | 38 | Tag/Bis/Eng | "sakit tiyan", "kabag", "hyperacidity", "buhol buhol" |
| RASHES | 32 | Tag/Bis/Eng | "pantal", "rash", "makati ang balat", "namumula ang balat" |
| SORE_THROAT | 31 | Tag/Bis/Eng | "masakit lalamunan", "sore throat", "garas akong tilaok", "paos" |
| COUGH_PRODUCTIVE | 20 | Tag/Bis/Eng | "may plema", "basang ubo", "halak", "kumakalansing sa dibdib" |
| ALLERGIC_RHINITIS | 17 | Tag/Bis/Eng | "allergy", "bahing", "alerdyi", "makati ilong" |
| DIARRHEA | 17 | Tag/Bis/Eng | "pagtatae", "diarrhea", "lbm", "loose bowel" |
| COUGH_GENERAL | 16 | Tag/Bis/Eng | "ubo", "cough", "inuubo", "gi-ubo" |
| COUGH_DRY | 15 | Tag/Bis/Eng | "walang plema", "tuyong ubo", "dry cough" |
| NASAL_CONGESTION | 11 | Tag/Bis/Eng | "barado ilong", "stuffy nose", "blocked nose" |
| RUNNY_NOSE | 10 | Tag/Bis/Eng | "sipon", "runny nose", "tumutulo ilong" |

### 1.2 Normalization (`_normalize()` function)
Deterministic text preprocessing:
- Lowercase
- Leetspeak/jejemon conversion: `@ → a, 0 → o, 1 → i, 3 → e, 4 → a, 5 → s, 7 → t, 8 → b, $ → s, ! → i, | → i`
- Remove non-alphanumeric characters (keep ñ)
- Collapse whitespace

Example: `"s@k1t ul0"` → `"sakit ulo"` → matches HEADACHE

### 1.3 Phrase Matching (`_phrase_in_text()`)
- **Multi-word phrases:** substring match in normalized text
- **Single-word keywords:** `\b` word boundary regex to prevent false positives (e.g., "ubo" inside "tubo")

### 1.4 Negation Handling
**11 negation words:** `no, not, without, walang, walay, waley, dili, di, hindi, hnd, wala`

**Window-based detection:** Negation word within 0–2 words BEFORE symptom phrase.

**Applied universally to ALL 13 symptom labels.**

**Consumed negation:** If another symptom keyword sits between the negation word and the target, the negation is consumed by the closer keyword and does NOT propagate. E.g., "hindi pala ubo sipon" — "hindi" negates "ubo", not "sipon". The `_INTERVENING_SYMPTOM_WORDS` set (28 words) is used for this check.

**Negated-Label Tracking:** A `negated_labels` set tracks which symptoms were dictionary-matched but negated, preventing fuzzy rescue from re-adding them.

### 1.5 Contrastive Boundary Splitting
Input is split on: `pero | but | kaso | however | though`

Each segment is evaluated independently for negation. Positive mention AFTER a contrastive boundary overrides prior negation.

Example: `"wala akong lagnat pero masakit ang ulo"` → FEVER negated, HEADACHE detected.

### 1.6 Cough-Type Qualification (`_extract_cough_type()`)
Runs BEFORE general dictionary scan. Decides between COUGH_DRY, COUGH_PRODUCTIVE, or COUGH_GENERAL.

**Logic flow:**
1. Check for itchy/scratchy throat → COUGH_DRY (implied dry cough)
2. Check for chest-rattle/congestion phrases → COUGH_PRODUCTIVE (even without "ubo/cough")
3. Check if "ubo/cough" word is present → if not, return []
4. Check for explicit cough negation (with plema-filler exemption) → if negated, return []
5. Check dry qualifiers (walang plema, dry cough, tuyong ubo, etc.) → COUGH_DRY
6. Check wet qualifiers (may plema, basang ubo, halak, etc.) → COUGH_PRODUCTIVE
7. Default → COUGH_GENERAL

**Priority rule:** Explicit DRY phrases beat WET.

**Chest-rattle bypass:** Phrases like "kumakalansing sa dibdib" directly map to COUGH_PRODUCTIVE without requiring the word "ubo/cough".

### 1.7 Headache Heuristic
Composable `head_word + pain_word` check with proximity (≤5 tokens):
- Head words: `head, ulo` (+ fuzzy: `hed→head, olo→ulo`)
- Pain words: `sakit, masakit, labad, throbbing, pounding, kirot, hurt, hurts, ache, sasabog, binibiyak, pumapasabog` (+ fuzzy)
- Both head and pain must be within 5 tokens of each other

### 1.8 SORE_THROAT Proximity Heuristic
Detects when throat_word and pain_word appear within ≤5 tokens, regardless of order.
- Throat words: `lalamunan, tutunlan, throat`
- Pain words: `masakit, sumasakit, mahapdi, sakit, pain, hurts, sore, hapdi`
- Dual negation checking on both throat and pain words

### 1.9 Per-Cue-Group Nasal Inference (`_infer_nasal_label()`)
3 independent cue groups, each with independent negation:
- Allergy cues → ALLERGIC_RHINITIS
- Runny cues → RUNNY_NOSE  
- Congestion cues → NASAL_CONGESTION
- Contrastive boundary awareness per group
- Only returns empty if ALL mentioned groups are negated

### 1.10 Allergen-Trigger Heuristic
If RASHES is detected AND an allergen-trigger word appears (dust, alikabok, pollen, amag, pet, dander, etc.), also infer ALLERGIC_RHINITIS.

### 1.11 Fuzzy Rescue (Levenshtein Distance)
7 fuzzy rescue families with exclusion sets:

| Symptom | Targets | Max Distance | Exclusions |
|---------|---------|-------------|------------|
| FEVER | lagnat, fever, hilanat | 1 | — |
| RUNNY_NOSE | sinisipon, sinasipon, sisipon, sipon | 2 | — |
| COUGH | ubo | 1 | ulo, ulu, ole, olo, tubo, ubos, ubi, ube, tuba, ubod |
| DIARRHEA | pagtatae, nagtatae, kalibang | 2 | kaninang, kanina, kaninag |
| RASHES | pantal, butlig | 1 | ipantal, pantalon, pantalan |
| STOMACH_ACHE | tiyan, sikmura | 1 | Requires nearby pain word |
| BODY_ACHES | katawan, lawas | 1 | Requires nearby pain word |

All fuzzy rescues check the `negated_labels` set before adding.

### 1.12 Proximity-Based Rescues
Additional proximity checks for:
- NASAL_CONGESTION: "barado" near "ilong/nose" (±3 tokens)
- RASHES: skin_word + rash_indicator co-occurrence
- FEVER: "mainit/init" near "katawan/lawas/body" (±3 tokens)
- STOMACH_ACHE: "stomach/tummy" near pain words (±3 tokens)

### 1.13 Strong Negation Overrides
Contrastive-boundary-aware negation for: FEVER, COUGH, HEADACHE, RUNNY_NOSE, BODY_ACHES. Each uses `_strong_neg_check()` with:
- Per-segment evaluation (split on pero/but/kaso/however/though)
- Last-segment-wins logic
- Consumed negation awareness
- Cough has `ignored_filler_words={"plema", "phlegm", "mucus"}` so "no plema" doesn't negate cough

---

## STAGE 2: SEMANTIC FALLBACK

**File:** `mendo_core/step2.py` (321 lines)

### Model
- **Name:** `paraphrase-multilingual-MiniLM-L12-v2` (Sentence-Transformers)
- **Parameters:** ~33 million
- **Embedding dimension:** 384
- **Languages:** 50+ including Filipino/Tagalog
- **Usage:** Pre-trained inference ONLY — no fine-tuning, no training
- **Device:** CPU by default (configurable via `MENDO_SEMANTIC_DEVICE` env var)

### Anchor Sentences
5–12 gold-standard example sentences per symptom label (118 anchor sentences total across 13 labels). These are pre-encoded once at initialization.

### How It Works
1. Pre-encode all anchor sentences into 384-dimensional vectors at startup
2. Encode user input into a vector at runtime
3. Compute cosine similarity between user input and each symptom's anchor embeddings
4. Return symptoms where best_anchor_score ≥ threshold (default: 0.65)

### When It Activates
- **ONLY when Stage 1 (dictionary) returns zero symptoms**
- This is the precision-first switching logic — dictionary results are trusted; semantic only fires as fallback
- Output is filtered through Stage 3's lexical guards

---

## STAGE 3: HYBRID MERGE + LEXICAL GUARDS + SAFETY FILTERS

**File:** `mendo_core/step3_hybrid.py` (1,636 lines)

### Pipeline Flow
```
1. Run detect_red_flags(user_input) → red_flags list
2. Run extract_symptoms_dictionary(user_input) → dict_symptoms
3. Apply _explicitly_negates_cough() override
4. IF dict_symptoms is non-empty → return dict_symptoms (skip semantic)
5. ELSE → load semantic model (lazy singleton)
6. Run semantic extraction → raw detections
7. Apply _semantic_lexical_guard() — 11 keyword gates
8. Apply _apply_semantic_safety_filters() — 7 negation + red-flag suppression
9. Score-rank and select top-N (default: 2) semantic symptoms
10. Return selected symptoms
```

### Lexical Guard — 11 Keyword Gates
Each semantic detection must pass a keyword check in the original text:

| Gate | Required Keywords |
|------|-------------------|
| COUGH_* | cough, ubo, inuubo, hubak, halak, kumakalansing, rattly chest |
| COUGH_PRODUCTIVE (special) | needs cough_keyword + plema_keyword OR chest/dibdib + plema |
| DIARRHEA | diarrhea, pagtatae, lbm, kalibang, tae, dumi, loo, bathroom, toilet, liquid, loose bowel |
| NASAL_* | nose, ilong, sipon, runny, stuffy, barado, tumutulo |
| FEVER | fever, temperature, hot, lagnat, nilalagnat, hilanat, gihilanat, init akong lawas |
| HEADACHE | headache, ulo, labad, migraine, tumitibok, kumikislot, sasabog, binibiyak, gibukbok, brain, explode, bumbunan |
| BODY_ACHES | body ache, katawan, lawas, muscle, binugbog, pinukpok, nanlalamig, ngalay, buto, bug at, heavy body |
| STOMACH_ACHE | stomach, tiyan, sikmura, hilab, kabag, buhol buhol, kumukulo, hyperacidity, heartburn |
| ALLERGIC_RHINITIS | sipon, bahing, sneeze, nasal, ilong, katol, makati, alerdyi |
| RASHES | rash, hives, pantal, butlig, balat, panit, itch, makati, pula, namumula, bumps |
| SORE_THROAT | sore throat, throat, lalamunan, tutunlan, katulon, paos, hapdi, garas, tilaok, scratchy |
| Default | pass through |

### 7 Explicit Negation Functions
- `_explicitly_negates_fever()` — fever/lagnat/hilanat
- `_explicitly_negates_headache()` — headache/head/ulo
- `_explicitly_negates_cough()` — ubo/cough (with plema-filler exemption)
- `_explicitly_negates_diarrhea()` — diarrhea/lbm/pagtatae/kalibang
- `_explicitly_negates_sore_throat()` — sore throat/lalamunan/tutunlan/tilaok
- `_explicitly_negates_nasal()` — sipon/runny nose/stuffy nose/barado
- `_explicitly_negates_allergy()` — allergy/allergies/allergic

### Centralized Safety Filter (`_apply_semantic_safety_filters()`)
Applies all 7 negation functions plus:
- **Red-flag suppression:** blood_in_stool → suppress DIARRHEA, severe_allergic_reaction → suppress SORE_THROAT
- **Word-boundary-safe matching** in `_has_any()` using `\b` regex

---

## STAGE 4: ASG RECOMMENDATION ENGINE

**File:** `mendo_core/step4_recommend.py` (936 lines)

### MedRow Dataclass (15 fields)
| Field | Type | Source |
|-------|------|--------|
| Brand | str | Product label |
| Generic/Main Use | str | Package insert |
| Drug Category | str | MIMS classification |
| Primary Symptom | str | Clinical mapping |
| Typical Symptoms Treated | str (comma-sep) | Package insert |
| Dosage Form | str | Product label |
| Minimum Age | str | Package insert |
| Notes | str | Clinical notes |
| Approved_Indications | tuple[str] | Package Insert / MIMS |
| Indication_Source | str | ASG attribution |
| Contraindications | tuple[str] | Package Insert / MIMS |
| Warnings | tuple[str] | Package Insert |
| Drug_Interactions | tuple[str] | Package Insert / MIMS |
| Max_Duration_Days | int | Package Insert |
| Contraindication_Source | str | ASG attribution |

### Recommendation Logic
1. **Triage gate:** If red_flags non-empty → return "CONSULT A DOCTOR" + suppress all OTC
2. **COUGH_GENERAL handling:** Sole symptom → ask_clarify; with others → defer cough, recommend rest
3. **Rule-based symptom→medicine matching** with score-ranked candidates
4. **Merge by brand** (keep highest score, combine reasons)
5. **Safety checks:**
   - Paracetamol overlap detection (Bioflu + Neozep + Biogesic = warning)
   - Opposing mechanism warning (expectorant + cough suppressant)
   - Cough follow-up informational warning

### OLDCARTS Duration Safeguard Matrix

The Duration component of the OLDCARTS (Onset, Location, Duration, Character, Aggravating, Relieving, Timing, Severity) clinical assessment framework is implemented as a universal safety layer across all 9 symptom categories. After the existing OLDCARTS-inspired clarification flow (Character, Onset, Aggravating, Timing), the system asks the patient how long each detected symptom has persisted. If the reported duration exceeds a clinically-defined threshold, OTC recommendations are blocked entirely and the patient is referred to a licensed medical professional.

This makes the OLDCARTS implementation cover 5 components: **Character** (cough type), **Onset** (diarrhea food poisoning context, headache hunger/dehydration detection), **Aggravating** (sipon allergy vs cold weather), **Timing** (sipon context), and **Duration** (universal symptom duration safety check).

**Flow:** Existing clarifications (cough type → diarrhea context → stomach context → sipon context) complete first, then duration is asked for each detected symptom sequentially via multiple-choice buttons.

| # | Symptom Label | Threshold (Days) | Action if Exceeded | Clinical Rationale |
|---|--------------|-------------------|--------------------|-----------|
| 1 | FEVER | > 3 | Block OTC / Refer | Dengue, Typhoid, Malaria indicator (endemic PH) |
| 2 | DIARRHEA | > 2 | Block OTC / Refer | Dehydration risk, bacterial/parasitic infection |
| 3 | SORE_THROAT | > 5 | Block OTC / Refer | Streptococcal infection, rheumatic fever risk |
| 4 | STOMACH_ACHE | > 7 | Block OTC / Refer | PUD, gallstones, appendicitis |
| 5 | HEADACHE | > 7 | Block OTC / Refer | Hypertension, neurological issues, rebound headaches |
| 6 | BODY_ACHES | > 7 | Block OTC / Refer | Inflammatory arthritis, nerve damage, post-viral sequelae |
| 7 | RASHES | > 7 | Block OTC / Refer | Fungal infection, scabies, chronic immune condition |
| 8 | ALLERGIC_RHINITIS | > 7 | Block OTC / Refer | Chronic immune issue requiring prescription treatment |
| 9 | NASAL_CONGESTION | > 10 | Block OTC / Refer | Bacterial Sinusitis |
| 10 | RUNNY_NOSE | > 10 | Block OTC / Refer | Bacterial sinus infection |
| 11 | COUGH_GENERAL | > 14 | Block OTC / Refer | TB screening (DOH protocol, endemic PH) |
| 12 | COUGH_DRY | > 14 | Block OTC / Refer | TB screening (DOH protocol) |
| 13 | COUGH_PRODUCTIVE | > 14 | Block OTC / Refer | TB screening (DOH protocol) |

**Implementation details:**
- **Question format:** Multiple-choice buttons (e.g., "1-2 days", "3 days", "More than 3 days")
- **Per-symptom:** Duration is asked separately for each detected symptom
- **Threshold logic:** Duration > threshold → block; Duration ≤ threshold → safe to proceed
- **Bilingual prompts:** All questions displayed in Tagalog and English
- **API endpoint:** `POST /consult/api/duration-check`
- **File:** `mendo_core/step4_recommend.py` — `DURATION_THRESHOLDS`, `check_duration_safety()`, `get_duration_question()`, `parse_duration_days()`

### 24 Medicine Entries (19 unique brands)
| # | Brand | Active Ingredient | Category | Primary Symptom | Form |
|---|-------|-------------------|----------|----------------|------|
| 1 | Bioflu | Paracetamol + Phenylephrine + Chlorphenamine | Cold & Flu | Fever | Tablet |
| 2 | Neozep / Neozep Z+ | Paracetamol + Phenylephrine + Chlorphenamine (± Zinc) | Cold | Nasal Congestion | Tablet |
| 3 | Neozep Syrup | Same | Cold | Nasal Congestion | Syrup |
| 4 | Decolgen | Paracetamol + Phenylephrine + Chlorphenamine | Cold | Runny Nose | Tablet |
| 5 | Decolgen Forte | Same | Cold | Nasal Congestion | Tablet |
| 6 | Symdex-D (Syrup) | Paracetamol + Decongestant + Antihistamine | Cold & Cough | Nasal Congestion | Syrup |
| 7 | Symdex-D (Tablet) | Same | Cold & Cough | Nasal Congestion | Tablet |
| 8 | Tuseran Forte | Dextromethorphan + Paracetamol + Phenylephrine + Chlorphenamine | Cold & Cough | Dry Cough | Tablet |
| 9 | Ascof Forte | Lagundi leaf extract | Cough | Productive Cough | Capsule |
| 10 | Solmux (Syrup) | Carbocisteine | Expectorant | Productive Cough | Syrup |
| 11 | Solmux (Capsule) | Carbocisteine | Expectorant | Productive Cough | Capsule |
| 12 | Robitussin | Guaifenesin | Expectorant | Chest Congestion | Capsule |
| 13 | Sinecod Forte | Butamirate citrate | Cough Suppressant | Dry Cough | Tablet |
| 14 | Biogesic (Syrup) | Paracetamol | Pain & Fever | Fever | Syrup |
| 15 | Biogesic (Tablet) | Paracetamol | Pain & Fever | Headache | Tablet |
| 16 | Advil (Syrup) | Ibuprofen | Pain & Inflammation | Pain | Syrup |
| 17 | Advil (Tablet) | Ibuprofen | Pain & Inflammation | Pain | Tablet |
| 18 | Cetirizine (Syrup) | Cetirizine HCl | Allergy | Allergic Rhinitis | Syrup |
| 19 | Cetirizine (Tablet) | Cetirizine HCl | Allergy | Allergic Rhinitis | Tablet |
| 20 | Loperamide (Diatabs) | Loperamide HCl | Anti-diarrhea | Diarrhea | Tablet |
| 21 | Erceflora | Bacillus clausii | GI / Probiotic | Diarrhea | Oral Suspension |
| 22 | Hydrite (ORS) | Oral Rehydration Salts (Sodium, Potassium, Glucose, Citrate) | Rehydration | Diarrhea | Powder for Solution |
| 23 | Kremil-S | Aluminum hydroxide + Magnesium hydroxide + Simethicone | Antacid | Hyperacidity | Tablet |
| 24 | Buscopan | Hyoscine butylbromide | Antispasmodic | Stomach Cramps | Tablet |

All ASG data sourced from: Package Inserts, MIMS Philippines, DOH Philippines.

---

## WEB APPLICATION LAYER

**Framework:** Flask (Python)
**Main app:** `web/app.py` → `app.py` (launcher)

### API Endpoints
**POST `/consult/api/analyze`**
- Input: `{"text": "masakit ulo ko", "age": 25, "severity": 5}`
- Runs full hybrid pipeline (Steps 0-4)
- Returns: symptoms, source, pipeline stages, recommendation, safety warnings
- Age filtering: removes medicines below minimum age
- POS integration: cross-references inventory stock and pricing
- Severity gate: severity ≥ 8 → pharmacist referral warning

**POST `/consult/api/clarify`**
- Handles cough type clarification (dry/productive)
- Re-runs recommendation with specified cough type

**POST `/consult/api/context-clarify`**
- Handles OLDCARTS-style context clarification (diarrhea, stomach ache, runny nose)
- Accepts clarify_type + clarification value
- Re-runs recommendation with context override

**POST `/consult/api/duration-check`**
- OLDCARTS Duration Safeguard — checks symptom duration against clinically-safe thresholds
- Input: `{"symptom": "FEVER", "duration_value": "4+", "original_symptoms": [...], "pending_durations": [...]}`
- If duration exceeds threshold → returns referral (OTC blocked)
- If safe and more symptoms pending → returns next duration question
- If all safe → returns final recommendation with POS stock cross-reference

### POS System (Point of Sale)
- SQLite database for inventory management
- Admin dashboard for stock management
- Cart system for purchase flow
- Authentication for admin access

---

## BENCHMARK & EVALUATION

### Primary Benchmark
- **File:** `testing/benchmark/testing.csv` — 288 test cases
- **Format:** CSV with columns: test_id, input_text, age, cough_type, expected_symptoms, test_category, notes
- **Runner:** `testing/test_algorithm.py` — AlgorithmTester class

### 60 Test Categories across 4 Tiers:

**Tier 1 — Core Functional (100 tests):**
Simple Single (10), Multiple Symptoms (10), Negation (6), Partial Negation (4), Noisy Input (10), Misspelling (10), Alternative Phrasing (10), English (5), Code-Switching (5), Third Person (5), Temporal (5), Age Context (5), Severe Intensity (5), Mild Intensity (5), Question Form (5)

**Tier 2 — Extended Robustness (100 tests):**
Jejemon/Leetspeak (8), Bisaya Heavy (7), Compound Multi (5), Contrastive Negation (6), Run-on Realistic (6), Diagnostic Confusion (5), Interjection/Filler (7), Symptom Chain (5), Temporal Progression (5), Polite/Formal (5), Extreme Severity (5), Very Mild (5), English Complex (5), Heavy Code-Switch (6), Pharmacy Kiosk Realistic (5), Negation Complex (5), Double Misspelling (5), Figurative Speech (5)

**Tier 3 — Adversarial (64 tests):**
Universal negation (7), False positive traps (10), Sore throat (3+2), Contrastive new (7), Multi-negation (2), Mixed complex (3), Non-symptom (6), Single word (6), Stress all (1), Bisaya negation (3), Reversed order (3), Conyo (2), Sore throat combo (2), Bisaya sore throat (1), Gibberish (3), Post-negation (1), Long realistic (1), Allergy nasal (1)

**Tier 4 — Triage Safety (24 tests):**
Chest pain (4), Breathing (4), Blood (4), Consciousness (3), Seizure (2), Allergic severe (2), High fever (2), Mixed (3)

**Tier 5 — Duration Safeguard (31 tests):**
Parse duration values (4), Duration question coverage (1), Safe duration cases (5), Blocked duration cases (11), Edge cases at threshold (4), API endpoint tests (4), Threshold count verification (1), Duration chain to next symptom (1)

### Results
| Benchmark | Result |
|-----------|--------|
| 288-case structured benchmark | **288/288 exact (F1 = 1.000)** |
| 9-case semantic stress set | **9/9 exact** |
| 80-case real-user simulation | **72 exact / 8 partial / 0 failed** |
| **Combined** | **369/377 exact (97.9%), 0 failures** |

### Evaluation Metrics Used
- **Exact match:** detected symptoms == expected symptoms (set equality)
- **Partial match:** at least one correct symptom detected, no false positives
- **Failed:** wrong symptoms or empty when expected non-empty
- **F1 score:** harmonic mean of precision and recall per test case, averaged

---

## KEY TECHNICAL INNOVATIONS (for methodology/results chapters)

1. **Contrastive Boundary Negation** — splits on pero/but/kaso, evaluates negation per segment
2. **Fuzzy Rescue with Exclusion Sets** — Levenshtein matching with curated false-positive prevention
3. **COUGH_GENERAL Defer Strategy** — only blocks recommendation when cough is sole symptom
4. **ASG Source Attribution** — every recommendation traces to Package Insert / MIMS
5. **Paracetamol Overlap Detection** — warns on multi-paracetamol combinations
6. **Headache Heuristic Composition** — head_word + pain_word composable matching
7. **Universal Negation with Negated-Label Tracking** — all 13 labels protected, fuzzy rescue aware
8. **Per-Cue-Group Nasal Inference** — 3 independent cue groups with independent negation
9. **SORE_THROAT Proximity Detection** — reversed word order handling
10. **False Positive Exclusion Sets** — "tubo" ≠ COUGH, "pantalon" ≠ RASHES
11. **Adversarial Testing Methodology** — 64 tests across 19 categories
12. **Triage/Red-Flag Safety Layer** — 18 emergency flag types via 19 triage rules, multilingual
13. **External AI Audit Validation** — 6/7 Gemini suggestions already implemented
14. **No Fine-Tuning by Design** — pre-trained inference only, safety-first
15. **Precision-First Switching Logic** — semantic fires only when dictionary returns zero
16. **Chest-Congestion Direct Indicators** — bypass cough-word gate for chest-rattle expressions
17. **Allergen-Trigger Heuristic** — RASHES + allergen word → also ALLERGIC_RHINITIS
18. **Centralized Semantic Safety Filters** — 7 negation + red-flag suppression in one function
19. **19 bugs discovered and fixed** through systematic adversarial probing
20. **OLDCARTS Duration Safeguard Matrix** — universal duration safety across all 9 symptom categories with clinically-calibrated thresholds for Philippine endemic conditions (Dengue >3d fever, TB >14d cough per DOH protocol)

---

## LANGUAGES SUPPORTED

| Language | Coverage | Example |
|----------|----------|---------|
| Tagalog | Primary | "masakit ang ulo ko" |
| Bisaya/Cebuano | Primary | "labad akong ulo", "garas akong tilaok" |
| English | Full | "I have a headache and fever" |
| Taglish/Conyo (code-switch) | Full | "masakit head ko", "may cough ako" |
| Jejemon/Leetspeak | Full | "s@k1t ul0", "lgnat ako" |

---

## HARDWARE DEPLOYMENT TARGET

- **Device:** Raspberry Pi 5
- **OS:** Linux-based
- **Hardware:** Arduino Mega for dispensing control
- **Interface:** Touchscreen kiosk
- **Network:** Offline-capable (all processing is local)
- **ML Model size:** ~130MB (MiniLM, loaded lazily only when needed)

---

## WHAT THE METHODOLOGY CHAPTER SHOULD ACTUALLY SAY

### Research Design
- Iterative design science methodology with 3 cycles
- **Iteration 1:** Baseline v2.0 analysis, 13-label symptom taxonomy, pipeline architecture design
- **Iteration 2:** Dictionary expansion to ~260+ phrases, negation handling, fuzzy rescue, contrastive boundary logic, benchmark creation (288 test cases)
- **Iteration 3:** Semantic fallback integration, adversarial testing (64 cases), triage layer, safety filters, OLDCARTS Duration Safeguard Matrix (13 symptom-duration thresholds), error-driven refinement (19 bugs fixed), deployment optimization

### Theoretical Framework
- **Rule-Based NLP:** Deterministic dictionaries, regex, negation windows (Step 1)
- **Distributional Semantics:** Pre-trained multilingual sentence embeddings for paraphrase handling (Step 2, inference-only, NO fine-tuning)
- **Knowledge-Based Systems:** Structured medicine dataset with safety constraints (Step 4)
- **Hybrid justification:** Rules for safety+speed, embeddings for linguistic coverage, structured data for medical grounding
- **OLDCARTS Clinical Framework:** 5 components implemented — Character (cough type clarification), Onset (diarrhea food-poisoning context, headache hunger/dehydration detection), Aggravating (sipon allergy vs cold weather), Timing (sipon context), Duration (universal symptom-duration safety check with DOH-aligned thresholds)

### Data
- **Symptom dictionary:** 331 phrases across 13 labels, 5 language variants
- **Medicine dataset:** 24 OTC entries × 15 fields, sourced from Package Inserts/MIMS/DOH
- **Test benchmark:** 288 cases × 60 categories × 4 tiers
- **Additional validation:** 9 semantic stress cases + 80 real-user simulation cases
- **NO 1,039-entry corpus.** NO pharmacist annotation. The project uses ASG (Authoritative-Source-Grounded) framework because the domain expert could not complete annotation within timeline.
- **NO fine-tuning.** The MiniLM model is used pre-trained with inference only.

### Evaluation Protocol
- Exact match / partial match / failed classification
- F1 score (per-test precision/recall averaged)
- 4-tier testing: functional → robustness → adversarial → safety
- Out-of-benchmark stress testing to check for overfitting
- Regression testing: all changes re-validated against full 288-benchmark
