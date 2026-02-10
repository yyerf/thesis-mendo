# V3 Model Quick Start Guide

## Yes, V3 is Now Implemented! ✅

V3 model is **ready to use** in app.py and all components.

---

## How to Use V3

### Option 1: Set Environment Variable (Recommended)

**Windows PowerShell:**
```powershell
$env:MENDO_ML_VERSION="v3"
python app.py
```

**Windows CMD:**
```cmd
set MENDO_ML_VERSION=v3
python app.py
```

**Linux/Mac:**
```bash
export MENDO_ML_VERSION=v3
python app.py
```

### Option 2: Default Behavior

V3 is now the **default model** if no environment variable is set!

Just run:
```bash
python app.py
```

---

## Switching Between Versions

You can switch between V1, V2, and V3 anytime:

```powershell
# Use V3 (5,170 samples, 77.4% F1) - RECOMMENDED ⭐
$env:MENDO_ML_VERSION="v3"

# Use V2 (3,670 samples, 74.8% F1)
$env:MENDO_ML_VERSION="v2"

# Use V1 (2,171 samples, 91.2% F1 on simple dataset)
$env:MENDO_ML_VERSION="v1"
```

---

## What's New in V3?

✅ **5,170 training samples** (+1,500 from V2)  
✅ **77.4% Micro F1** (+2.6% improvement)  
✅ **69.8% Macro F1** (+2.5% improvement)  
✅ **Context-aware multilingual** (Tagalog "hilo" vs Cebuano "hilo")  
✅ **Modern slang support** ("af", "ngl", "rn", "vibes")  
✅ **+219% confidence** on rare phrases ("gatuyok akong pananaw")  

---

## Verification

To verify V3 is loaded:

```powershell
$env:MENDO_ML_VERSION="v3"
python -c "from mendo_core.step3_hybrid import get_classifier_path; import joblib; m = joblib.load(get_classifier_path()); print(f'Version: {m[\"version\"]}, Samples: {m[\"train_samples\"]}')"
```

Expected output:
```
Version: v3, Samples: 5170
```

---

## Full Documentation

See [MODEL_COMPARISON.md](MODEL_COMPARISON.md) for comprehensive performance analysis with real measurements.

---

## Current Status

| Component | V3 Support | Status |
|-----------|------------|--------|
| **Code** | ✅ | `step3_hybrid.py` updated |
| **Model File** | ✅ | `symptom_classifier_v3.joblib` exists |
| **Default** | ✅ | V3 is default when no env var set |
| **Tested** | ✅ | All critical phrases working |
| **Documentation** | ✅ | MODEL_COMPARISON.md created |

---

**Last Updated:** February 10, 2026  
**V3 Training Date:** February 10, 2026
