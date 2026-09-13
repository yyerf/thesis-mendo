# Negation and Spelling Correction Fixes - August 15, 2026

## Summary

Fixed critical issues with **comma-separated negation lists**, **overly aggressive spell correction**, and **missing symptom detection**.

---

## Issue 1: VOMITING Symptom Removal ✅

**Problem:** VOMITING symptom had remnants in the codebase causing confusion, even though it was never fully implemented.

**Fix:**
- Removed VOMITING from all modules: `step1.py`, `step2.py`, `step3_hybrid.py`, `advanced_fuzzy.py`, `symptom_models.py`
- Removed nausea/vomiting phrases from STOMACH_ACHE dictionaries and keywords
- STOMACH_ACHE now focuses on stomach pain, heartburn, and cramping only

---

## Issue 2: Overly Aggressive Spell Correction ❌→✅

### Problem 1: "ulo" (head) incorrectly matched to "ubo" (cough)

**Example:** "Nagtulo akong ilong, pero dili sakit akong ulo" → detected COUGH + RUNNY_NOSE
- **Root cause:** Fuzzy matcher had "ubu" as variant of "ubo", which matched "ulo" after phonetic normalization

**Fix:**
- Removed "ubu" from "ubo" variants in `advanced_fuzzy.py`
- Added "ulo" to `_KNOWN_LOCAL_TOKENS` to prevent spell correction

### Problem 2: "kalit" (suddenly) incorrectly changed to "sakit" (pain)

**Example:** "Kalit lang ko nagkalibang" → detected DIARRHEA + BODY_ACHES
- **Root cause:** Fuzzy matcher changed "kalit" to "sakit", then generic "sakit" mapped to BODY_ACHES

**Fix:**
- Added "kalit", "bigla", "sukad", "ganiha" to `_KNOWN_LOCAL_TOKENS` (time/manner words)
- **Removed the entire `("sakit", "BODY_ACHES")` mapping** - "sakit" is a generic pain word that requires body-part context (katawan/lawas)
- Kept "masakit" and "labad" which are more specific to body aches

**Impact:** Spell correction is now much more conservative and respects legitimate local words.

---

## Issue 3: Comma-Separated Negation Lists ❌→✅

### Problem: Commas break negation scope

**Example:** "wala koy sakit sa tiyan, sakit sa ulo, sakit sa ngipon, pero naa koy sipon"
- **Expected:** Only RUNNY_NOSE (all three pains negated)
- **Got:** HEADACHE + TOOTHACHE + RUNNY_NOSE (only tiyan negated)

### Root Cause Analysis

1. **Normalization strips commas:** `_normalize()` converts "tiyan, ulo" → "tiyan ulo" (commas become spaces)
2. **Intervening symptom logic fails:** When checking if "wala" negates "ulo", the function sees "tiyan" as an intervening symptom
3. **No list continuation detected:** After normalization, there's no comma or connector between "tiyan" and "ulo"

### Solution: Parallel Structure Detection

**Key insight:** Even after commas are removed, **parallel phrasing patterns** indicate list continuation:
- "sakit sa tiyan sakit sa ulo" → "sakit" repeats (parallel structure)
- "sakit akong tiyan akong ulo" → "akong" repeats (abbreviated list with ellipsis)

**Implementation in `_negation_reaches()` (step1.py lines 1001-1034):**

```python
# When an intervening symptom is found, check if negation continues via:
# 1. Explicit connectors: "ug", "and", "or"
# 2. Parallel structure: phrase_first repeats before target
# 3. Abbreviated lists: possessive markers (akong/ang/sa) signal continuation
```

**Specific fixes:**

1. **Skip empty tokens (punctuation remnants):**
   - Changed `if not bare: return False` → `if not bare: continue`
   - Allows negation to continue past normalized punctuation

2. **Detect phrase_first repetition:**
   - "sakit sa tiyan sakit sa ulo" → "sakit" appears again → list detected
   - Guard: for single-word phrases, don't match the target itself

3. **Detect abbreviated lists:**
   - "sakit akong tiyan akong ulo" → "akong" signals continuation
   - Check if possessive marker is followed by body part word

---

## Issue 4: Missing COUGH Detection ❌→✅

**Problem:** "giubo ko" not detected as cough

**Example:** "dili sakit akong tiyan, akong ulo, akong ngipon pero giubo ko"
- **Expected:** COUGH_GENERAL
- **Got:** Nothing (negated symptoms correctly removed, but cough missed)

**Root cause:** "giubo" was in the SYMPTOM_DICTIONARY but NOT in the `_extract_cough_type()` function's cough detection list.

**Fix:** Added "giubo" to the cough verb list in `_extract_cough_type()` (line 1210)

---

## Issue 5: Trace UI Clarity ✅

**Problem:** Dictionary proximity rescues didn't show in trace "Dictionary evidence" section, making it look like semantic model made decisions.

**Example:** "Barado akong ilong" matched via proximity pattern but showed empty dictionary evidence.

**Fix:** Added explicit dictionary entries for common patterns:
- "barado akong ilong"
- "bara akong ilong"

Now these show up properly in the trace UI, making decision attribution clear.

---

## Test Results

All test cases now pass:

| Test Case | Input | Expected | Result |
|-----------|-------|----------|--------|
| Comma list | `wala koy sakit sa tiyan, sakit sa ulo, sakit sa ngipon, pero naa koy sipon` | `[RUNNY_NOSE]` | ✅ |
| Abbreviated list | `dili sakit akong tiyan, akong ulo, akong ngipon pero giubo ko` | `[COUGH_GENERAL]` | ✅ |
| Simple list | `wala koy ulo, tiyan` | `[]` | ✅ |
| Diarrhea only | `Kalit lang ko nagkalibang sukad ganiha buntag` | `[DIARRHEA]` | ✅ |
| Runny nose only | `Nagtulo akong ilong, pero dili sakit akong ulo` | `[RUNNY_NOSE]` | ✅ |

---

## Files Modified

1. `mendo_core/step1.py` - Main negation and cough detection fixes
2. `mendo_core/step2.py` - Removed VOMITING, updated STOMACH_ACHE and DIARRHEA anchors
3. `mendo_core/step3_hybrid.py` - Removed VOMITING from lexical guard
4. `mendo_core/advanced_fuzzy.py` - Removed problematic fuzzy mappings
5. `mendo_core/symptom_models.py` - Removed VOMITING patterns

---

## Key Learnings

1. **Normalization has side effects:** Commas are stripped early, so comma-based logic must adapt to parallel structure patterns
2. **Generic words need context:** "sakit" alone can mean any pain - needs body part context to indicate body aches
3. **Consistency matters:** If "giubo" is in the dictionary, it must also be in the cough type detection function
4. **Proximity rescues need comprehensive negation:** Simple regex patterns with fixed windows don't handle comma lists
5. **Trace UI transparency:** Users need to see ALL dictionary matches (including proximity rescues) for trust


---

## Issue 4: Headache Intake Adding HEADACHE Incorrectly ❌→✅

### Problem: HEADACHE added when not detected by symptom pipeline

**Example:** "dili sakit akong tiyan, akong ulo, akong ngipon pero giubo ko"
- **Expected:** Only COUGH_GENERAL (headache correctly negated)
- **Actual (before fix):** System showed headache selection interface, user forced to select type, then HEADACHE added to symptoms
- **Result:** System recommended headache medicine instead of cough medicine

### Root Cause

In `pos/routes_consultation.py` at lines 515-523, the code would add HEADACHE whenever `headache_location` was set:

```python
if headache_location and "HEADACHE" not in report["final"]["symptoms"]:
    report["final"]["symptoms"].append("HEADACHE")
```

This didn't validate:
1. Whether HEADACHE was actually detected by the symptom pipeline
2. Whether other symptoms were detected (negating the need for headache intake)
3. Whether the user explicitly clicked on the headache diagram vs frontend sending a stale value

### Fix

Modified logic to only add HEADACHE when there's clear evidence the user intended a headache consult:

```python
# Track whether headache_location came from intake vs user click
headache_from_intake = False
if not headache_location:
    headache_intake = _apply_text_headache_intake(report, user_text, user_age)
    if headache_intake:
        headache_location = headache_intake["key"]
        headache_from_intake = True

# Only add HEADACHE for explicit user clicks
# (intake already adds HEADACHE when appropriate)
user_clicked_illustration = (
    headache_location and 
    headache_location == data.get("headache_location")
)
if headache_location and "HEADACHE" not in report["final"]["symptoms"]:
    if user_clicked_illustration:
        report["final"]["symptoms"].append("HEADACHE")
```

### Key Changes

1. **Track source**: New variable `headache_from_intake` indicates whether `headache_location` came from text intake vs user input
2. **Validate clicks**: Only add HEADACHE if `headache_location` matches user's request
3. **Trust intake logic**: `_apply_text_headache_intake` already adds HEADACHE for bare cues, no need to add again
4. **Prevent stale values**: Ignore `headache_location` if it doesn't match user input and didn't come from intake

### Test Results

| Test Case | Input | User Click | Expected | Result |
|-----------|-------|------------|----------|--------|
| Negated with cough | "dili sakit akong tiyan, akong ulo, akong ngipon pero giubo ko" | None | `["COUGH_GENERAL"]` | ✅ Pass |
| User clicked diagram | Same text | "tension" | `["COUGH_GENERAL", "HEADACHE"]` | ✅ Pass |
| Bare cue promotion | "tension" | None | `["HEADACHE"]` | ✅ Pass |
| Bare cue with symptoms | "giubo ko ug tension" | None | `["COUGH_GENERAL"]` | ✅ Pass |
| Negated sinus | "wala koy sinus" | None | `[]` | ✅ Pass |

### Files Modified

- `pos/routes_consultation.py`: Lines 507-530 (api_analyze endpoint)
- New test file: `testing/test_headache_intake_bug_fix.py`

### Impact

- **Precision preserved**: Symptom pipeline negation logic is now fully respected
- **User intent honored**: Explicit diagram clicks still work as intended  
- **Bare cue promotion intact**: "sinus", "tension", etc. still route to headache consults when no other symptoms present
- **Bug fixed**: No more incorrect HEADACHE additions when other symptoms detected

---

## Summary of All Fixes

| Issue | Status | Files Modified | Impact |
|-------|--------|----------------|--------|
| 1. VOMITING removal | ✅ Fixed | 5 core modules | Cleaner codebase, no confusion |
| 2. Spell correction | ✅ Fixed | `advanced_fuzzy.py`, `step1.py` | More conservative, respects local words |
| 3. Comma negation | ✅ Fixed | `step1.py` | Handles parallel structure in negation |
| 4. Headache intake | ✅ Fixed | `pos/routes_consultation.py` | Respects symptom pipeline results |

All fixes maintain backward compatibility and pass existing regression tests.
