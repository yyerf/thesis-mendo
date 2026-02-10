# Iteration 1: Baseline System (Pre-ML)
## System State Before Machine Learning Integration

**Date:** Pre-February 10, 2025  
**Status:** Dictionary + Semantic Only  
**ML Integration:** ❌ None

---

## System Overview

### Architecture
```
User Input (Text/Voice)
        │
        ▼
┌───────────────────┐
│Step 1: Dictionary │  ← Exact keyword matching
│     Matching      │     "sipon" → runny_nose
└─────────┬─────────┘
          │ ❌ No match
          ▼
┌───────────────────┐
│Step 2: Semantic   │  ← sentence-transformers
│   Similarity     │     Cosine similarity
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│Step 3: Recommend  │  ← Rule-based engine
│   Medications     │     Based on symptoms
└───────────────────┘
```

### Key Files
- **`mendo_core/step3_hybrid.py`**: NLP pipeline (dictionary + semantic)
- **`mendo_core/step4_recommend.py`**: Recommendation engine
- **`data/datasets/Mendo-Datasets-latest.json`**: Medication database
- **`web/app.py`**: Flask web application

---

## How It Worked

### 1. Dictionary-Based Matching
**Method:** Exact keyword lookup with regex patterns

**Example:**
```python
SYMPTOM_KEYWORDS = {
    "FEVER": [
        "fever", "lagnat", "init", "hilanat",
        "high temperature", "may init"
    ],
    "COUGH": [
        "cough", "ubo", "tusok", "may ubo"
    ],
    "RUNNY_NOSE": [
        "runny nose", "sipon", "sip-on", "may sipon"
    ]
}
```

**Process:**
1. Normalize user input (lowercase, remove punctuation)
2. Check each keyword list
3. Return matching symptoms

**Strengths:**
- ✅ Fast (regex matching)
- ✅ High precision (exact matches)
- ✅ No training required

**Weaknesses:**
- ❌ No typo tolerance ("sepun" ≠ "sipon")
- ❌ Limited vocabulary (only predefined keywords)
- ❌ Can't handle paraphrasing

### 2. Semantic Fallback (sentence-transformers)
**Model:** all-MiniLM-L6-v2 (384-dim embeddings)

**Method:** Cosine similarity between user input and symptom descriptions

**Example:**
```python
# Symptom templates
templates = {
    "FEVER": "I have a fever, high temperature, feeling hot",
    "COUGH": "I am coughing, persistent cough",
    "RUNNY_NOSE": "I have runny nose, nasal discharge"
}

# Compute similarity
user_embedding = model.encode(user_input)
for symptom, template in templates.items():
    template_embedding = model.encode(template)
    similarity = cosine_similarity(user_embedding, template_embedding)
    if similarity > threshold:
        detected.append(symptom)
```

**Parameters:**
- **Threshold:** 0.65 (minimum similarity to detect)
- **Top Margin:** 0.08 (gap between top and second score)
- **Max Symptoms:** 3 (prevent over-detection)

**Strengths:**
- ✅ Handles paraphrasing ("my throat hurts when I swallow" → sore throat)
- ✅ No explicit training needed
- ✅ Generalizes to unseen phrases

**Weaknesses:**
- ❌ Poor typo handling ("sepun" → low similarity to "sipon")
- ❌ Slow (neural network inference)
- ❌ False positives (semantic drift)

---

## Performance Analysis

### Test Cases
| Input | Dictionary | Semantic | Expected | ✅/❌ |
|-------|-----------|----------|----------|-------|
| "may sipon ako" | ✅ runny_nose | - | runny_nose | ✅ |
| **"sepun ako"** | ❌ | ❌ | runny_nose | ❌ |
| "ubo ko grabe" | ✅ cough | - | cough | ✅ |
| **"ubu ako"** | ❌ | ❌ | cough | ❌ |
| "masakit ulo ko" | ✅ headache | - | headache | ✅ |
| **"masaket ulo"** | ❌ | ❌ | headache | ❌ |
| "lagnat ko" | ✅ fever | - | fever | ✅ |
| **"lagnt ko"** | ❌ | ❌ | fever | ❌ |

**Typo Accuracy: 0% (0/4)** ❌

### Why Typos Failed

1. **Dictionary:** Requires exact match
   - "sepun" not in ["sipon", "sip-on", "runny nose"]
   
2. **Semantic:** Embedding space doesn't handle character-level edits well
   - "sepun" and "sipon" have different embeddings
   - Cosine similarity < 0.65 threshold

---

## Limitations Identified

### 1. Typo Intolerance
**Problem:** Filipino users often type quickly with typos  
**Impact:** System fails on common typos like "sepun", "ubu", "lagnt"  
**Example:** "sepun ako" → ❌ No symptoms detected

### 2. Limited Vocabulary
**Problem:** Only predefined keywords work  
**Impact:** Misses valid symptom descriptions  
**Example:** "runny nose ko" (English + Tagalog mix) → might miss

### 3. No Learning Capability
**Problem:** System can't improve from data  
**Impact:** Must manually add keywords for each variation  
**Scale:** Doesn't scale to thousands of variations

### 4. Ambiguity Handling
**Problem:** No confidence scores from dictionary  
**Impact:** Can't rank multiple possible interpretations  
**Example:** "init" could be fever or hot weather

---

## Dataset Situation

### Existing Dataset
**File:** `data/datasets/testing.csv`  
**Size:** ~2,170 samples  
**Format:** CSV with columns [text, symptoms]

**Sample:**
```csv
text,symptoms
"may sipon ako",runny_nose
"ubo at lagnat",cough;fever
"masakit ang ulo ko",headache
```

### Trained Model (Discovered Later)
**File:** `training/symptom_classifier.joblib`  
**Status:** ✅ Existed but NOT integrated
**Performance:** 91.2% F1 score
**Problem:** Nobody knew it existed or how to use it!

**This became the starting point for Iteration 2.**

---

## User Experience

### Successful Cases
```
User: "may sipon at ubo ako"
System: ✅ Detected: runny_nose, cough
        ✅ Recommends: Bioflu, Neozep
```

### Failed Cases
```
User: "sepun ako" (typo for "sipon ako")
System: ❌ No symptoms detected
        ❌ No recommendations
        😢 User frustrated
```

---

## Why ML Was Needed

### Problem Statement
The baseline system failed on **real-world user input**:
- Typos ("sepun", "ubu", "lagnt")
- Slang ("init init", "labad ulo")
- Mixed languages ("runny nose ko")
- Informal speech ("grabe ang ubo")

### Proposed Solution
Train a machine learning classifier that:
1. ✅ Handles typos through character n-grams
2. ✅ Learns patterns from real user data
3. ✅ Provides confidence scores
4. ✅ Scales to thousands of variations

This led to **Iteration 2: Model Discovery**

---

## Technical Details

### Dependencies
```python
# Required packages (baseline)
flask==2.3.0
scikit-learn==1.3.0
sentence-transformers==2.2.2
torch==2.0.0
```

### Code Structure
```
mendo_core/
├── step3_hybrid.py      # Dictionary + semantic pipeline
├── step4_recommend.py   # Recommendation engine
└── symptom_models.py    # Symptom template definitions

web/
└── app.py               # Flask web interface

data/datasets/
├── Mendo-Datasets-latest.json  # Medication database
└── testing.csv                 # Symptom samples (unused!)
```

---

## Summary

### What Worked ✅
- Dictionary matching for clean input
- Semantic fallback for paraphrasing
- Fast response times
- Simple architecture

### What Failed ❌
- Typo tolerance: 0/4 (0%)
- Scalability (manual keyword addition)
- Learning from data (static rules only)
- User experience with real-world input

### Key Insight
**"A trained machine learning model existed but was never integrated into production. This became the foundation for Iteration 2."**

---

**Previous:** [01_PROJECT_OVERVIEW.md](01_PROJECT_OVERVIEW.md)  
**Next:** [03_ITERATION_2_MODEL_DISCOVERY.md](03_ITERATION_2_MODEL_DISCOVERY.md)
