# Headache Intake Fix - August 15, 2026

## Problem

User reported that the headache selection interface was appearing and forcing users to select a headache type even when HEADACHE was not detected by the symptom pipeline.

### Test Case
Input: `"dili sakit akong tiyan, akong ulo, akong ngipon pero giubo ko"`
- Translation: "my stomach doesn't hurt, my head, my teeth but I'm coughing"
- Expected: `["COUGH_GENERAL"]` only
- Actual (before fix): User forced to select headache type, then HEADACHE added to symptoms
- Result: System recommended headache medicine instead of cough medicine

## Root Cause Analysis

The issue was in `pos/routes_consultation.py` at lines 515-523 in the `api_analyze` endpoint:

```python
if headache_location and "HEADACHE" not in report["final"]["symptoms"]:
    report["final"]["symptoms"].append("HEADACHE")
```

This code would add HEADACHE whenever `headache_location` was set, regardless of:
1. Whether HEADACHE was actually detected by the symptom pipeline
2. Whether other symptoms were detected
3. Whether the user explicitly clicked on the headache diagram vs the frontend sending a stale value

### Why This Was Dangerous

The original logic assumed that if `headache_location` was set, it must be because either:
1. User clicked on the headache diagram, OR
2. Free-text intake promoted a bare headache cue

But it didn't validate this assumption. This could lead to:
- Frontend bugs causing stale `headache_location` values
- Users accidentally clicking on diagrams
- Session state pollution
- HEADACHE being added when other symptoms (like COUGH) were correctly detected

## Solution

Modified the logic to only add HEADACHE when there's clear evidence the user intended a headache consult:

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

1. **Track source of headache_location**: New variable `headache_from_intake` indicates whether `headache_location` came from free-text intake logic vs user input
2. **Validate user clicks**: Only add HEADACHE if `headache_location` matches the user's request (`data.get("headache_location")`)
3. **Trust intake logic**: `_apply_text_headache_intake` already adds HEADACHE when promoting bare cues, so we don't need to add it again
4. **Prevent stale values**: If `headache_location` is set but doesn't match user input and didn't come from intake, it's ignored

## Test Results

### Test Case 1: Negated symptoms with cough (no user click)
- Input: `"dili sakit akong tiyan, akong ulo, akong ngipon pero giubo ko"`
- User clicked: None
- Result: `["COUGH_GENERAL"]` ✅
- HEADACHE correctly NOT added

### Test Case 2: User explicitly clicks headache diagram
- Input: `"dili sakit akong tiyan, akong ulo, akong ngipon pero giubo ko"`
- User clicked: `"tension"`
- Result: `["COUGH_GENERAL", "HEADACHE"]` ✅
- Both symptoms detected (user click honored)

### Test Case 3: Bare headache cue with no other symptoms
- Input: `"tension"`
- User clicked: None
- Result: `["HEADACHE"]` ✅
- HEADACHE promoted from bare cue (added exactly once by intake)

## Impact

- **Precision preserved**: Symptom pipeline negation logic is now respected
- **User intent honored**: Explicit diagram clicks still work as intended
- **Bare cue promotion intact**: "sinus", "tension", etc. still route to headache consults when no other symptoms present
- **Bug fixed**: No more incorrect HEADACHE additions when other symptoms detected

## Files Modified

- `pos/routes_consultation.py`: Lines 507-530 (api_analyze endpoint)
  - Added `headache_from_intake` tracking
  - Added `user_clicked_illustration` validation
  - Changed HEADACHE addition logic to require explicit user click
  - Updated transformation reason text

## Related Issues

This fix builds on previous work:
- Negation scope handling (comma-separated lists)
- Spell correction fixes (ulo vs ubo)
- Proximity rescue negation checks

All of these ensure symptoms are correctly detected, but the final gatekeeper is this logic that decides when to add HEADACHE based on headache_location.
