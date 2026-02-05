# Mendo - Symptom to OTC Medicine Recommendation

NLP-based system for extracting symptoms from Filipino/English text and recommending OTC medications.

## Quick Start

```powershell
# Install dependencies
pip install -r requirements.txt

# Run the app
python app.py
```

Then open: **http://localhost:5000**

## What It Does

1. **Step 1**: Dictionary-based symptom extraction (Tagalog/Bisaya/English)
2. **Step 2**: AI semantic extraction using sentence transformers
3. **Step 3**: Hybrid pipeline (rules first, AI fallback)
4. **Step 4**: OTC medication recommendation

## First Run

The first time you run the app, it will download the AI model (~420MB). This takes 1-2 minutes and only happens once.

## Core Features

- ✅ **No database required** - works out of the box
- ✅ **Multilingual** - Tagalog, Bisaya, English, Taglish
- ✅ **AI-powered** - Uses transformer models for semantic understanding
- ✅ **Offline** - Everything runs locally

## Test It

Try these inputs:
- `masakit ang ulo ko at may lagnat` → Detects: HEADACHE, FEVER
- `I have cough and sipon` → Detects: COUGH, RUNNY_NOSE
- `labad ang ulo ug init ang lawas` → Detects: HEADACHE, FEVER (Bisaya)

## Technical Details

See [info.md](info.md) for detailed documentation on the models and algorithms.
