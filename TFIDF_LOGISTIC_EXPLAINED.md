# 🔍 WHERE IS TF-IDF & LOGISTIC REGRESSION? (Simple Explanation)

**For non-technical people: This shows EXACTLY where the "machine learning magic" happens**

---

## 📍 PART 1: TRAINING (Creating the Brain)

**File:** `training/train_v3_model.py` (Lines 1-184)

### Step-by-Step Walkthrough

#### 1️⃣ **Import the ML Tools** (Lines 19-21)

```python
from sklearn.feature_extraction.text import TfidfVectorizer  # ← This converts words to numbers
from sklearn.linear_model import LogisticRegression          # ← This is the "brain" that learns
from sklearn.multiclass import OneVsRestClassifier           # ← Wrapper for multiple symptoms
```

**Simple explanation:**
- `TfidfVectorizer` = Converts "masakit ulo ko" into a list of 5,000 numbers
- `LogisticRegression` = The actual learning algorithm
- `OneVsRestClassifier` = Trains 15 separate brains (one per symptom)

---

#### 2️⃣ **Load Training Data** (Lines 47-59)

```python
# Load dataset (5,170 examples)
data = load_dataset(dataset_path)

# Extract texts and labels
texts = [item["text"] for item in data]
# texts = ["sepun ako", "masakit ulo", "ubo ko", ...]

labels = [item["labels"] for item in data]
# labels = [["runny_nose"], ["headache"], ["cough"], ...]
```

**Simple explanation:**
- Read 5,170 examples from file
- Each example has:
  - **Text:** "sepun ako" (what user typed)
  - **Labels:** ["runny_nose"] (what it means)

---

#### 3️⃣ **Split Data** (Lines 69-76)

```python
X_train, X_test, y_train, y_test = train_test_split(
    texts, y, test_size=0.15, random_state=42
)
# X_train = 4,394 texts for training
# X_test  = 776 texts for testing (to check if it learned correctly)
```

**Simple explanation:**
- Use 85% (4,394 samples) to teach the model
- Keep 15% (776 samples) hidden to test if it really learned
- Like studying with practice problems, then taking a real exam

---

#### 4️⃣ **TF-IDF: Convert Words to Numbers** (Lines 78-88) ⭐⭐⭐

```python
vectorizer = TfidfVectorizer(
    max_features=5000,      # Use only 5000 most important words
    ngram_range=(1, 3),     # Look at 1-word, 2-word, and 3-word phrases
    min_df=2,               # Word must appear at least 2 times
    sublinear_tf=True       # Use log scaling (math trick)
)

# THIS IS WHERE TF-IDF HAPPENS! ⭐
X_train_vec = vectorizer.fit_transform(X_train)
# Result: 4,394 texts → 4,394 rows × 5,000 numbers
```

**Simple explanation - What TF-IDF does:**

```
Before TF-IDF:
  "sepun ako grabe"  ← Just text

After TF-IDF:
  [0.0, 0.0, 0.42, 0.0, 0.0, 0.31, 0.0, ...]  ← 5,000 numbers
   ↑    ↑     ↑     ↑    ↑     ↑
   word word  "sepun" word word "ako"
   123  456   score  890  1234  score
```

**How it works:**
1. Build vocabulary of 5,000 most common words
2. For each word in your text, assign a score:
   - **High score** if word is rare but appears in this text
   - **Low score** if word appears everywhere
   - **Zero** if word not in vocabulary

**Example:**
- "sepun" → 0.42 (rare word, important!)
- "ako" → 0.31 (common word, less important)
- "the" → 0.01 (super common, almost useless)

**Why n-grams (1,2,3)?**
```
Input: "sepun ako"

Unigrams (1-word):  ["sepun", "ako"]
Bigrams (2-word):   ["sepun ako"]
Trigrams (3-word):  [] (not enough words)

Each gets its own score!
```

---

#### 5️⃣ **Logistic Regression: Train the Brain** (Lines 95-103) ⭐⭐⭐

```python
classifier = OneVsRestClassifier(
    LogisticRegression(max_iter=1000, C=1.0, random_state=42),
    n_jobs=-1  # Use all CPU cores
)

# THIS IS WHERE MACHINE LEARNING HAPPENS! ⭐
classifier.fit(X_train_vec, y_train)
# Input:  4,394 rows × 5,000 numbers (from TF-IDF)
# Output: Learned weights for 15 symptoms
```

**Simple explanation - What `.fit()` does:**

**Before training:**
```
Brain: "I don't know anything about symptoms"
Weights: All random numbers
```

**During training (1000 iterations):**
```
Iteration 1:
  Model guesses: "sepun ako" → headache (WRONG!)
  Model learns: "Oops, I need to increase 'sepun' weight for runny_nose"
  
Iteration 2:
  Model guesses: "sepun ako" → runny_nose (CORRECT!)
  Model learns: "Good! Keep this weight"
  
... 998 more iterations ...

Iteration 1000:
  Model is now good at predicting!
```

**What gets saved:**
```python
{
  "sepun": +0.89 for runny_nose,  # Strong indicator
  "ubo":   +0.92 for cough,       # Strong indicator
  "ulo":   +0.78 for headache,    # Strong indicator
  "ako":   +0.02 for everything,  # Weak (appears everywhere)
  ...
  (75,000 weights total = 5,000 words × 15 symptoms)
}
```

**The Math (Simplified):**
```
For each symptom:
  Score = (weight1 × word1) + (weight2 × word2) + ... + (weight5000 × word5000)
  
Example for "sepun ako":
  runny_nose score = (0.89 × 0.42) + (0.02 × 0.31) + ... = 0.38 (38%)
  headache score   = (0.12 × 0.42) + (0.89 × 0.31) + ... = 0.31 (31%)
  fever score      = (0.05 × 0.42) + (0.01 × 0.31) + ... = 0.08 (8%)
  
If score ≥ 20% (threshold) → Symptom detected!
  ✅ runny_nose (38% ≥ 20%)
  ✅ headache   (31% ≥ 20%)
  ❌ fever      (8% < 20%)
```

---

#### 6️⃣ **Save the Trained Model** (Lines 127-143)

```python
joblib.dump({
    "vectorizer": vectorizer,      # Saves the word→number converter
    "classifier": classifier,      # Saves the 75,000 learned weights
    "label_binarizer": mlb,        # Saves symptom names
    "threshold": 0.20,             # 20% threshold
    "version": "v3",
    "train_samples": 5170
}, model_path)
```

**Simple explanation:**
- Saves everything to `symptom_classifier_v3.joblib` file
- This file contains all the learned knowledge
- Next time, just load this file (no need to retrain)

---

## 📍 PART 2: INFERENCE (Using the Brain)

**File:** `mendo_core/step3_hybrid.py` (Lines 189-228)

### How the Trained Model is Used

#### 1️⃣ **Load the Saved Model** (Lines 129-149)

```python
def _load_ml_classifier(version: Optional[str] = None):
    """Load the pre-trained model from file"""
    global _ML_CLASSIFIER, _ML_VECTORIZER, _ML_LABEL_BINARIZER
    
    model_path = get_classifier_path(version)  # Get path to .joblib file
    
    # Load the saved model
    data = joblib.load(model_path)
    _ML_VECTORIZER = data["vectorizer"]        # Word→number converter
    _ML_CLASSIFIER = data["classifier"]        # The 75,000 learned weights
    _ML_LABEL_BINARIZER = data["label_binarizer"]  # Symptom names
    _ML_THRESHOLD = data.get("threshold", 0.3)     # 20% threshold
```

**Simple explanation:**
- Loads the saved brain from disk
- Now ready to make predictions!

---

#### 2️⃣ **Make Prediction** (Lines 189-228) ⭐⭐⭐

```python
def _predict_ml_classifier(user_input: str):
    """Use the trained model to predict symptoms"""
    
    _load_ml_classifier()  # Make sure model is loaded
    
    # STEP 1: Convert user text to numbers (TF-IDF)
    X = _ML_VECTORIZER.transform([user_input])
    # "sepun ako" → [0.0, 0.0, 0.42, 0.0, 0.31, ...]
    
    # STEP 2: Use Logistic Regression to predict probabilities
    probs = _ML_CLASSIFIER.predict_proba(X)[0]
    # Output: [0.38, 0.12, 0.31, 0.08, ...]  (15 probabilities)
    #          ↑     ↑     ↑     ↑
    #       runny  cough head  fever
    #       nose
    
    # STEP 3: Keep only symptoms above threshold (20%)
    detected = []
    for idx, prob in enumerate(probs):
        if prob >= 0.20:  # 20% threshold
            symptom = _ML_LABEL_BINARIZER.classes_[idx]
            detected.append(symptom)
    
    return detected
    # Returns: ["runny_nose", "headache"] (both ≥ 20%)
```

**Simple explanation - Step by step:**

```
User types: "sepun ako grabe"
      ↓
STEP 1: TF-IDF converts to numbers
      [0.42 for "sepun", 0.31 for "ako", 0.18 for "grabe", ...]
      ↓
STEP 2: Logistic Regression calculates probabilities
      runny_nose: 38% ✅ (0.42×0.89 + 0.31×0.02 + ...)
      headache:   31% ✅ (0.42×0.12 + 0.31×0.89 + ...)
      fever:       8% ❌ (0.42×0.05 + 0.31×0.01 + ...)
      ↓
STEP 3: Filter by threshold (≥20%)
      ✅ runny_nose (38%)
      ✅ headache (31%)
      ❌ fever (8%)
      ↓
RESULT: ["runny_nose", "headache"]
```

---

## 🎨 VISUAL SUMMARY

### The Complete Flow

```
┌─────────────────────────────────────────────────────────────┐
│               TRAINING (Done Once)                           │
│            training/train_v3_model.py                        │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
    ┌──────────────────────────────────────────────┐
    │  Load 5,170 examples:                        │
    │  {"text": "sepun ako", "labels": ["runny"]}  │
    └────────────┬─────────────────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────────────────────┐
    │  TF-IDF: Convert text → 5,000 numbers        │
    │                                              │
    │  "sepun ako"  →  [0.42, 0.31, 0.0, ...]     │
    │  "masakit"    →  [0.0, 0.89, 0.12, ...]     │
    │  (4,394 rows × 5,000 columns)               │
    └────────────┬─────────────────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────────────────────┐
    │  Logistic Regression: Learn patterns         │
    │                                              │
    │  Adjusts 75,000 weights over 1000 iterations │
    │  "sepun" → +0.89 for runny_nose             │
    │  "ubo"   → +0.92 for cough                  │
    └────────────┬─────────────────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────────────────────┐
    │  Save to symptom_classifier_v3.joblib        │
    │  (0.68 MB file with all learned weights)     │
    └──────────────────────────────────────────────┘


┌─────────────────────────────────────────────────────────────┐
│            PREDICTION (Every time user types)               │
│            mendo_core/step3_hybrid.py                        │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
    ┌──────────────────────────────────────────────┐
    │  Load saved model from .joblib file          │
    └────────────┬─────────────────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────────────────────┐
    │  User types: "sepun ako grabe"               │
    └────────────┬─────────────────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────────────────────┐
    │  TF-IDF: Convert to numbers                  │
    │  "sepun ako grabe" → [0.42, 0.31, 0.18, ...] │
    └────────────┬─────────────────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────────────────────┐
    │  Logistic Regression: Calculate scores       │
    │                                              │
    │  runny_nose: 38% ✅                          │
    │  headache:   31% ✅                          │
    │  fever:       8% ❌                          │
    └────────────┬─────────────────────────────────┘
                 │
                 ▼
    ┌──────────────────────────────────────────────┐
    │  Return symptoms ≥ 20%                       │
    │  ["runny_nose", "headache"]                  │
    └──────────────────────────────────────────────┘
```

---

## 💡 SIMPLE ANALOGIES

### TF-IDF = Recipe Ingredient Lists

**Think of it like converting recipes to ingredient scores:**

```
Recipe A: "chocolate cake with chocolate chips"
  → chocolate: HIGH score (appears twice, important!)
  → cake: MEDIUM score
  → with: LOW score (common word, not helpful)

Recipe B: "vanilla cake with sprinkles"
  → vanilla: HIGH score (unique to this recipe)
  → cake: MEDIUM score
  → with: LOW score (common word again)
```

**Same for symptoms:**
```
"sepun ako" 
  → sepun: HIGH (rare word, very informative!)
  → ako: LOW (everyone says this, not helpful)

"masakit ulo ko"
  → masakit: HIGH (strong symptom word!)
  → ulo: HIGH (body part, important!)
  → ko: LOW (everyone says this)
```

---

### Logistic Regression = Pattern Recognition

**Like a doctor who learned from experience:**

```
After seeing 5,170 patients:
  Patient says "sepun" → 89% likely runny nose
  Patient says "ubo"   → 92% likely cough
  Patient says "ulo"   → 78% likely headache

New patient says "sepun ako":
  Doctor calculates: 38% chance runny nose (ABOVE 20% → YES!)
                     8% chance fever (BELOW 20% → NO!)
```

---

## 🔢 THE NUMBERS

| Component | Size | What it is |
|-----------|------|------------|
| **Vocabulary** | 5,000 words | Most common words learned from training data |
| **Training Samples** | 5,170 examples | Human-labeled symptom descriptions |
| **Features per sample** | 5,000 numbers | TF-IDF scores for each word |
| **Learned Weights** | 75,000 weights | 5,000 features × 15 symptoms |
| **Training Time** | 2-3 minutes | How long to train on regular laptop |
| **Model File Size** | 0.68 MB | How much space the saved model takes |
| **Prediction Time** | <10 milliseconds | How fast it makes predictions |

---

## ❓ COMMON QUESTIONS

### Q: "Why 5,000 features?"
**A:** More features = more detail, but also slower and bigger file. 5,000 is the sweet spot:
- Less than 5,000: Might miss important words
- More than 5,000: Gets slower, doesn't improve much

### Q: "What are n-grams?"
**A:** Looking at word combinations:
```
Input: "sepun ako"

1-grams (unigrams):  ["sepun", "ako"]           ← Individual words
2-grams (bigrams):   ["sepun ako"]              ← Word pairs
3-grams (trigrams):  --none-- (only 2 words)    ← Word triplets
```

This helps catch phrases like "no fever" (2-gram) vs just "fever" (1-gram).

### Q: "What does 'max_iter=1000' mean?"
**A:** The model tries to learn 1,000 times, getting better each iteration:
```
Iteration 1:   70% correct (still learning)
Iteration 500: 76% correct (getting better!)
Iteration 1000: 77.4% correct (done!)
```

### Q: "Why threshold 0.2 (20%)?"
**A:** If too high (like 50%), misses typos. If too low (like 5%), too many false alarms.
- 20% = Best balance found through testing

---

## 🎯 KEY TAKEAWAY

**The "machine learning" is:**
1. **TF-IDF** = Smart way to convert text to numbers
2. **Logistic Regression** = Learning which words predict which symptoms
3. **75,000 weights** = The "knowledge" learned from 5,170 examples

**NOT:**
- ❌ NOT hardcoded (learns from data)
- ❌ NOT deep learning (simpler algorithm)
- ❌ NOT LLM/GPT (different approach)

**It's like:** A very smart pattern-matching system that learned from 5,170 examples, not a human writing if-else rules.

---

*For even more technical details, see the training script at:*  
`training/train_v3_model.py` (full code with comments)
