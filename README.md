# Mendo

Mendo is a multilingual, knowledge-based expert system for OTC consultation and
medicine vending. It combines deterministic English/Tagalog/Cebuano phrase and
safety rules with the pretrained
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` embedding model.
MiniLM cosine similarity supports phrase interpretation; it is not a trained
clinical classifier and its scores are not probabilities.

## Run locally

Python 3.10+ is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Open `http://localhost:5000`. On first run, Mendo creates
`data/mendo_pos.db`, applies additive migrations, seeds the inventory, and
downloads MiniLM if it is not already cached. The runtime database, journals,
application logs, and raw consultation logs are intentionally ignored by Git.

The seeded administrator is for first-run development only:

- Username: `admin`
- Password: `mendo2026`

Change the password immediately in any shared or deployed environment, and set
`MENDO_SECRET_KEY` to a stable secret.

## Consultation and audit flow

1. The participant accepts or declines multilingual research consent.
2. Dictionary rules record matched, negated, and safety-suppressed evidence.
3. MiniLM records its model id, anchors, threshold, and cosine similarities.
4. Expert rules resolve symptom labels, red flags, severity, duration,
   clarification, age, headache illustration, and recommendation filtering.
5. Consented consultations are stored as session timelines for independent
   domain-expert review.
6. An administrator adjudicates disagreements into a final gold annotation.
7. Only consented and adjudicated records enter research exports or field
   validation metrics. Nothing automatically retrains production.

Declining consent does not block consultation. Raw health text is not persisted;
only an anonymous aggregate operational counter is incremented. The 507
pre-consent interactions retained during merge recovery are marked
legacy/unconsented and excluded from research exports and field metrics.

## Evaluation terminology

- **Synthetic technical benchmark**: researcher/LLM-created regression cases in
  `testing/benchmark/testing.csv`. This is technical evidence, not clinical
  field validation.
- **Domain-expert field validation**: independently reviewed, consented
  consultations with administrator-adjudicated gold labels.
- **Per-case precision, recall, F1, and exact match**: computed only after
  adjudication.
- **Micro F1**: pools label decisions across all eligible cases.
- **Macro F1**: averages performance across labels.
- **Cohen’s kappa**: shown only when at least two reviewers share reviewed
  cases; otherwise the interface reports “insufficient reviewers.”
- **Clinical appropriateness**: the proportion of adjudicated recommendation
  judgments marked appropriate among appropriate/inappropriate judgments.

Run verification:

```bash
python3 -m unittest discover -s testing -p 'test_*.py' -v
python3 testing/test_algorithm.py
```

The benchmark script uses the same `predict_symptoms` service as
`/consult/api/analyze`, reports both raw-input and guided-clarification metrics,
and writes the single tracked manifest at
`testing/benchmark/results/current.json`. Timestamped HTML/CSV runs are ignored.

## Repository map

- `mendo_core/prediction_pipeline.py` — deployed, versioned prediction service
- `mendo_core/interaction_logger.py` — consent, audit, reviews, adjudication,
  metrics, and de-identified exports
- `pos/routes_consultation.py` — consultation APIs
- `pos/routes_admin.py` — restricted clinical audit APIs
- `web/templates/pos/logs.html` — session-oriented reviewer interface
- `testing/benchmark/results/current.json` — current synthetic benchmark manifest
- `docs/thesis/current/` — canonical thesis and synchronized comments document
- `docs/thesis/archive/` — prior DOCX/PDF revisions retained in history
- `docs/research/` — research audits and diagrams
- `docs/defense/` — defense notes and presentation material

The ignored `_For-Mendo/` five-brand SVM prototype is not a production
dependency and is not imported by the application.

See [docs/README.md](docs/README.md) for the document index.
