# Live Demo Script

This file is a strict, panel-safe live demo guide for tomorrow.

All sample inputs below were cross-checked against the current app.

## Demo Goal

Show four things in under 3 minutes:

1. Basic symptom detection and recommendation
2. Clarification instead of guessing
3. Safety triage for emergency-like symptoms
4. Multilingual support

## Important Note Before the Demo

For red-flag cases like difficulty breathing or chest pain, the system may show:

1. No symptom labels
2. Immediate triage or referral

That is correct behavior.

The system is designed to avoid giving OTC recommendations when it detects emergency patterns.

Example:

`hirap huminga ako`

This does not return a normal symptom label, but it does trigger a red-flag triage response.

## Suggested Demo Order

Use this exact order:

1. Normal recommendation
2. Clarification flow
3. Safety triage
4. Multilingual support

This is the safest order because it starts simple, then shows intelligence, then safety, then localization.

## 3-Minute Word-for-Word Script

### Opening Line

"For this demo, I will show how Mendo handles a normal consultation, how it asks clarification questions instead of guessing, how it blocks unsafe self-medication in emergency-like cases, and how it supports multilingual input."

### Demo 1: Normal Recommendation

Type:

`masakit ang ulo ko at may lagnat`

Expected behavior:

1. Detects `HEADACHE` and `FEVER`
2. Recommends medicines such as `Biogesic`, `Advil`, `Bioflu`, `Decolgen`, `Decolgen Forte`

What to say:

"In this first case, the system detects multiple symptoms from a normal patient-style input. It identifies headache and fever, then it returns suitable OTC options from the medicine dataset. This shows the standard recommendation path."

### Demo 2: Clarification Instead of Guessing

Type:

`may ubo ako`

Expected behavior:

1. Detects `COUGH_GENERAL`
2. Asks: `Is your cough dry or with phlegm?`

What to say:

"Here, the system does not guess immediately. It detects that the user has cough, but cough is still too broad for a safe recommendation. So instead of forcing an answer, it asks a clarification question first."

Then choose one follow-up:

Option A:

Select or answer `dry cough`

Expected result:

1. Recommends `Tuseran Forte`, `Sinecod Forte`

What to say:

"If the cough is dry, the recommendations shift to medicines intended for dry cough."

Option B:

Select or answer `with phlegm`

Expected result:

1. Recommends `Ascof Forte`, `Solmux`, `Robitussin`

What to say:

"If the cough has phlegm, the recommendations change accordingly. This shows that the system is not just matching keywords. It changes the output based on clarified symptom character."

### Demo 3: Safety Triage

Type:

`hirap huminga ako`

Expected behavior:

1. No normal symptom labels are returned
2. The system immediately gives a triage response
3. It warns: `CONSULT A LICENSED MEDICAL EXPERT IMMEDIATELY`

What to say:

"This is a safety case. Even though the system does not return a normal symptom label, it detects a red-flag pattern for difficulty breathing. Instead of recommending OTC medicine, it immediately escalates the case. This is intentional, because the system is designed to block unsafe self-medication."

If you want a backup triage case, use:

`masakit ang dibdib ko`

Expected behavior:

1. Immediate triage for possible cardiac emergency

### Demo 4: Multilingual Support

Type:

`labad akong ulo ug gihilanat ko`

Expected behavior:

1. Detects `HEADACHE` and `FEVER`
2. Recommends medicines such as `Biogesic`, `Advil`, `Bioflu`, `Decolgen`, `Decolgen Forte`

What to say:

"This example is in Bisaya. The system still recognizes the same symptoms and produces the corresponding recommendation flow. This matters because real pharmacy users do not speak in only one language."

### Optional Extra Demo: Code-Switching

Type:

`masakit head ko and may cough ako`

Expected behavior:

1. Detects `HEADACHE` and `COUGH_GENERAL`
2. Still asks clarification for the cough type

What to say:

"This input mixes Filipino and English. The system still detects the symptoms correctly and keeps the same safety behavior by asking clarification for the cough."

### Closing Line

"So in summary, the system does not only identify symptoms. It also asks clarification when needed, blocks unsafe OTC suggestions for emergency-like cases, and supports multilingual real-world input."

## Fastest Safe Version

If time becomes very short, do only these three:

1. `masakit ang ulo ko at may lagnat`
2. `may ubo ako`
3. `hirap huminga ako`

That already shows:

1. Recommendation
2. Clarification
3. Safety triage

## Exact Verified Cases

These were cross-checked against the current app:

1. `masakit ang ulo ko at may lagnat`
   Result: recommend

2. `may ubo ako`
   Result: ask clarify

3. `nagtatae ako`
   Result: ask clarify

4. `hirap huminga ako`
   Result: triage

5. `masakit ang dibdib ko`
   Result: triage

6. `labad akong ulo ug gihilanat ko`
   Result: recommend

7. `masakit head ko and may cough ako`
   Result: ask clarify

## Diarrhea Clarification Demo

Use this only if you want a second clarification example.

Type:

`nagtatae ako`

Expected behavior:

1. The system asks whether spoiled food may be involved
2. It separates infectious-like context from non-infectious context

If you choose `No, no bad food`:

Expected recommendations:

1. `Hydrite (ORS)`
2. `Loperamide (Diatabs)`
3. `Erceflora`

If you choose `Yes, ate spoiled food`:

Expected recommendations:

1. `Hydrite (ORS)`
2. `Erceflora`

What to say:

"This shows that the system changes its recommendation logic based on context. It avoids treating all diarrhea cases the same way."

## Backup Lines If Something Looks Unexpected

If the panel asks why a triage case has no symptom label, say:

"That is expected. Emergency-like patterns are intercepted by the safety layer, so the system prioritizes referral over ordinary symptom labeling."

If the panel asks why the system asks a question instead of recommending right away, say:

"Because the system is designed to avoid guessing when the symptom is still clinically ambiguous for OTC selection."

If the panel asks why you are not starting with voice, say:

"Voice is only an input convenience layer. The main contribution of the thesis is the hybrid symptom analysis and safety-controlled recommendation pipeline."

## Night-Before Checklist

1. Start the app before the demo and let the model warm up
2. Use text input as the main path
3. Keep voice optional only if already tested on the same machine and browser
4. Keep this demo order visible beside you
5. Do not let the panel freestyle the first input
