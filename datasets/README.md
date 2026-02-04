# Datasets

## Format (JSONL)

One JSON object per line.

Required fields:
- `id`: string (unique example id)
- `text`: string (the input sentence)
- `labels`: array of canonical symptom labels

Example:
```json
{"id":"ex001","text":"Ubo at lagnat","labels":["cough","fever"]}
```

## Canonical labels

Use the keys in `symptom_models.SYMPTOM_PATTERNS` (lowercase):
- `cough`
- `headache`
- `fever`
- `sore_throat`
- `runny_nose`
- `stuffy_nose`
- `dizziness`
- `nausea`
- `vomiting`
- `diarrhea`
- `fatigue`
- `body_aches`
- `shortness_of_breath`
- `chest_pain`
- `stomach_ache`

## Files

- `symptom_eval.sample.jsonl`: small starter set you can benchmark immediately
- `symptom_eval.template.jsonl`: copy/append and grow your own dataset
