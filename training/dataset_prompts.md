# Dataset Prompt Templates (JSONL)

Use these prompts with an AI to generate **JSONL** training data that only uses canonical labels.

## Canonical labels (must use only these)
- cough
- headache
- fever
- sore_throat
- runny_nose
- stuffy_nose
- dizziness
- nausea
- vomiting
- diarrhea
- fatigue
- body_aches
- shortness_of_breath
- chest_pain
- stomach_ache

## Output format
One JSON object per line:
```
{"id":"ex001","text":"Ubo at lagnat","labels":["cough","fever"]}
```

## Prompt 1 — Single‑symptom sentences
Generate 200 JSONL lines. Each line should contain 1 symptom from the canonical list.
Use Tagalog, Bisaya, English, and code‑switching. Vary spelling and slang.
Output JSONL only, no extra text.

## Prompt 2 — Multi‑symptom sentences
Generate 200 JSONL lines. Each line should contain 2–3 symptoms from the canonical list.
Include natural mixed‑language sentences. Avoid adding any label outside the list.
Output JSONL only, no extra text.

## Prompt 3 — Negations and partial negations
Generate 100 JSONL lines with negations (e.g., “no fever but headache”).
Labels should reflect only the positive symptoms. Output JSONL only.

## Prompt 4 — Noisy/misspelled inputs
Generate 100 JSONL lines with misspellings, slang, and casual speech.
Map to canonical labels only. Output JSONL only.

## Prompt 5 — English‑only baseline
Generate 100 JSONL lines (English). Use canonical labels only. Output JSONL only.
