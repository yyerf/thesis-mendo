# Technology Used (Presentation Summary)

## Core Stack
- **Python** — main language for all backend logic and ML pipeline.
- **Flask** — lightweight web server and API for the app UI and endpoints.
- **Jinja2 + HTML/CSS/JS** — templated web pages and UI assets.

## NLP & ML
- **Rule-based NLP** — dictionary + regex + heuristics for symptom extraction (fast, explainable).
- **Sentence-Transformers** — multilingual semantic embeddings for fallback extraction.
- **PyTorch** — deep learning runtime used by sentence-transformers.
- **scikit-learn (legacy)** — optional SVM-based model and vectorizers for an older `/assess` page.
- **NumPy + Joblib** — numeric processing and model artifact loading.

## Speech-to-Text (Offline)
- **faster-whisper** (preferred) or **openai-whisper** — local speech transcription for WAV input.

## Data & Recommendations
- **JSON/JSONL datasets** — curated symptom–OTC mappings and evaluation files.
- **Rule-based recommender** — deterministic scoring and ranking of OTC options.

## Optional Infrastructure
- **MySQL + flask-mysqldb / PyMySQL** — optional shop/cart features.
- **SQLite** — zero-config POS/inventory system.
- **Serial hardware bridge** — optional Arduino-based vending/dispensing integration.

## Tooling & Evaluation
- **Benchmark scripts** — offline accuracy metrics for rule and ML models.
- **Training utilities** — dataset cleaning, synthetic data generation, and model comparison tools.

## Quick Clarifications (for Q&A)
- **TF‑IDF** — word-importance counting method; **not used** in the current pipeline.
- **Sentence‑BERT / paraphrase‑multilingual‑MiniLM‑L12‑v2** — **pretrained transformer** used for semantic similarity only (no training here).
- **Supervised learning** — **not done** in this system (no labeled training, no epochs).
- **Rule‑based dictionary** — **used** in Step 1 (deterministic rules/keywords).
- **Deep learning** — the transformer is deep learning, but we only **run inference**, so **no epochs**.
