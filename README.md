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

## Hardware integration status

The current build is intentionally **payment-only**. The tested Allan D2 coin
path and TB74 D3 bill path are integrated with the Cashier and kiosk checkout
screens. A successful payment creates one receipt and deducts reserved stock
exactly once. Medicine motors are compile-time disabled: no paid checkout can
send a servo/rotor command in this phase.

The real controller runs at 115200 baud through the dedicated hardware daemon.
Simulator cash remains visibly labelled for software-only tests. This is a
prototype test gate, not production authorization; wiring, voltage, enclosure,
cashbox, restart-replay, and long-run acceptance evidence still require
completion. See the [hardware guide](hardware/README.md) and
[CHECKPOINT.md](CHECKPOINT.md) before connecting an Arduino.

## Ten-slot medicine catalog

Production recommendations, POS inventory, checkout, and benchmarks use one
versioned hardware catalog:
`mendo-hardware-catalog-v4-2026-10-15`. The formulation-level JSON remains the
medicine reference source. Nine medicines occupy the first nine slots;
Nutrabliss is sold separately as a digestive-health supplement in slot 10:

| Slot | Medicine | Runtime category | Form | Minimum age |
|---:|---|---|---|---:|
| 1 | Kremil-S | Antacid | Chewable Tablet | 12 |
| 2 | Bioflu | Cold & Flu | Tablet | 12 |
| 3 | Biogesic | Pain & Fever | Tablet | 12 |
| 4 | Cetirizine | Allergy | Tablet | 6 |
| 5 | Solmux | Cough with Phlegm / Productive Cough | Capsule | 12 |
| 6 | Sinecod | Cough Suppressant | Tablet | 13 |
| 7 | Symdex | Cold & Cough | Tablet | 6 |
| 8 | Buscopan | Antispasmodic | Tablet | 6 |
| 9 | Loperamide (Diatabs) | Anti-diarrhea | Capsule | 12 |
| 10 | Nutrabliss Daily Defense Probiotic | Digestive-health food supplement | Capsule | 12 |

Startup migrations normalize same-product aliases, assign hardware slots,
and mark retired products inactive. Newly introduced products start in separate
inventory rows with zero stock; existing records for the same product retain
their own stock. A different medicine's stock and history are never renamed
into a new drug. Historical transactions and stock movements remain.
Nutrabliss is purchasable through the retail catalog and uses the same cart,
reservation, stock deduction and receipt flow. It is separate from the nine
medicines used for symptom-based recommendations.
Food-poisoning guidance requires oral rehydration and excludes loperamide;
there is currently no approved stocked probiotic recommendation.

The pharmacist scope revision removes toothache from the supported symptom
labels. Dental cues remain as exclusion guards and yield a dentist/pharmacist
message when no supported symptom is present. The dictionary now contains
13 labels and 541 phrases. Stomach acidity routes to Kremil-S and cramping
routes to Buscopan. See the [Iteration 1 review](docs/research/iteration-1-results-discussion-review.md)
for evidence requirements, limitations, and thesis corrections. Restart the
application to reload the catalog and apply inventory synchronization; confirm
the actual stocked formulations, selling prices, and physical slot labels.

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
only an anonymous aggregate operational counter is incremented. Legacy
unconsented interactions are excluded from research exports and field metrics.

For a fresh hands-on event audit, follow the [convention logging guide](docs/convention-logging.md).
The preparation command archives the database, runtime logs, and local source
before clearing consultation audit records; inventory and commerce history remain.

The welcome screen offers direct medicine browsing or symptom consultation.
The kiosk catalog includes local reference photos, product details, stock,
prices and an age-checked cart. Diarrhea consultations use a ten-question
screen before the existing duration safeguard. Unsupported complaints get
named pharmacy guidance; urgent symptoms retain medical referral. See the
[October convention changes](docs/convention-kiosk-changes.md) for scope and sources.

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
- `mendo_core/medicine_catalog.py` — canonical hardware-slot allowlist and aliases
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
