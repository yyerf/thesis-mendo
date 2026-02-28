# MendoVendo V3 — Multilingual OTC Medicine Recommendation Kiosk

NLP pipeline that accepts free-text Filipino/English symptom input and recommends appropriate over-the-counter medicines. Designed for Raspberry Pi 5 kiosk deployment (CPU-only, no GPU).

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the kiosk app
python app.py
```

Open: **http://localhost:5000**

> First run downloads the embedding model (~90MB). Happens once.

---

## Project Structure

```
mendo-testing/
├── app.py                        # App launcher (entry point)
├── requirements.txt
│
├── mendo_core/                   # Core NLP pipeline (Steps 1–4)
│   ├── step1.py                  # Rule-based symptom extraction
│   ├── step2.py                  # Semantic embedding fallback (MiniLM)
│   ├── step3_hybrid.py           # Hybrid cascade orchestrator
│   ├── step4_recommend.py        # Knowledge-based OTC scoring
│   └── symptom_models.py         # Symptom label definitions + model registry
│
├── web/                          # Flask web application
│   ├── app.py                    # Routes, STT endpoint, kiosk UI
│   ├── templates/                # Jinja2 HTML templates
│   └── static/                   # CSS, JS, medicine SVG images
│
├── pos/                          # Point-of-Sale module
│   ├── db.py                     # SQLAlchemy models
│   ├── auth.py                   # Admin authentication
│   ├── routes_admin.py           # Admin routes
│   └── routes_shop.py            # Shop/inventory routes
│
├── hardware/                     # Arduino + serial bridge
│   ├── serial_bridge.py          # Python ↔ Arduino serial interface
│   ├── mendo_vendo_v2.ino        # Current Arduino firmware
│   └── config.json               # Hardware pin/serial config
│
├── training/                     # Model training scripts only
│   ├── train_sentence_transformer.py   # Fine-tune MiniLM on symptom pairs
│   ├── train_symptom_classifier.py     # Train TF-IDF + LogReg classifier
│   ├── clean_dataset.py                # Dataset cleaning utilities
│   ├── generate_synthetic_dataset.py   # Synthetic data generation
│   ├── validate_dataset.py             # JSONL dataset validation
│   ├── convert_testing_csv_to_jsonl.py # CSV → JSONL conversion
│   └── README.md                       # Training guide
│
├── benchmarks/                   # All benchmark and evaluation scripts
│   ├── benchmark_full.py         # End-to-end pipeline benchmark (Steps 1–4)
│   ├── benchmark_semantic_models.py    # Semantic model comparison (MiniLM/LaBSE/MPNet)
│   ├── benchmark_ml_vs_rules.py        # ML classifier vs rule-based baseline
│   ├── benchmark_pipeline.py           # Per-label symptom extraction metrics
│   ├── compare_models_cli.py           # Interactive model comparison CLI
│   └── results/                        # Benchmark output CSVs and JSONs
│
├── testing/                      # Integration and algorithm tests
│   ├── test_algorithm.py         # Step-by-step pipeline tests
│   ├── testing.csv               # Manual test cases
│   └── README.md
│
├── data/
│   ├── datasets/
│   │   ├── Mendo-Datasets.json         # 26-drug knowledge graph (Step 4)
│   │   ├── symptom_eval.whole.jsonl    # Full labeled eval corpus (2,170 entries)
│   │   ├── symptom_eval.synthetic.jsonl
│   │   ├── symptom_eval.sample.jsonl   # Hand-curated seed (70 entries)
│   │   ├── symptom_eval.user_additions.jsonl
│   │   ├── symptom_eval.from_testing.jsonl
│   │   ├── st_pairs.sample.jsonl       # Sentence-pair fine-tuning data (252 pairs)
│   │   ├── symptom_master_labels.json  # Canonical 15-label schema
│   │   ├── annotation/                 # Domain expert annotation workspace
│   │   │   ├── userInquiry.txt         # 1,039 real-user inquiries for annotation
│   │   │   ├── annotator_prompt.md     # System prompt for the annotator tool
│   │   │   └── domain_expert_annotations.template.json
│   │   └── README.md
│   └── Mendo-Datasets.xlsx
│
├── tools/                        # Utility scripts
│   ├── stt.py                    # Speech-to-text helper
│   └── update_mendo_dataset.py   # Dataset update utility
│
└── docs/                         # Thesis and project documentation
    ├── architecture.md           # System architecture + algorithm details
    ├── thesis-methods.md         # Chapter 3 methodology reference
    ├── model_summary.md          # Model comparison summary
    ├── technology.md             # Development tools and stack
    ├── training.md               # Training process overview
    ├── FULLEXP.md                # Full plain-language system explanation
    ├── presentation.md           # Panel presentation notes
    ├── perplexityAnswer.md       # Context summary for AI assistance
    └── archive/
        └── oldApp.py             # V1 app (archived reference)
```

---

## NLP Pipeline

```
User Input (Tagalog / Bisaya / English / Code-switched)
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  Step 1: Rule-Based Extraction                      │
│  Dictionary + Regex + Negation + Fuzzy Matching     │
│  ~522 phrases · 15 symptom labels                   │
└─────────────────────────────────────────────────────┘
        │ match found → skip Step 2
        ▼
┌─────────────────────────────────────────────────────┐
│  Step 2: Semantic Embedding Fallback                │
│  paraphrase-multilingual-MiniLM-L12-v2              │
│  Cosine similarity · CPU-only · ~4.6ms/query        │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  Step 3: Hybrid Cascade Orchestrator                │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────┐
│  Step 4: Knowledge-Based OTC Scoring                │
│  26 drugs · dosage · age restrictions · safety      │
└─────────────────────────────────────────────────────┘
        │
        ▼
   Recommended Medicine + Dosage + Age Guidance
```

---

## Test Inputs

```
masakit ang ulo ko at may lagnat       → HEADACHE, FEVER
I have cough and sipon                 → COUGH, RUNNY_NOSE
labad ang ulo ug init ang lawas        → HEADACHE, FEVER  (Bisaya)
LBM nako grabe dili mohunong           → DIARRHEA
Sakit akong tutunlan lisod motulon     → SORE_THROAT
```

---

## Running Benchmarks

```bash
# End-to-end pipeline benchmark
python benchmarks/benchmark_full.py

# Semantic model comparison (MiniLM vs LaBSE vs MPNet)
python benchmarks/benchmark_semantic_models.py \
  --dataset data/datasets/st_pairs.sample.jsonl

# ML classifier vs rule-based
python benchmarks/benchmark_ml_vs_rules.py \
  --data data/datasets/symptom_eval.from_testing.jsonl \
  --model training/symptom_classifier.joblib

# Per-label symptom extraction metrics
python benchmarks/benchmark_pipeline.py \
  --dataset data/datasets/symptom_eval.whole.jsonl --all-models
```

---

## Documentation

| File | Contents |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Full pipeline algorithm details |
| [docs/thesis-methods.md](docs/thesis-methods.md) | Chapter 3 methodology reference |
| [docs/model_summary.md](docs/model_summary.md) | Model benchmark results |
| [training/README.md](training/README.md) | How to train/fine-tune models |
| [benchmarks/README.md](benchmarks/README.md) | How to run each benchmark |
| [data/datasets/README.md](data/datasets/README.md) | Dataset formats and labels |
