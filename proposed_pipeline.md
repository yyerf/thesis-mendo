# Proposed Safety-First Retrieval Pipeline

This proposal keeps Mendo V3 as a deterministic safety-first OTC support system. It does not turn the system into a diagnosis chatbot.

## Preferred Architecture

```text
User input
  -> normalization
  -> deterministic safety layer
  -> deterministic symptom extraction
  -> embedding retrieval
  -> reranker
  -> deterministic safety filters
  -> safe OTC recommendation
  -> hardware dispense only after payment/auth/stock checks
```

The core policy:

```text
Deterministic safety rules always override model output.
```

## Pipeline Stages

### Stage A: Input Capture

Inputs:

- typed text
- optional STT transcript
- age
- severity
- duration answers
- context clarification answers
- optional known conditions

Output:

- normalized text
- raw text preserved for logging and audit

Design requirement:

- STT confidence or transcript source should be logged separately because STT errors can affect symptom detection.

### Stage B: Deterministic Safety Layer

Runs before embeddings.

Responsibilities:

- red-flag triage
- blood-context detection
- severe allergy detection
- pregnancy and hypertension safety context
- high fever at or above 40 C
- difficulty breathing
- seizure or loss of consciousness
- severe dehydration

Output:

```json
{
  "red_flags": [],
  "blocked": false,
  "safety_evidence": []
}
```

If `blocked=true`, the system may still log symptom interpretation for evaluation, but the user-facing recommendation is referral-only.

### Stage C: Deterministic Symptom Extraction

Use the current dictionary/rule system as the first symptom layer.

Output:

```json
{
  "symptoms": ["HEADACHE", "FEVER"],
  "source": "deterministic",
  "evidence": [
    {"label": "HEADACHE", "matched_phrase": "masakit ulo"}
  ],
  "conditions": ["HYPERTENSION"]
}
```

Why keep it:

- fastest
- most explainable
- safest under common phrasing
- easy to defend in thesis

### Stage D: Embedding Retrieval

Runs after deterministic safety and preferably only when one of these is true:

- dictionary found no symptom
- dictionary found a partial result and the system is configured to search for missed secondary symptoms
- input is semantically rich but lexical evidence is weak

Candidate corpus:

- symptom anchor documents
- approved indication snippets
- clarification-intent documents

Candidate example:

```json
{
  "id": "SYMPTOM:STOMACH_ACHE",
  "label": "STOMACH_ACHE",
  "text": "stomach pain, sakit tiyan, sakit akong tiyan, abdominal pain, kabag"
}
```

Embedding retrieval output:

```json
{
  "candidates": [
    {
      "label": "STOMACH_ACHE",
      "score": 0.78,
      "best_anchor": "sakit akong tiyan"
    }
  ]
}
```

### Stage E: Reranker

Rerank only top-k candidates, not the whole corpus.

Recommended top-k:

- symptom candidates: 5 to 10
- medicine indication candidates: 5 to 10

Reranker input:

```text
query: user's normalized text
document: candidate symptom or approved indication text
```

Reranker output:

```json
{
  "label": "COUGH_PRODUCTIVE",
  "rerank_score": 0.91,
  "evidence": "ubo na naay plema"
}
```

Safety rule:

- The reranker may reorder candidates.
- The reranker may not invent new labels.
- The reranker may not override red flags, negation, duration, age, or contraindications.

### Stage F: Semantic Safety Filters

Apply after retrieval and reranking.

Required filters:

- negation filter
- blood-context filter
- lexical guard
- red-flag suppressions
- cough dry/productive consistency
- maximum symptom count or calibrated threshold
- diagnosis-text filter if any model emits free text internally

Output:

```json
{
  "final_symptoms": ["COUGH_PRODUCTIVE"],
  "removed": [
    {"label": "CHEST_PAIN", "reason": "red_flag_or_out_of_scope"}
  ]
}
```

### Stage G: Clarification Layer

Clarification remains deterministic.

Ask a question when:

- `COUGH_GENERAL` is present
- diarrhea context is unsafe/unclear
- stomach ache context is unclear
- runny nose context is unclear
- duration is required

Do not ask open-ended medical questions that invite diagnosis.

### Stage H: Safe OTC Recommendation

Use deterministic recommendation over approved medicine data only.

Inputs:

- final symptom labels
- age
- conditions
- duration results
- red flags
- clarification answers
- inventory availability

Filters:

- red flags
- duration threshold
- age minimum
- contraindications
- condition safety
- paracetamol duplicate
- opposing cough mechanisms
- stock availability
- anti-hoarding policy

Output:

```json
{
  "action": "recommend",
  "recommendations": [
    {
      "medicine_id": "SKU:SOLMUX_CAPSULE",
      "brand": "Solmux",
      "reason": "productive_cough_match",
      "source": "Package Insert / MIMS Philippines",
      "warnings": []
    }
  ],
  "safety_warnings": []
}
```

### Stage I: Hardware Dispense Gate

Dispensing should occur only after:

- recommendation safety pass
- user selects medicine
- anti-hoarding check
- stock check
- fingerprint/auth check
- payment success or cashier approval
- hardware status ready

Dispense flow:

```text
paid -> reserve stock -> dispense command -> acknowledgement -> commit sale
```

If dispensing fails:

```text
paid -> reserve stock -> dispense failed -> manual review/refund path
```

## Explainability Design

Every user-facing recommendation should be traceable.

Minimum evidence:

- detected symptom
- source stage: dictionary, semantic, clarification
- matched phrase or best semantic anchor
- score if semantic
- medicine indication source
- safety filters applied
- warnings and contraindications checked

Example explanation:

```text
Detected: COUGH_PRODUCTIVE
Evidence: "naay plema" matched productive-cough rule
Recommendation: Solmux
Why: dataset row indicates productive cough/phlegm indication
Safety: no red flags, duration within threshold, age allowed, no contraindication found
```

## Model Selection in This Pipeline

Pi-local default:

- deterministic dictionary
- current MiniLM fallback
- optional Qwen3-Embedding-0.6B experiment only if quantized and benchmarked

Pi-local reranking:

- avoid by default
- allow top-3 or top-5 reranking only if latency is acceptable

Server-side optional:

- Qwen3-Embedding-4B/8B
- Qwen3-Reranker-4B/8B
- BGE-M3 full
- Jina Embeddings v3

If server inference fails:

- fall back to local deterministic + MiniLM.

## Implementation Contracts

### Symptom Result

```python
class SymptomResult:
    labels: list[str]
    conditions: list[str]
    red_flags: list[dict]
    evidence: list[dict]
    source: str
    latency_ms: dict
```

### Retrieval Candidate

```python
class RetrievalCandidate:
    label: str
    candidate_id: str
    text: str
    retrieval_score: float
    rerank_score: float | None
    evidence: dict
```

### Safety Decision

```python
class SafetyDecision:
    allowed: bool
    action: str
    blocked_reasons: list[str]
    warnings: list[str]
```

## Failure Modes and Safe Fallbacks

| Failure | Expected behavior |
| --- | --- |
| Embedding model unavailable | dictionary-only result |
| Reranker unavailable | embedding retrieval without rerank |
| All models unavailable | deterministic rules only |
| Red flag detected | no OTC recommendation |
| Hardware disconnected | do not dispense; show manual assistance |
| Payment verification failed | do not dispense |
| SKU out of stock | do not add to cart |
| Unknown symptom | ask user to rephrase or consult pharmacist |

## Why This Is Thesis-Friendly

The architecture can be defended as:

- deterministic where safety matters
- semantic only where phrasing variability matters
- retrieval-based rather than generative
- source-grounded for medicines
- explainable at every stage
- deployable locally with optional server enhancement
- benchmarkable and reproducible

## Sources

- Qwen3 Embedding model cards: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B and https://huggingface.co/Qwen/Qwen3-Embedding-8B
- Qwen3 Reranker model card: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
- BGE-M3 model card: https://huggingface.co/BAAI/bge-m3
- Jina Embeddings v3 documentation: https://jina.ai/news/jina-embeddings-v3-a-frontier-multilingual-embedding-model/
- Current MiniLM baseline: https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
