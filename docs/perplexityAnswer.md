# MendoVendo V3 — Context Summary for Panel Defense

## What This Project Is
MendoVendo is a **multilingual OTC medicine recommendation kiosk system** deployed on a Raspberry Pi 5. Users type free-text symptom descriptions in Filipino (Tagalog, Bisaya, English, or code-switched combinations), and the system recommends an appropriate over-the-counter medicine with dosage guidance.

---

## Version History

| Version | Core Tech | Drug Coverage | Accuracy |
|---|---|---|---|
| V1 | Flask + SVM (TF-IDF) | 5 drugs, ~137 training rows | ~81% (inflated by leakage) |
| V2 | Flask + SVM (TF-IDF), Blueprint architecture | Same 5 drugs, expanded tests | 38.9–39.5% on clean CSV, 75% with mapped labels |
| V3 (current) | Rule-based + MiniLM embeddings + Knowledge Graph | 26 drugs, 15 symptom labels, 2,170+ eval entries | Benchmarked per model (see below) |

V1 and V2 predicted a **drug name directly** from input using a bag-of-words SVM. V3 classifies a **symptom label** first, then scores all 26 drugs via a knowledge graph. Completely different architecture.

---

## V3 NLP Pipeline (4 Steps)

```
User Input (Tagalog / Bisaya / English / Code-switched)
        ↓
Step 1: Rule-Based Extraction
        Dictionary + Regex + Negation Parser + Levenshtein Fuzzy Matching
        ~522 curated phrases across 15 symptom labels
        ↓ (if match found → skip Step 2)
Step 2: Semantic Embedding Fallback
        paraphrase-multilingual-MiniLM-L12-v2 (90MB, CPU-only)
        Cosine similarity against symptom prototype embeddings
        ↓
Step 3: Hybrid Cascade Orchestrator
        Combines Step 1 + Step 2 outputs
        ↓
Step 4: Knowledge-Based OTC Scoring
        Scores all 26 drugs from Mendo-Datasets.json
        Rules: symptom match, age restrictions, contraindications, dosage
        ↓
Recommended Medicine + Dosage + Age Guidance
```

---

## 15 Symptom Labels
`HEADACHE`, `FEVER`, `COUGH_DRY`, `COUGH_PRODUCTIVE`, `COUGH_GENERAL`, `RUNNY_NOSE`, `NASAL_CONGESTION`, `SORE_THROAT`, `STOMACH_ACHE`, `NAUSEA`, `VOMITING`, `DIARRHEA`, `BODY_ACHES`, `DIZZINESS`, `FATIGUE`

---

## Dataset State (Actual File Counts)

| File | Count | Purpose |
|---|---|---|
| `symptom_eval.whole.jsonl` | 2,170 entries | Full labeled evaluation corpus |
| `symptom_eval.synthetic.jsonl` | 1,800 entries | Synthetically generated (negation, abbreviation, multi-symptom) |
| `symptom_eval.sample.jsonl` | 70 entries | Hand-curated seed |
| `st_pairs.sample.jsonl` | 252 pairs | Sentence-pair data for MiniLM fine-tuning |
| `userInquiry.txt` | 1,039 entries | Real-user style inquiries for domain expert annotation |

`userInquiry.txt` covers: Bisaya, Tagalog, English, code-switched, slang/jejemon, negations, abbreviations, multi-symptom combos, profanity/emotional expressions. Cleaned from 1,000 to 939, then expanded with 50 DIARRHEA + 50 SORE_THROAT entries.

---

## 26 OTC Drugs in Knowledge Graph

**Categories:** Allergy (5), Cold (3), Cold & Cough (3), Expectorant (3), Pain & Fever (3), Cough (2), Cough Suppressant (1), Anti-diarrhea (2), GI/Probiotic (1), Antacid (1), Pain & Inflammation (1), Cold & Sinus (1), Cold & Flu (1)

**Notable drugs:** Bioflu, Neozep, Decolgen, Biogesic, Advil, Cetirizine, Loperamide (Diatabs), Erceflora, Kremil-S, Claritin, Allerta, Solmux, Sinecod, Ascof, Robitussin, Sinutab, Benadryl AH, Aspirin

**Thesis claimed ~40–60 drugs — current confirmed scope is 26.** Gap of 14–34 drugs still needed (e.g., Mefenamic acid, ORS/Hydrite, Betadine gargle, Strepsils, Omeprazole).

---

## Semantic Model Benchmarks (CPU, threshold sweep 0.40–0.85)

| Model | Best F1 | Recall | Inference |
|---|---|---|---|
| paraphrase-multilingual-MiniLM-L12-v2 | 0.409 | 0.460 | ~4.6ms |
| paraphrase-multilingual-mpnet-base-v2 | 0.335 | 0.390 | ~14.5ms |
| LaBSE | 0.550 | 0.910 | ~13ms |

**LaBSE has better quality but V3 uses MiniLM** for RPi5 deployment reasons: 90MB vs 1.8GB RAM, 3× faster inference, fits within Raspberry Pi 5 8GB constraint alongside Flask + MySQL.

---

## Hardware Deployment Target
- **Raspberry Pi 5**, ARM Cortex-A76, 8GB LPDDR4X, **no GPU**
- CPU-only inference — rules out anything >500MB RAM or >50ms latency
- MiniLM: 90MB RAM, ~4.6ms/query ✅
- LaBSE: ~1.8GB RAM, ~13ms/query ⚠️ (borderline)
- Any 4B/7B LLM: impossible on RPi5 kiosk

---

## Missing Chapter 3 Sections (Panel Defense Gaps)

### 1. Conceptual Framework
Exists in `thesis-methods.md` as ASCII diagram. Needs to be formalized as a proper figure in the Word doc.

### 2. Design Procedure
- Physical: RPi5 + touchscreen + optional mic (Whisper STT) + optional thermal printer
- Software: Flask, sentence-transformers, scikit-learn, PyTorch CPU, MySQL, SQLAlchemy

### 3. Testing Procedures
- **Intrinsic**: F1/precision/recall on `symptom_eval.whole.jsonl` (2,170 entries), benchmark CSV files in `testing/benchmark/results/`
- **Extrinsic**: Domain expert annotation of `userInquiry.txt` (1,039 entries), kiosk user testing
- **No data leakage** — V2 explicitly documented 7/38 curated test cases leaked from training. V3 has a clean split.

### 4. Development Tools

| Category | Tool | Purpose |
|---|---|---|
| Language | Python 3.11 | Core |
| Web | Flask 3.x | Kiosk UI |
| NLP | sentence-transformers | Step 2 embeddings |
| ML | scikit-learn | Optional symptom classifier |
| DL | PyTorch (CPU) | Model inference |
| DB | MySQL + SQLAlchemy | POS module |
| Hardware | Raspberry Pi OS Bookworm 64-bit | Deployment |

### 5. Work Plan / Gantt Chart
Not in codebase — must be reconstructed from git history and timeline.

### 6. Line-Item Budget
Raspberry Pi 5 8GB (~₱4,500), SD card + accessories (~₱800), touchscreen (~₱2,500–5,000), optional thermal printer (~₱3,000), misc (~₱500).

---

## 7. Theoretical Framework — Switching from IR Theory

**V1 and V2 used Information Retrieval (IR) Theory** — correct for TF-IDF + SVM because that architecture literally retrieves the closest matching "document" (drug label) from a term-frequency corpus. IR Theory is the right citation for bag-of-words retrieval.

**V3 is NOT using IR Theory** — TF-IDF is completely gone. V3 uses three distinct theoretical bases:

| Step | Theory | Citation Basis |
|---|---|---|
| Step 1 (dictionary + regex + negation) | **Rule-Based NLP / Computational Linguistics** | Explicit linguistic rules encode domain expert knowledge as formal grammar patterns |
| Step 2 (MiniLM cosine similarity) | **Distributional Semantics Theory** | "Words that appear in similar contexts have similar meanings" — Mikolov et al. (2013), Reimers & Gurevych (2019, SBERT) |
| Step 4 (knowledge graph scoring) | **Knowledge-Based Expert Systems Theory** | Structured medical domain knowledge encoded as scoring rules — similar to MYCIN/clinical decision support systems |
| Overall cascade design | **Hybrid NLP Systems** | Deterministic path first (fast), statistical fallback when deterministic fails — resource-aware architecture |

**Recommended framing for panel:** V3 transitions from Information Retrieval Theory to a **hybrid of Distributional Semantics Theory and Knowledge-Based Expert Systems Theory**, motivated by the need for multilingual semantic generalization (IR fails on unseen Bisaya/code-switched variants) and safety-conscious drug recommendation (a knowledge graph enforces dosage and age rules that a statistical model cannot guarantee).

This is a defensible and honest upgrade story: V1/V2 used IR because they were retrieval systems. V3 uses Distributional Semantics because it needs to generalize across languages, and Expert Systems because clinical safety requires explicit rule enforcement, not probabilistic outputs.

---

## Annotation System (In Progress)
- **Schema**: `domain_expert_annotations.template.json` — fields: `entry_id`, `user_inquiry`, `user_age`, `language` (required, never null), `symptom_labels[]`, `suggested_otc.selected[]`, `min_age`, `has_age_restrictions`, dosage guide per drug
- **Annotator prompt**: `annotator_prompt.md` — 5 rules, dosage reference table, 26-drug list, safety escalation triggers, 4 worked examples
- **Language field** must always be one of: `tagalog`, `bisaya`, `english`, `code-switched` — never null
- **Required fields**: `entry_id`, `user_inquiry`, `language`, `symptom_labels`, `suggested_otc.selected`, `min_age`, `has_age_restrictions`, `confidence`, `annotated_by`, `annotated_at`
- **Conditional required**: `known_contraindications_details` only if `has_known_contraindications: true`; dosage guide required per drug in `selected[]`
