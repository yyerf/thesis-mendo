# Iteration-2 Pharmacist Validation Protocol (MendoVendo v3.0)

**Purpose.** Independent, human-derived accuracy for the kiosk's symptom
detection. The 288-case benchmark is LLM-generated synthetic input (regression
coverage only — never claim it as independent accuracy). This protocol is the
evidence source the thesis describes as *Iteration-2 field validation*.

**Role.** One licensed pharmacist (PH) reviews anonymized kiosk-style inputs
and assigns expected symptom labels. Annotator disagreements with the engine
are the honest accuracy signal.

---

## 1. Privacy (RA 10173 / PH Data Privacy Act)

- The export identifies each case **only** by `id = "mendo-" + sha256(input)[:16]`.
- No patient name, age, contact, or transaction data is included.
- **Inputs are clinical in nature** (users describe symptoms). The export
  file must stay on the device or in secured research storage; never commit
  it to the repository or transmit it unencrypted.
- Do not re-identify inputs; discuss cases by id, not by content, outside
  secured review.

## 2. Exporting a validation set

```
python testing/validation/export_validation_set.py --max 100 --seed 7 ^
    --out testing/validation/export_validation.jsonl
```

- Sources: the kiosk interaction log (`logs/interactions.jsonl`) first, then
  the 288-case benchmark for label coverage.
- Sampling is stratified (every label the engine detects keeps a
  representative) with a fixed seed, capped at `--max`.
- The exporter runs the live pipeline and records `detected`,
  `engine_id`, `engine_available`, and `latency_ms` — the comparison
  baseline for the annotator's labels.

## 3. Annotation instructions (for the pharmacist)

1. Read each `input` sentence as if a customer typed it at the kiosk.
2. Write the symptom labels that match **your clinical reading**, using only
   the 14-label vocabulary below. Use `NONE` when no symptom is present
   (chit-chat, questions, "wala po akong sakit").
3. Label **symptom classes**, not every word: "masakit ulo at nilalagnat"
   -> `HEADACHE,FEVER`; "ubo na may plema" -> `COUGH_PRODUCTIVE` (not
   `COUGH_GENERAL`).
4. Sore throat vs cough: "lalamunan/tutunlan/throat" with pain or difficulty
   swallowing -> `SORE_THROAT`. "Bara/garas/kaskas" (obstruction/scratchy) in
   the throat -> `SORE_THROAT` (clear-secretion distinction rationale is in
   the thesis; the 520 sheet's throat->Cough annotation clash is a known
   dataset quirk, not a clinical rule).
5. Toothache -> `TOOTHACHE` (dictionary-only label; the semantic stage has
   no TOOTHACHE head).
6. `NASAL_CONGESTION` (blocked/stuffy/barado) vs `RUNNY_NOSE` (sipon
   flowing) are distinct; both together is allowed.
7. Negated symptoms are not symptoms: "walang ubo" -> `NONE`, not
   `COUGH_*`.
8. Red-flag presentations (danger signs like stiff neck + fever, one-sided
   weakness, fainting, pregnancy + headache) are still labeled for their
   *symptoms*; their refer decision is the pipeline's job, not the label's.

**Vocabulary (14):** HEADACHE, FEVER, COUGH_GENERAL, COUGH_DRY,
COUGH_PRODUCTIVE, SORE_THROAT, STOMACH_ACHE, BODY_ACHES, DIARRHEA,
NASAL_CONGESTION, RUNNY_NOSE, RASHES, ALLERGIC_RHINITIS, TOOTHACHE — plus
`NONE`.

## 4. Annotation file format

CSV (3 columns) or JSONL:

```
id,input,expected
mendo-3f9a...,masakit ulo ko,HEADACHE
mendo-9c1b...,wala po akong sakit,NONE
```

- `expected`: comma-separated labels, or `NONE`. Leave empty to mark
  "not annotated" (row is skipped).

## 5. Ingesting annotations

```
python testing/validation/import_annotations.py --in annotated.csv
```

- Validates every `id` against `sha256(input)` (tamper/typo guard),
  checks the label vocabulary, dedupes against existing rows, and appends
  to `testing/benchmark/pharmacist_validated.jsonl`.
- The classifier training script picks that file up as a fourth source on
  the next retrain (see `train_semantic_classifier.load_training_rows`).

## 6. Reporting (never inflate)

- Report annotator-vs-engine **exact-match and per-label agreement** on the
  annotated rows, with `engine_id` recorded per row.
- The 288/288 synthetic benchmark stays a *regression* result; the
  pharmacist set is the *accuracy* result. Cite both, labeled distinctly.