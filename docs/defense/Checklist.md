# OLDCARTS Duration Safeguard Matrix — Implementation Checklist

## Overview
Implementing the Duration component of OLDCARTS as a universal safety measure across all 9 symptom categories. When a symptom exceeds its clinically-defined duration threshold, the system blocks OTC recommendations and refers the patient to a doctor.

## Duration Safeguard Matrix

| # | Symptom | Threshold | Action | Clinical Rationale |
|---|---------|-----------|--------|-------------------|
| 1 | FEVER | > 3 days | Block / Refer | Dengue, Typhoid, Malaria indicator |
| 2 | DIARRHEA | > 2 days | Block / Refer | Dehydration risk, bacterial/parasitic infection |
| 3 | SORE_THROAT | > 5 days | Block / Refer | Streptococcal infection risk |
| 4 | STOMACH_ACHE | > 7 days | Block / Refer | PUD, gallstones, appendicitis |
| 5 | HEADACHE | > 7 days | Block / Refer | Hypertension, neurological issues |
| 6 | BODY_ACHES | > 7 days | Block / Refer | Inflammatory arthritis, nerve damage |
| 7 | RASHES / ALLERGIC_RHINITIS | > 7 days | Block / Refer | Fungal infection, chronic immune issue |
| 8 | NASAL_CONGESTION / RUNNY_NOSE | > 10 days | Block / Refer | Bacterial sinusitis |
| 9 | COUGH (all types) | > 14 days | Block / Refer | TB screening (DOH protocol) |

## Design Decisions
- **Question Format**: Multiple choice buttons (Option A)
- **Exceeded Behavior**: Block OTC entirely — no recommendations, refer to doctor
- **Flow Order**: After existing clarification (e.g. cough type → then duration)
- **Multi-symptom**: Ask duration for each symptom separately

---

## Implementation Tasks

### Backend (mendo_core/step4_recommend.py)
- [x] Add `DURATION_THRESHOLDS` dictionary mapping symptom labels to day thresholds
- [x] Add `check_duration_safety()` function
- [x] Add `get_duration_question()` function returning per-symptom question + button options
- [x] Add duration referral response builder (doctor referral message)
- [x] Add `parse_duration_days()` for button value parsing
- [x] Add `_DURATION_OPTIONS` with bilingual button labels per symptom
- [x] Add `_SYMPTOM_DISPLAY_NAMES` for Tagalog/English question text

### API Routes (pos/routes_consultation.py)
- [x] Add `/consult/api/duration-check` POST route
- [x] Integrate duration flow into consultation state machine
- [x] Handle multi-symptom sequential duration asking (pending_durations chaining)
- [x] Add POS inventory cross-reference for final recommendation
- [x] Add interaction logging for both block and pass outcomes

### Frontend UI (web/templates/pos/consultation.html)
- [x] Add duration question display component (consistent with existing clarification UI)
- [x] Add duration button options (multiple choice)
- [x] Add doctor referral display (block screen with warning + clinical rationale)
- [x] Wire duration flow: after clarification → ask duration per symptom → proceed or block
- [x] Handle multi-symptom sequential duration questions
- [x] Add progress dots for multi-symptom duration tracking
- [x] Add CSS for `.duration-referral-banner` and `.duration-progress`
- [x] Reset duration state in `assessAgain()` and `resetAll()`

### Testing (testing/test_regressions.py)
- [x] Add tests for each symptom's duration threshold (11 blocked tests)
- [x] Test duration block behavior (no recommendations returned)
- [x] Test duration safe behavior (5 safe tests)
- [x] Test multi-symptom duration flow (chain test)
- [x] Test edge cases (exactly at threshold — 4 tests)
- [x] Test API endpoint (safe, blocked, chain, missing params — 4 tests)
- [x] Test `parse_duration_days()` (4 tests)
- [x] Test `get_duration_question()` coverage (1 test)
- [x] Test threshold count verification (1 test)

### Thesis Updates (FULL_SYSTEM_DATA_FOR_THESIS.md)
- [x] Update OLDCARTS section — now covers 5 components (Character, Onset, Aggravating, Timing, Duration)
- [x] Add Duration Safeguard Matrix table with all 13 entries
- [x] Update system architecture description (API endpoints)
- [x] Update safety measures section (Key Technical Innovations #20)
- [x] Add Tier 5 testing documentation (31 duration tests)
- [x] Update Iteration 3 description
- [x] Add OLDCARTS to Theoretical Framework

---

## Progress Log
- **Started**: March 30, 2026
- **Status**: ✅ Complete

### Test Results
- **74/74 regression tests passed** (43 original + 31 new duration tests)
- **All 3 API scenarios verified** (safe, blocked, chain)
- **Runtime**: ~13.5 seconds

### Files Modified
| File | Changes |
|------|---------|
| `mendo_core/step4_recommend.py` | Added DURATION_THRESHOLDS, check_duration_safety(), get_duration_question(), parse_duration_days() |
| `pos/routes_consultation.py` | Added `/consult/api/duration-check` route with full flow logic |
| `web/templates/pos/consultation.html` | Added duration UI, CSS, JS flow, referral banner |
| `testing/test_regressions.py` | Added DurationSafeguardTests class (31 tests) |
| `FULL_SYSTEM_DATA_FOR_THESIS.md` | Updated OLDCARTS to 5 components, added Duration Matrix table, Tier 5 tests, Innovation #20 |
