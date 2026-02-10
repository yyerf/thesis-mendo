# Technical Specifications
## Complete System Architecture & Implementation Details

**Version:** 2.0 (with ML Classifier V2)  
**Last Updated:** February 10, 2025

---

## System Architecture

### High-Level Overview
```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE (Flask)                    │
│  - Web app (HTML/CSS/JS)                                    │
│  - Voice input (Whisper STT)                                │
│  - Text input (multilingual)                                │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                 NLP PIPELINE (Hybrid)                        │
│  Step 1: Dictionary → Step 2: ML → Step 3: Semantic         │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│              RECOMMENDATION ENGINE                           │
│  - Age-based filtering                                       │
│  - Symptom matching                                          │
│  - Safety warnings                                           │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│                   MEDICATION DATABASE                        │
│  - 200+ OTC medications                                      │
│  - Symptom mappings                                          │
│  - Age restrictions                                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Specifications

### 1. ML Classifier (Core Innovation)

#### Algorithm
**TF-IDF + Logistic Regression (Multi-label)**

**Vectorizer Configuration:**
```python
TfidfVectorizer(
    max_features=5000,      # Top 5000 words
    ngram_range=(1, 3),     # Unigrams, bigrams, trigrams
    min_df=2,               # Min document frequency
    sublinear_tf=True,      # Use log(tf)
    lowercase=True,         # Case normalization
    strip_accents='unicode' # Remove accents
)
```

**Feature Engineering:**
- **Unigrams (1-gram):** ["sepun", "ako", "grabe"]
- **Bigrams (2-gram):** ["sepun ako", "ako grabe"]
- **Trigrams (3-gram):** ["sepun ako grabe"]
- **Character n-grams:** Effectively captured via word n-grams

**Why n-grams handle typos:**
```
"sepun" and "sipon" share:
- Letters: s, p, n
- Bigrams: "se", "ep", "pu", "un" vs "si", "ip", "po", "on"
- Overlap: Sufficient for TF-IDF similarity
```

#### Classifier Configuration
```python
OneVsRestClassifier(
    LogisticRegression(
        max_iter=1000,          # Max optimizer iterations
        C=1.0,                  # Regularization (inverse)
        solver='lbfgs',         # L-BFGS optimizer
        random_state=42,        # Reproducibility
        class_weight='balanced' # Handle class imbalance
    ),
    n_jobs=-1                   # Parallel training
)
```

**Multi-label Approach:**
- 15 binary classifiers (one per symptom)
- Independent predictions joined with OR
- Allows multiple symptoms per input

#### Model Versions

| Property | V1 | V2 |
|----------|----|----|
| Training Samples | 2,170 | 3,670 |
| Features | 3,016 | 3,633 |
| Threshold | 0.5 | **0.2** |
| File Size | 0.47 MB | 0.57 MB |
| F1 (at threshold) | 91.2% | 74.8% |
| Typo Accuracy | 66.7% | **100%** |
| Cebuano Support | Minimal | Comprehensive |

### 2. Dictionary Matching

#### Implementation
**File:** `mendo_core/step3_hybrid.py`

**Method:** Regex pattern matching

```python
SYMPTOM_KEYWORDS = {
    "FEVER": [
        r"\b(fever|lagnat|init|hilanat)\b",
        r"\b(high temperature|may init)\b",
        r"\blagnat na lagnat\b"
    ],
    "COUGH": [
        r"\b(cough|ubo|tusok)\b",
        r"\bmay ubo\b",
        r"\bubo ubo\b"
    ],
    # ... 13 more symptoms
}
```

**Process:**
1. Normalize text (lowercase, strip punctuation)
2. Check each regex pattern
3. Return matched symptoms immediately

**Performance:**
- Latency: ~1ms
- Precision: Very high (exact matches)
- Recall: Low (no typo tolerance)

### 3. Semantic Fallback

#### Model
**sentence-transformers/all-MiniLM-L6-v2**

**Specifications:**
- Embedding dimension: 384
- Model size: 80 MB
- Speed: ~50ms per inference

#### Process
```python
# 1. Encode user input
user_embedding = model.encode(user_input)

# 2. Encode symptom templates
for symptom, template in TEMPLATES.items():
    template_embedding = model.encode(template)
    
    # 3. Compute cosine similarity
    similarity = cosine_similarity(
        user_embedding,
        template_embedding
    )
    
    # 4. Threshold filtering
    if similarity >= 0.65:
        detected.append(symptom)
```

**Configuration:**
```python
semantic_threshold = 0.65       # Min similarity
semantic_top_margin = 0.08      # Gap between top 2
semantic_max_symptoms = 3       # Max detections
```

---

## Pipeline Flow

### Three-Stage Decision Tree

```python
def extract_symptoms_hybrid(user_input):
    # STAGE 1: Dictionary (fastest)
    dict_results = dictionary_match(user_input)
    if dict_results:
        return dict_results  # ✅ Done (1ms)
    
    # STAGE 2: ML Classifier (medium)
    _load_ml_classifier()  # Lazy load
    ml_results = ml_predict(user_input)
    if ml_results:
        return ml_results  # ✅ Done (10ms)
    
    # STAGE 3: Semantic (slowest)
    semantic_results = semantic_match(user_input)
    return semantic_results  # ✅ Fallback (50ms)
```

### Latency Budget
| Stage | Avg Latency | Success Rate | Throughput |
|-------|-------------|--------------|------------|
| Dictionary | 1ms | 40% | Fast path |
| ML | 10ms | 30% | Medium path |
| Semantic | 50ms | 20% | Slow path |
| None | 0ms | 10% | No match |
| **Total Avg** | **~15ms** | **90%** | **Acceptable** |

---

## Data Structures

### Model File Format (.joblib)

```python
{
    "vectorizer": TfidfVectorizer,
    "classifier": OneVsRestClassifier,
    "label_binarizer": MultiLabelBinarizer,
    "version": "v2",
    "train_samples": 3670,
    "threshold": 0.2  # V2-specific
}
```

### Symptom Classes (15 total)
```python
SYMPTOM_CLASSES = [
    "body_aches",
    "chills",
    "cough",
    "diarrhea",
    "dizziness",
    "fatigue",
    "fever",
    "headache",
    "nausea",
    "runny_nose",
    "shortness_of_breath",
    "sore_throat",
    "stomach_ache",
    "stuffy_nose",
    "vomiting"
]
```

### Dataset Format (.jsonl)

```python
{
    "text": "sepun ako grabe",
    "labels": ["runny_nose"]
}
```

**Validation Rules:**
- `text`: Non-empty string
- `labels`: Non-empty list of valid symptom names
- Encoding: UTF-8

---

## Performance Metrics

### Training Metrics (V2)

```
Training Samples: 3,119
Test Samples: 551
Validation Split: 15%

Micro F1: 74.8% (at threshold=0.5)
Macro F1: 67.3% (at threshold=0.5)

Real-World Typo F1: 100% (at threshold=0.2) ✅
```

### Inference Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Model load (cold) | 500ms | One-time startup |
| Model load (warm) | 1ms | Cached in memory |
| Dictionary match | 1ms | Regex search |
| ML inference | 10ms | TF-IDF + prediction |
| Semantic encode | 50ms | Neural network |
| **Total (ML path)** | **~15ms** | **Acceptable** |

### Memory Usage

| Component | RAM |
|-----------|-----|
| Flask app | 50 MB |
| ML model (V2) | 20 MB |
| Semantic model | 100 MB |
| **Total** | **~170 MB** |

---

## Dependencies

### Python Version
**Python 3.8+** (tested on 3.10)

### Core Libraries
```
flask==2.3.0
scikit-learn==1.3.0
sentence-transformers==2.2.2
joblib==1.3.0
numpy==1.24.0
```

### Optional Dependencies
```
faster-whisper==0.9.0     # Voice input (STT)
pymysql==1.1.0            # Shop database
flask-mysqldb==1.0.1      # MySQL integration
```

---

## File Structure

```
mendo-v3/thesis-mendo/
├── app.py                          # Launcher
├── requirements.txt                # Dependencies
│
├── mendo_core/                     # Core NLP logic
│   ├── __init__.py
│   ├── step3_hybrid.py             # Hybrid pipeline ⭐
│   ├── step4_recommend.py          # Recommendation engine
│   └── symptom_models.py           # Semantic templates
│
├── training/                       # ML training scripts
│   ├── symptom_classifier_v1.joblib  # V1 model (backup)
│   ├── symptom_classifier_v2.joblib  # V2 model ⭐
│   ├── train_v2_model.py           # Training script
│   ├── merge_datasets_v2.py        # Dataset merging
│   └── compare_models_cli.py       # Comparison tool
│
├── data/datasets/                  # Training data
│   ├── symptom_eval.whole.jsonl    # Original 2,170
│   ├── symptom_eval.tagalog_500.jsonl
│   ├── symptom_eval.cebuano_500.jsonl
│   ├── symptom_eval.english_500.jsonl
│   ├── symptom_eval.combined_v2.jsonl  # Merged 3,670 ⭐
│   └── Mendo-Datasets-latest.json  # Medication DB
│
├── web/                            # Flask app
│   ├── app.py                      # Main Flask app
│   ├── templates/                  # HTML templates
│   └── static/                     # CSS/JS/images
│
└── documentation/                  # This folder! ⭐
    ├── 01_PROJECT_OVERVIEW.md
    ├── 02_ITERATION_1_BASELINE.md
    ├── ... (complete journey docs)
    └── 08_TECHNICAL_SPECIFICATIONS.md
```

---

## Configuration

### Environment Variables

```bash
# ML model version
export MENDO_ML_VERSION=v2    # Options: v1, v2, none

# Whisper STT (optional)
export MENDO_WHISPER_MODEL=small
export MENDO_WHISPER_DEVICE=cpu
export MENDO_WHISPER_COMPUTE_TYPE=int8
```

### Flask Configuration

```python
# web/app.py
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = 'mendo-dev-secret-key'

# Optional MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'mendo-user'
app.config['MYSQL_PASSWORD'] = '******'
app.config['MYSQL_DB'] = 'mendo'
```

---

## API Specifications

### Internal API (step3_hybrid.py)

#### Function: `extract_symptoms_hybrid_report()`

**Signature:**
```python
def extract_symptoms_hybrid_report(
    user_input: str,
    semantic_threshold: float = 0.65,
    semantic_top_margin: float = 0.08,
    semantic_max_symptoms: int = 3,
    enable_semantic_fallback: bool = True
) -> Dict[str, Any]
```

**Input:**
- `user_input`: User's symptom description (any language)
- `semantic_threshold`: Min similarity score (0.0-1.0)
- `semantic_top_margin`: Gap between top scores
- `semantic_max_symptoms`: Max symptoms to detect
- `enable_semantic_fallback`: Enable semantic stage

**Output:**
```python
{
    "final": {
        "symptoms": ["fever", "cough"],
        "source": "ml_classifier"  # or "dictionary", "semantic"
    },
    "stages": [
        {
            "stage": "dictionary",
            "used": True,
            "result": []
        },
        {
            "stage": "ml_classifier",
            "used": True,
            "available": True,
            "result": ["fever", "cough"],
            "probabilities": {
                "fever": 0.73,
                "cough": 0.68
            }
        }
    ]
}
```

---

## Security Considerations

### Input Validation
```python
# Max input length
MAX_INPUT_LENGTH = 500  # characters

# Sanitization
user_input = user_input.strip()[:MAX_INPUT_LENGTH]

# SQL injection protection (if using MySQL)
# All queries use parameterized statements
```

### Model Security
- Models are read-only after loading
- No user input affects training
- Joblib files validated before loading

---

## Scalability

### Current Limits
- **Concurrent users:** ~100 (single Flask process)
- **Requests/second:** ~50 (with ML enabled)
- **Memory per process:** ~170 MB

### Scaling Strategies

#### Horizontal Scaling (Multiple Workers)
```bash
# Using Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 web.app:app

# Each worker loads model once
# Total memory: 4 × 170 MB = 680 MB
```

#### Caching Layer
```python
# Cache ML predictions
from functools import lru_cache

@lru_cache(maxsize=1000)
def predict_cached(text_hash):
    return _predict_ml_classifier(text)
```

---

## Testing

### Unit Tests
```python
# Test ML classifier
def test_ml_classifier():
    assert "runny_nose" in predict_ml("sepun ako")
    assert "cough" in predict_ml("ubo ko")
    assert "fever" in predict_ml("lagnat")
```

### Integration Tests
```python
# Test full pipeline
def test_pipeline():
    result = extract_symptoms_hybrid("sepun ako")
    assert result["final"]["symptoms"] == ["runny_nose"]
    assert result["final"]["source"] == "ml_classifier"
```

### Performance Tests
```python
# Benchmark latency
def test_latency():
    start = time.time()
    extract_symptoms_hybrid("test input")
    latency = time.time() - start
    assert latency < 0.1  # 100ms threshold
```

---

## Monitoring

### Logs
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('mendo')
logger.info(f"Loaded ML model: {version}")
logger.debug(f"Prediction: {result}")
```

### Metrics to Track
- Request latency (p50, p95, p99)
- ML cache hit rate
- Stage usage distribution
- Error rates per stage

---

## Known Limitations

### 1. Character Limit
- Max input: 500 characters
- Longer inputs truncated

### 2. Language Support
- Primary: Tagalog, Cebuano, English
- Limited: Other Filipino languages
- None: Non-Filipino languages

### 3. Symptoms Coverage
- Covered: 15 common symptoms
- Not covered: Rare/specialized conditions

### 4. OTC Only
- Recommends: Over-the-counter meds
- Does NOT: Prescribe prescription drugs
- Warns: Users to consult doctor for serious cases

---

**Previous:** [07_ITERATION_6_THRESHOLD_OPTIMIZATION.md](07_ITERATION_6_THRESHOLD_OPTIMIZATION.md)  
**Next:** [09_EXPERIMENTAL_RESULTS.md](09_EXPERIMENTAL_RESULTS.md)
