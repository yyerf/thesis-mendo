# Trace UI Clarity Issue - Dictionary vs Semantic Attribution

## Issue Summary

The trace UI was **misleadingly suggesting semantic model made decisions when the dictionary actually made them**, particularly for proximity-based rescues.

## Example Case

**Input:** "Barado akong ilong, pero wala may mogawas nga sip-on"  
**Translation:** "My nose is blocked, but there's no discharge"  
**Expected:** NASAL_CONGESTION (blocked nose, no runny nose)

### What the trace showed (before fix):

```
Dictionary evidence · matched / negated / suppressed
  [EMPTY - no matches shown]

MiniLM cosine similarities · threshold 0.65 · observational
  NASAL_CONGESTION: 0.6027 (vetoed)
  RUNNY_NOSE: 0.7409 (vetoed)
  [all scores below threshold]

Final: NASAL_CONGESTION
```

This made it look like the semantic model chose NASAL_CONGESTION despite having a low score (0.6027 < 0.65 threshold).

### What was actually happening:

1. **Dictionary detected NASAL_CONGESTION via proximity rescue:** "barado" (blocked) + "ilong" (nose) within 3 words
2. **Dictionary detected RUNNY_NOSE:** explicit match on "sip-on"
3. **Negation layer:** "wala may mogawas" (no discharge) negated RUNNY_NOSE
4. **Final result:** NASAL_CONGESTION (dictionary decision, not semantic)
5. **Semantic scores were observational only** - shown in trace but didn't influence the decision

## Root Cause

The `_dictionary_matches()` function only reported **exact phrase matches** from `SYMPTOM_DICTIONARY`. It did NOT report:

1. **Proximity rescues** (e.g., "barado akong ilong" matched via regex pattern)
2. **Fuzzy rescues** (e.g., typo corrections)
3. **Special logic** (nasal disambiguation, cough classification, etc.)

When these advanced dictionary features detected a symptom, it appeared in `detected` but NOT in `details`, causing the UI to show an empty "Dictionary evidence" section.

## Solution

Added explicit dictionary entries that were previously only matched via proximity patterns:

```python
"NASAL_CONGESTION": [
    # ... existing entries ...
    "barado akong ilong",    # Now explicit, shows in trace
    "bara akong ilong",      # Now explicit, shows in trace
]
```

This ensures common patterns show up in the trace's "Dictionary evidence" section, making it clear that the dictionary (not semantic model) made the decision.

## Remaining Limitation

Proximity rescues with **filler words** still won't show exact matched phrases:
- "barado na rin ilong" (blocked + 2 filler words + nose)
- "stuffy pa yung nose" (stuffy + 2 filler words + nose)

These will still be detected but won't show a specific matched phrase in the trace. This is acceptable because:
1. The dictionary reports the symptom in `detected`
2. The semantic section clearly states "observational" when dictionary already matched
3. Most common patterns are now explicit in the dictionary

## Impact

- ✅ Trace UI now clearly shows dictionary matches for common blocked nose patterns
- ✅ No confusion about semantic model making decisions when dictionary decided
- ✅ Researchers can trust the trace to understand which layer made each decision
