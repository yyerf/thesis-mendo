# Domain-Expert Questionnaire + Data Collection Sheet (Mendo Step 2 Fine-Tuning)

Use this document directly with your pharmacist/clinician/domain expert.

## A) Scope and Goal
We are collecting sentence pairs to fine-tune a multilingual SentenceTransformer for semantic symptom matching.

Target pair format:
- `text1`
- `text2`
- `label` (`1` = same symptom meaning, `0` = different meaning)

The model should handle English, Tagalog, Bisaya, code-switching, slang, and misspellings.

---

## B) Exact Symptom Set (must use these exact tags)
Use only these symptom tags (mapped to current Step 2 anchors):

1. `HEADACHE`
2. `COUGH_DRY`
3. `COUGH_PRODUCTIVE`
4. `COUGH_GENERAL`
5. `FEVER`
6. `BODY_ACHES`
7. `NASAL_CONGESTION`
8. `RUNNY_NOSE`
9. `ALLERGIC_RHINITIS`
10. `RASHES`
11. `DIARRHEA`
12. `STOMACH_ACHE`

Master vocabulary reference for website/backend consistency:
- [data/datasets/symptom_master_labels.json](data/datasets/symptom_master_labels.json)

If your website can store all labels, use the `master_labels` list from that file.
For Step 2 embedding fine-tuning specifically, prioritize the 12 tags above.

---

## C) Questionnaire for Domain Expert (ready to send)

### 1) Symptom Expressions
For each symptom tag above, provide:
- 20 common patient statements
- 10 slang/vernacular variants
- 10 misspelled/noisy variants
- 10 code-switch statements (Tagalog/Bisaya/English mixed)

### 2) Negation and Exclusion
For each symptom tag, provide:
- 8 explicit negation forms (example: “wala akong lagnat”)
- 8 similar-sounding but NOT-the-symptom phrases
- 5 “false friend” phrases often confused with this symptom

### 3) Hard Negatives (critical)
Provide at least 15 confusion pairs per symptom where wording overlaps but meaning differs.
Examples:
- `HEADACHE` vs `STOMACH_ACHE`
- `FEVER` vs feeling hot due to weather
- `COUGH_DRY` vs `COUGH_PRODUCTIVE`

### 4) Ambiguity Rules
For each symptom tag, define:
- minimum wording needed to count as that symptom
- borderline examples to mark as uncertain
- when to avoid assigning any symptom

### 5) Language Prioritization
Give estimated language mix of real users (%):
- English: ___%
- Tagalog: ___%
- Bisaya: ___%
- Code-switch: ___%

---

## D) Annotation Rules (for pair labels)

### Label = 1 (Similar)
Use `1` only if both sentences express the same symptom intent.
- Same language or cross-language is okay.
- Slang/paraphrase is okay.
- Minor detail differences are okay if core symptom is same.

### Label = 0 (Not Similar)
Use `0` if symptom intent differs.
- Includes hard negatives.
- Includes negation mismatch (positive vs negated symptom).

### Special rules
- If uncertain, set `review_status = needs_review`.
- Avoid medical diagnosis labels (flu, COVID, dengue) unless explicitly mapped to symptom wording only.

---

## E) Data Collection Sheet Schema (for your website)
Use these fields in your form/database:

- `pair_id` (string, unique)
- `text1` (string)
- `text2` (string)
- `label` (0 or 1)
- `symptom_primary` (one of exact tags above)
- `symptom_secondary` (optional; for difficult negatives)
- `pair_type` (paraphrase | translation | slang | typo | negation | hard_negative | code_switch)
- `language_text1` (en | tl | ceb | mixed)
- `language_text2` (en | tl | ceb | mixed)
- `confidence` (1-5)
- `review_status` (approved | needs_review)
- `expert_id` (string)
- `notes` (optional)

---

## F) Minimum Dataset Targets (defense-friendly)
Suggested minimum before first fine-tune:
- 1,200 total pairs
- 600 positive + 600 negative
- At least 80–100 positive pairs per symptom tag
- At least 40 hard negatives per symptom tag
- At least 15 negation pairs per symptom tag

Better target:
- 2,400+ pairs for stronger generalization

---

## G) JSONL Export Format (from website)
Export exactly as JSONL for training script compatibility:

`{"text1":"...","text2":"...","label":1}`

Optional metadata can be kept in your DB or in a separate export file.

---

## H) Quality Checklist Before Training
- [ ] No empty `text1`/`text2`
- [ ] Label only 0/1
- [ ] Balanced positives/negatives
- [ ] Each symptom sufficiently covered
- [ ] Negations included
- [ ] Hard negatives included
- [ ] Random sample manually audited by expert

---

## I) Copy-Paste Message You Can Send to Domain Expert
We are building a multilingual symptom understanding system. Please provide real-world patient phrasing (English/Tagalog/Bisaya/code-switch) for these exact symptom tags: HEADACHE, COUGH_DRY, COUGH_PRODUCTIVE, COUGH_GENERAL, FEVER, BODY_ACHES, NASAL_CONGESTION, RUNNY_NOSE, ALLERGIC_RHINITIS, RASHES, DIARRHEA, STOMACH_ACHE.

For each tag, please provide common phrases, slang, misspellings, and negations. We also need hard-negative examples where wording is similar but symptom meaning is different. We will use pair labels only: 1 (same meaning) and 0 (different meaning).
