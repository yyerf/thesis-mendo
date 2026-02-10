# Deployment Guide & Usage Instructions
## How to Run the MENDO System

**Version:** 2.0 with ML Classifier V2  
**Target Users:** Developers, Researchers, Deployers

---

## Quick Start (5 Minutes)

### Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Windows/Linux/Mac OS

### Installation

```bash
# 1. Clone/navigate to project
cd thesis-mendo/

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set ML version (use V2)
set MENDO_ML_VERSION=v2    # Windows
export MENDO_ML_VERSION=v2 # Linux/Mac

# 4. Run the app
python app.py
```

### Access
Open browser: `http://localhost:5000`

---

## Detailed Setup

### Step 1: Environment Setup

#### Option A: Virtual Environment (Recommended)
```bash
# Create venv
python -m venv venv

# Activate
venv\Scripts\activate      # Windows
source venv/bin/activate   # Linux/Mac

# Install packages
pip install -r requirements.txt
```

#### Option B: System-Wide
```bash
# Install directly
pip install -r requirements.txt
```

### Step 2: Verify Installation

```bash
# Check Python version
python --version
# Output: Python 3.10.x (or higher)

# Check scikit-learn
python -c "import sklearn; print(sklearn.__version__)"
# Output: 1.3.0

# Check Flask
python -c "import flask; print(flask.__version__)"
# Output: 2.3.0
```

### Step 3: Verify ML Model

```bash
# Check if V2 model exists
python -c "from pathlib import Path; print('✓ V2 exists' if Path('training/symptom_classifier_v2.joblib').exists() else '✗ Missing')"
# Output: ✓ V2 exists

# Load and inspect
python -c "
import joblib
v2 = joblib.load('training/symptom_classifier_v2.joblib')
print(f'Version: {v2.get(\"version\")}')
print(f'Samples: {v2.get(\"train_samples\")}')
print(f'Threshold: {v2.get(\"threshold\")}')"
# Output:
# Version: v2
# Samples: 3670
# Threshold: 0.2
```

---

## Configuration

### ML Model Version

**Environment Variable:** `MENDO_ML_VERSION`

```bash
# Use V2 (RECOMMENDED - 100% typo accuracy)
set MENDO_ML_VERSION=v2

# Use V1 (Legacy - 66.7% typo accuracy)
set MENDO_ML_VERSION=v1

# Disable ML (dictionary + semantic only)
set MENDO_ML_VERSION=none
```

**In Python:**
```python
import os
os.environ["MENDO_ML_VERSION"] = "v2"
```

### Flask Configuration

**File:** `web/app.py`

```python
# Debug mode (development)
app.run(debug=True)

# Production mode
app.run(debug=False, host='0.0.0.0', port=5000)
```

### Optional: MySQL (Shop Features)

```python
# web/app.py
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'your_user'
app.config['MYSQL_PASSWORD'] = 'your_password'
app.config['MYSQL_DB'] = 'mendo'
```

**Note:** MySQL only needed for shop/POS features, NOT for core NLP.

---

## Running the Application

### Development Mode

```bash
# Basic run
python app.py

# Output:
#  * Running on http://127.0.0.1:5000
#  * Debug mode: on
```

**Features:**
- Auto-reload on code changes
- Detailed error messages
- Single-threaded

### Production Mode

#### Option 1: Gunicorn (Linux/Mac)
```bash
pip install gunicorn

gunicorn -w 4 -b 0.0.0.0:5000 web.app:app
```

**Configuration:**
- `-w 4`: 4 worker processes
- `-b 0.0.0.0:5000`: Bind to all interfaces
- `web.app:app`: Module path to Flask app

#### Option 2: Waitress (Windows)
```bash
pip install waitress

waitress-serve --port=5000 web.app:app
```

---

## Testing the System

### Test 1: Web Interface

1. Open `http://localhost:5000`
2. Enter symptom: `"sepun ako"`
3. Expected: Detects "Runny Nose" ✅
4. Should recommend: Neozep, Bioflu, etc.

### Test 2: ML Classifier Directly

```bash
# Run comparison tool
python training/compare_models_cli.py --quick-test

# Expected output:
# V1: 4/6 correct (66.7%)
# V2: 6/6 correct (100.0%)
# 🎉 V2 IS BETTER on typos/edge cases!
```

### Test 3: Interactive Mode

```bash
python training/compare_models_cli.py

# Prompts:
Enter symptoms: sepun ako
V1: ['runny_nose']
V2: ['runny_nose']

Enter symptoms: ubu ako grabe
V1: []
V2: ['cough']  ← V2 detects, V1 doesn't!
```

### Test 4: Python API

```python
from mendo_core.step3_hybrid import extract_symptoms_hybrid_report

# Test typo handling
result = extract_symptoms_hybrid_report("sepun ako")
print(result["final"]["symptoms"])
# Output: ['runny_nose'] ✅

# Check which stage caught it
print(result["final"]["source"])
# Output: 'ml_classifier' ✅
```

---

## Common Issues & Solutions

### Issue 1: Model Not Found

**Error:**
```
FileNotFoundError: [Errno 2] No such file or directory: 'training/symptom_classifier_v2.joblib'
```

**Solution:**
```bash
# Check if file exists
ls training/symptom_classifier_v2.joblib

# If missing, check V1
ls training/symptom_classifier_v1.joblib

# Use V1 if V2 missing
set MENDO_ML_VERSION=v1
```

### Issue 2: Import Errors

**Error:**
```
ModuleNotFoundError: No module named 'sklearn'
```

**Solution:**
```bash
# Install dependencies
pip install -r requirements.txt

# Or install individually
pip install scikit-learn==1.3.0
```

### Issue 3: Version Mismatch

**Error:**
```
UserWarning: Trying to unpickle estimator trained with scikit-learn 1.3.0 using 1.2.0
```

**Solution:**
```bash
# Upgrade scikit-learn
pip install --upgrade scikit-learn==1.3.0
```

### Issue 4: Port Already in Use

**Error:**
```
OSError: [Errno 98] Address already in use
```

**Solution:**
```bash
# Find process using port 5000
netstat -ano | findstr :5000    # Windows
lsof -i :5000                   # Linux/Mac

# Kill process (Windows)
taskkill /PID <process_id> /F

# Kill process (Linux/Mac)
kill -9 <process_id>

# Or use different port
python app.py --port 5001
```

### Issue 5: Slow Response

**Symptoms:**
- First request takes 2-3 seconds
- Subsequent requests faster

**Explanation:**
- First request loads ML model (cold start)
- Model cached in memory afterward
- Expected behavior!

**Solution (if problematic):**
```python
# Pre-load model at startup
# Add to web/app.py
from mendo_core.step3_hybrid import _load_ml_classifier
_load_ml_classifier()  # Load during app init
```

---

## Verification Checklist

### ✅ Installation Verified
- [ ] Python 3.8+ installed
- [ ] Dependencies installed (`pip list`)
- [ ] V2 model file exists (0.57 MB)
- [ ] V2 threshold = 0.2

### ✅ Configuration Verified
- [ ] `MENDO_ML_VERSION=v2` set
- [ ] Flask runs without errors
- [ ] Web interface loads at `http://localhost:5000`

### ✅ Functionality Verified
- [ ] "sepun ako" → Detects runny_nose ✅
- [ ] "ubu ako grabe" → Detects cough ✅
- [ ] "may sipon" → Detects runny_nose ✅
- [ ] Recommendations displayed

### ✅ Performance Verified
- [ ] First request < 5 seconds (model loading)
- [ ] Subsequent requests < 100ms
- [ ] No errors in console

---

## API Usage Examples

### Example 1: Simple Symptom Check

```python
from mendo_core.step3_hybrid import extract_symptoms_hybrid

# English
symptoms = extract_symptoms_hybrid("I have a runny nose")
print(symptoms)  # ['runny_nose']

# Tagalog
symptoms = extract_symptoms_hybrid("may sipon ako")
print(symptoms)  # ['runny_nose']

# Typo (V2 handles!)
symptoms = extract_symptoms_hybrid("sepun ako")
print(symptoms)  # ['runny_nose'] ✅
```

### Example 2: Detailed Report

```python
from mendo_core.step3_hybrid import extract_symptoms_hybrid_report

report = extract_symptoms_hybrid_report("sepun at lagnt ko")

# Results
print(report["final"]["symptoms"])
# Output: ['runny_nose', 'fever']

print(report["final"]["source"])
# Output: 'ml_classifier'

# Probabilities (if ML was used)
for stage in report["stages"]:
    if stage["stage"] == "ml_classifier":
        print(stage["probabilities"])
        # Output: {'runny_nose': 0.68, 'fever': 0.73}
```

### Example 3: Get Recommendations

```python
from mendo_core.step3_hybrid import extract_symptoms_hybrid_report
from mendo_core.step4_recommend import recommend_from_dataset
from data.datasets import load_medication_database

# Step 1: Detect symptoms
report = extract_symptoms_hybrid_report("sepun at ubu")
symptoms = report["final"]["symptoms"]
# ['runny_nose', 'cough']

# Step 2: Load medication database
medications = load_medication_database()

# Step 3: Get recommendations
recommendations = recommend_from_dataset(
    detected_symptoms=symptoms,
    medication_database=medications,
    user_age=25,
    user_input="sepun at ubu"
)

# Step 4: Display
for med in recommendations["recommendations"]:
    print(f"{med['name']}: {med['reasons']}")
# Output:
# Bioflu: ['Addresses: cough', 'Addresses: runny_nose']
# Neozep: ['Addresses: runny_nose']
```

---

## Production Deployment

### Recommended Stack

```
┌─────────────────────────┐
│   Nginx (Reverse Proxy) │
│   Port 80/443 (HTTPS)   │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   Gunicorn (WSGI)       │
│   4 workers × 170 MB    │
│   127.0.0.1:5000        │
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   Flask App + ML Model  │
│   MENDO V2              │
└─────────────────────────┘
```

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Systemd Service (Auto-restart)

```ini
# /etc/systemd/system/mendo.service
[Unit]
Description=MENDO Medical Recommendation System
After=network.target

[Service]
Type=simple
User=mendo
WorkingDirectory=/path/to/thesis-mendo
Environment="MENDO_ML_VERSION=v2"
ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 web.app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

**Enable and start:**
```bash
sudo systemctl enable mendo
sudo systemctl start mendo
sudo systemctl status mendo
```

---

## Monitoring

### Log Files

```bash
# Application logs
tail -f logs/mendo.log

# Gunicorn access logs
tail -f logs/gunicorn_access.log

# Gunicorn error logs
tail -f logs/gunicorn_error.log
```

### Health Check Endpoint

```python
# Add to web/app.py
@app.route('/health')
def health_check():
    return {
        "status": "healthy",
        "ml_version": os.environ.get("MENDO_ML_VERSION"),
        "ml_loaded": _ML_CLASSIFIER is not None
    }
```

**Test:**
```bash
curl http://localhost:5000/health
# Output: {"status": "healthy", "ml_version": "v2", "ml_loaded": true}
```

---

## Backup & Recovery

### Backup Model Files

```bash
# Create backup directory
mkdir -p backups/$(date +%Y%m%d)

# Backup models
cp training/symptom_classifier_v2.joblib backups/$(date +%Y%m%d)/
cp training/symptom_classifier_v1.joblib backups/$(date +%Y%m%d)/

# Backup datasets
cp data/datasets/symptom_eval.combined_v2.jsonl backups/$(date +%Y%m%d)/
```

### Restore from Backup

```bash
# List backups
ls -la backups/

# Restore V2 model
cp backups/20260210/symptom_classifier_v2.joblib training/
```

---

## Performance Tuning

### 1. Model Caching (Already Implemented)

```python
# Global model cache in step3_hybrid.py
_ML_CLASSIFIER = None  # Loaded once, reused
```

### 2. Response Caching

```python
# Add to app (for repeated queries)
from functools import lru_cache

@lru_cache(maxsize=1000)
def cached_symptom_detection(text_hash):
    return extract_symptoms_hybrid(text)
```

### 3. Gunicorn Workers

```bash
# Rule of thumb: (2 × CPU cores) + 1
# 4-core machine: (2 × 4) + 1 = 9 workers
gunicorn -w 9 -b 0.0.0.0:5000 web.app:app
```

### 4. Preload Model

```python
# web/app.py - load model at startup
from mendo_core.step3_hybrid import _load_ml_classifier

# Before app.run()
_load_ml_classifier()  # Warm up cache
```

---

## Troubleshooting Guide

| Symptom | Diagnosis | Solution |
|---------|-----------|----------|
| No symptoms detected | ML not loaded | Check MENDO_ML_VERSION |
| Wrong symptoms | Wrong model version | Use V2, not V1 |
| Slow first request | Cold start (normal) | Pre-load model |
| Memory issues | Too many workers | Reduce Gunicorn workers |
| Import errors | Missing deps | pip install -r requirements.txt |
| Typos not detected | Using V1 or threshold wrong | Use V2 with threshold=0.2 |

---

## FAQ

**Q: Which version should I use, V1 or V2?**  
A: **V2**. It handles typos 100% vs V1's 66.7%.

**Q: Can I use CPU instead of GPU?**  
A: Yes! LogisticRegression is CPU-only, no GPU needed.

**Q: How much RAM do I need?**  
A: Minimum 512 MB, recommended 1 GB+.

**Q: Can I retrain the model?**  
A: Yes! Use `training/train_v2_model.py` with your own dataset.

**Q: How do I add more symptoms?**  
A: Add to training dataset, retrain model, update SYMPTOM_CLASSES.

**Q: Is MySQL required?**  
A: No, only for shop/POS features. Core NLP works without it.

**Q: Can I deploy on Heroku/AWS/GCP?**  
A: Yes! Works on any platform supporting Python 3.8+.

---

## Summary

### Minimal Setup
```bash
cd thesis-mendo/
set MENDO_ML_VERSION=v2
pip install -r requirements.txt
python app.py
```

### ✅ Ready When You See
```
 * Running on http://127.0.0.1:5000
 * Debug mode: on
✓ V2 model loaded successfully
```

### 🎯 Success Test
```
Input: "sepun ako"
Output: Runny Nose detected → Recommends Neozep ✅
```

---

**Previous:** [08_TECHNICAL_SPECIFICATIONS.md](08_TECHNICAL_SPECIFICATIONS.md)  
**Next:** [README.md](README.md) (Quick reference)
