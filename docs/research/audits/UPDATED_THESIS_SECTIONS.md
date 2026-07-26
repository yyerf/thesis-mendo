# UPDATED THESIS SECTIONS — Copy-Paste Ready
## Corrected sections for Propsal-latest-thesis.pdf

> These are the sections that need to be replaced in your paper. Each section shows EXACTLY what to paste. All numbers verified against the actual codebase as of March 29, 2026.

---

## 1. FIX: Stage 1 intro paragraph (replace "307 phrases")

**FIND this in your paper:**
> The primary extraction stage uses a curated multilingual symptom dictionary containing 307 phrases across 13 symptom labels, covering five language variants.

**REPLACE WITH:**

The primary extraction stage uses a curated multilingual symptom dictionary containing 331 phrases across 13 symptom labels, covering five language variants. Each phrase was manually verified for linguistic accuracy and clinical relevance through iterative expansion during Iteration 1.

---

## 2. FIX: Table 4 — Symptom Dictionary (phrase counts were wrong)

**REPLACE the entire Table 4 with:**

| Symptom Label | Phrase Count | Languages | Key Examples |
|---|---|---|---|
| FEVER | 43 | Tag/Bis/Eng | "lagnat", "nilalagnat", "hilanat", "init akong lawas" |
| HEADACHE | 42 | Tag/Bis/Eng | "masakit ang ulo", "labad akong ulo", "headache" |
| BODY_ACHES | 39 | Tag/Bis/Eng | "masakit katawan", "binugbog", "bug at akong lawas" |
| STOMACH_ACHE | 38 | Tag/Bis/Eng | "sakit tiyan", "kabag", "hyperacidity" |
| RASHES | 32 | Tag/Bis/Eng | "pantal", "rash", "makati ang balat", "namumula ang balat" |
| SORE_THROAT | 31 | Tag/Bis/Eng | "masakit lalamunan", "sore throat", "garas akong tilaok" |
| COUGH_PRODUCTIVE | 20 | Tag/Bis/Eng | "may plema", "basang ubo", "halak" |
| ALLERGIC_RHINITIS | 17 | Tag/Bis/Eng | "allergy", "bahing", "alerdyi", "makati ilong" |
| DIARRHEA | 17 | Tag/Bis/Eng | "pagtatae", "diarrhea", "lbm", "loose bowel" |
| COUGH_GENERAL | 16 | Tag/Bis/Eng | "ubo", "cough", "inuubo", "gi-ubo" |
| COUGH_DRY | 15 | Tag/Bis/Eng | "walang plema", "tuyong ubo", "dry cough" |
| NASAL_CONGESTION | 11 | Tag/Bis/Eng | "barado ilong", "stuffy nose", "blocked nose" |
| RUNNY_NOSE | 10 | Tag/Bis/Eng | "sipon", "runny nose", "tumutulo ilong" |

Table 4: Symptom Dictionary — 331 phrases across 13 labels

---

## 3. FIX: Stage 2 anchor sentence count (replace "307 curated phrases" reference)

**FIND this in your paper:**
> The semantic fallback covers symptom descriptions that fall outside the dictionary's 307 curated phrases.

**REPLACE WITH:**

The semantic fallback covers symptom descriptions that fall outside the dictionary's 331 curated phrases.

---

## 4. FIX: Anchor sentence count

**FIND:**
> At initialization, 118 anchor sentences (8–12 per symptom label) are pre-encoded into 384-dimensional vectors.

This is actually correct — 118 anchors is verified. Keep as-is.

---

## 5. FIX: Medicine dataset — "23 medicine entries" → 24, "15 fields" stays

**FIND in your paper (Stage 4 section, Table 6 area):**
> The dataset contains 23 medicine entries covering 18 unique brands

**REPLACE WITH:**

The dataset contains 24 medicine entries covering 19 unique brands, representing common OTC medications available in Philippine pharmacies. Multiple entries exist for medicines available in different dosage forms (e.g., Biogesic Tablet and Biogesic Syrup) to enable age-appropriate form selection.

---

## 6. FIX: Medicine Coverage paragraph

**FIND:**
> Medicine Coverage. The 23 entries cover: Cold & Flu (Bioflu), Cold/Decongestant (Neozep, Decolgen, Decolgen Forte, Symdex-D), Cough Suppressant (Tuseran Forte, Sinecod Forte), Expectorant (Ascof Forte, Solmux, Robitussin), Pain & Fever (Biogesic, Advil), Allergy (Cetirizine), Anti-Diarrheal (Loperamide/Diatabs), Probiotic (Erceflora), Antacid (Kremil-S), and Antispasmodic (Buscopan).

**REPLACE WITH:**

Medicine Coverage. The 24 entries cover: Cold & Flu (Bioflu), Cold/Decongestant (Neozep, Decolgen, Decolgen Forte, Symdex-D), Cough Suppressant (Tuseran Forte, Sinecod Forte), Expectorant (Ascof Forte, Solmux, Robitussin), Pain & Fever (Biogesic, Advil), Allergy (Cetirizine), Anti-Diarrheal (Loperamide/Diatabs), Probiotic (Erceflora), Rehydration (Hydrite ORS), Antacid (Kremil-S), and Antispasmodic (Buscopan).

---

## 7. FIX: Introduction scope claim (page 5)

**FIND:**
> it targets a narrowly scoped OTC recommendation task (13 symptoms, 23 medicines)

**REPLACE WITH:**

it targets a narrowly scoped OTC recommendation task (13 symptoms, 24 medicines)

---

## 8. FIX: Benchmark categories — keep "60 categories" (this is correct)

The paper says "60 categories" — verified correct. No change needed.

---

## 9. FIX: Objective 3 (grammatically broken — reads as a statement, not an objective)

**FIND:**
> 3. The dataset will be released as a publicly accessible CSV file hosted on a recognized academic data repository (such as Zenodo or Kaggle Datasets), along with documentation describing the annotation schema, symptom label definitions, and intended use cases to support reproducibility.

**REPLACE WITH:**

3. Release the annotated dataset as a publicly accessible CSV file hosted on a recognized academic data repository (such as Zenodo or Kaggle Datasets), along with documentation describing the annotation schema, symptom label definitions, and intended use cases to support reproducibility.

---

## 10. FIX: Iteration 1 data collection description — Requirement paragraph

**FIND:**
> In parallel, the researchers aim to collect approximately 5,000 symptom-response entries from individuals purchasing OTC medicines at selected Botika ng Bayan pharmacies. These entries should cover the study's predefined base symptoms: fever, cough, cold, headache, allergy, stomachache, and body pain.

This is fine as-is since it clearly says "aim to collect" (future/planned). Keep it.

---

## 11. FIX: Iteration 1 — Implementation paragraph (line count consistency)

Your paper does not cite specific line counts in the main body, which is good. No change needed.

---

## 12. FIX: Table 6 field count reference

**FIND:**
> Each of the 23 medicine entries contains 15 fields:

**REPLACE WITH:**

Each of the 24 medicine entries contains 15 fields:

---

## 13. FIX: "307-phrase" in Comparative Benchmark — Fairness and Transparency (3rd occurrence)

**FIND:**
> Its 307-phrase symptom dictionary was built from clinical references, pharmacy fieldwork, and multilingual language resources, not from the benchmark CSV.

**REPLACE WITH:**

Its 331-phrase symptom dictionary was built from clinical references, pharmacy fieldwork, and multilingual language resources, not from the benchmark CSV.

---

## 14. FIX: Table 8 vs Table 9 — Misleading "different scoring methods" explanation

**FIND:**
> The evaluation uses two different scoring methods, which is why Table 8 and Table 9 show different numbers on the same 288 test cases. This is intentional and not a contradiction: The per-case rubric (Table 8) scores each of the 288 test cases individually — a case counts as "exact match" when the set of detected symptoms exactly equals the set of expected symptoms. By this measure, all 288 cases were exact matches, giving an F1 of 1.000. The multi-label micro-averaging rubric (Table 9) evaluates the same 288 cases across all 13 symptom labels at the same time. Under this protocol, even one missed secondary symptom in one case drags the overall score down. By this stricter measure, the same 288 cases yield 81.2% exact match and a micro F1 of 0.852.

**REPLACE WITH:**

Table 8 and Table 9 show different numbers on the same 288 test cases because they evaluate different stages of the pipeline. In Table 8, when a test case involves cough, the benchmark simulates the user answering the cough clarification question ("Is your cough dry or with phlegm?"), resolving COUGH_GENERAL into the specific cough type. Under that condition, all 288 cases achieve exact match. In Table 9 (the comparative benchmark), this clarification step is removed so that all six models are evaluated on the same raw pipeline output. Without the clarification, 54 cough-related cases are scored as partial mismatches because the system detects COUGH_GENERAL instead of the specific type, yielding 234/288 (81.2%) exact match and a micro F1 of 0.852. The raw-output evaluation in Table 9 is the fairer comparison because the baseline models do not have a clarification mechanism.

> **NOTE:** This is an important correction. The current thesis describes the difference as "per-case rubric vs multi-label micro-averaging rubric," which is inaccurate. The 54-case gap comes entirely from the cough clarification override, not from a different scoring formula.

---

## SUMMARY OF ALL FIND-AND-REPLACE CORRECTIONS

| What to find | Replace with |
|---|---|
| "307 phrases" (appears 3×) | "331 phrases" |
| "307-phrase symptom dictionary" (comparative section) | "331-phrase symptom dictionary" |
| "23 medicine entries" (appears ~3×) | "24 medicine entries" |
| "18 unique brands" (appears ~1×) | "19 unique brands" |
| "23 entries cover" | "24 entries cover" |
| "13 symptoms, 23 medicines" | "13 symptoms, 24 medicines" |
| Table 4 phrase counts | Updated counts (see table above) |
| "Each of the 23 medicine entries contains 15 fields" | "Each of the 24 medicine entries contains 15 fields" |
| Objective 3 ("The dataset will be released") | "Release the annotated dataset" |
| Medicine Coverage (missing Hydrite) | Add "Rehydration (Hydrite ORS)" |
| Table 8/9 "different scoring methods" explanation | Rewrite to explain cough clarification override difference |
| OLDCARTS Sample Implementation (entire section) | Full rewrite — see Fix #15 above |

---

## 16. FIX: "knowledge graph integration" overclaim (Introduction, page 5)

**FIND in your paper (Introduction, page 5):**
> Third, a clinical constraint engine with knowledge graph integration encodes structured relationships between OTC medications, including active ingredients, contraindications, and age-based formulation rules, enabling deterministic safety checks during the recommendation process.

**REPLACE WITH:**

Third, a clinical constraint engine encodes structured relationships between OTC medications — including active ingredients, contraindications, and age-based formulation rules — through a curated JSON dataset, enabling deterministic safety checks during the recommendation process.

> **NOTE:** The system does NOT use a knowledge graph (no graph database, no node-edge data structure). It uses a flat JSON dataset with rule-based lookups. "Knowledge graph integration" is an overclaim that a panelist will catch.

---

## 17. FIX: Table 8/9 — DELETE redundant contradictory "rubric" paragraph

After the correct cough-clarification explanation you already applied, the OLD misleading text is still there. **DELETE** the following two sentences entirely:

> To put it simply: the first rubric asks "did the system get this particular case right?" while the second asks "across every single symptom label in every single case, did it get them all right?" The second one is a much harder bar to clear. We use the stricter rubric for the comparative benchmark (Table 9) because it puts all six models on the exact same scale and makes the comparison fair.

These sentences contradict the correct explanation above them. The difference between Table 8 and Table 9 is NOT about scoring rubrics — both use exact match (set equality). The difference is whether the cough clarification step is simulated. Delete this paragraph entirely.

---

## 18. FIX: Anchor sentence range "8–12" → "5–12"

**FIND:**
> At initialization, 118 anchor sentences (8–12 per symptom label) are pre-encoded into 384-dimensional vectors.

**REPLACE WITH:**

At initialization, 118 anchor sentences (5–12 per symptom label) are pre-encoded into 384-dimensional vectors.

> **NOTE:** Actual per-label counts: COUGH_GENERAL=5, RUNNY_NOSE=5, ALLERGIC_RHINITIS=7, COUGH_DRY=7, NASAL_CONGESTION=7, DIARRHEA=8, BODY_ACHES=9, FEVER=10, COUGH_PRODUCTIVE=12, HEADACHE=12, RASHES=12, SORE_THROAT=12, STOMACH_ACHE=12. Three labels have fewer than 8, so "8–12" is wrong.

---

## 19. FIX: "11 keyword gates per symptom label" → clarify wording

**FIND (Stage 3 processing flow, step 7):**
> Apply lexical guard: 11 keyword gates per symptom label—each semantic detection must be grounded in at least one relevant keyword from the original input text

**REPLACE WITH:**

Apply lexical guard: 11 keyword-gate groups covering all 13 symptom labels — each semantic detection must be grounded in at least one relevant keyword from the original input text

> **NOTE:** There are 11 keyword-gate definitions (cough, plema, diarrhea, nasal, fever, headache, body_aches, stomach, rhinitis, rash, sore_throat) mapped across 13 symptom labels. "Per symptom label" implies each label has 11 separate gates, which is incorrect.

---

## 20. FIX: Introduction OLDCARTS — qualify the scope

**FIND (Introduction, page 5):**
> the system incorporates the OLDCARTS symptom assessment framework, which structures symptom descriptions according to clinically relevant attributes such as onset, location, duration, character, aggravating factors, relieving factors, timing, and severity

**REPLACE WITH:**

the system incorporates elements of the OLDCARTS symptom assessment framework — specifically the Character, Onset, Aggravating, and Timing components — to guide targeted clarification questions for ambiguous symptoms

> **NOTE:** The original sentence lists all 8 OLDCARTS components, implying all are implemented. The system only implements 4 partially: Character (cough type, stomach type), Onset (diarrhea food poisoning trigger), Aggravating (runny nose rain exposure), and Timing (runny nose seasonal patterns). Location, Duration, Relieving, and Severity are NOT implemented.

---

## 21. FIX: Grammar — "traceability and safety critical" (System Architecture section)

**FIND (System Architecture, after Stage 0/1 overview):**
> This arrangement prioritizes traceability and safety critical in a pharmacy context where the system must explain and constrain its outputs rather than generate open-ended medical advice.

**REPLACE WITH:**

This arrangement prioritizes traceability and safety — critical in a pharmacy context where the system must explain and constrain its outputs rather than generate open-ended medical advice.

> **NOTE:** The original sentence parses as "prioritizes [traceability] and [safety critical]" which is grammatically broken. Adding the em-dash makes "critical in a pharmacy context" a parenthetical modifier of both traceability and safety.

---

## 22. FIX: Budget table — Missing Section C label

The budget table labels go **A. Equipment/Hardware → B. Supplies and Materials → D. Transportation and Fieldwork**. There is no **Section C**. Either:
- Add a **C.** label for a missing category (e.g., "C. Software and Subscriptions" with ₱0 since all tools are open-source), OR
- Relabel **D** to **C** so the sequence is A, B, C

This is a minor formatting issue but a panelist may notice the gap.

---

## REMINDER: Only 2 fixes remain NOT APPLIED in the latest PDF

| Fix # | Issue | Why it matters |
|---|---|---|
| **#21** | "traceability and safety critical" — grammatically broken sentence | Minor grammar issue a panelist may notice |
| **#22** | Budget sections skip from B to D (missing C) | Minor formatting issue |

All other fixes (#1–#20) have been successfully applied. Great work!

---

## UPDATED SUMMARY OF ALL CORRECTIONS

| # | What to find | Replace with | Status |
|---|---|---|---|
| 1 | "307 phrases" (3 occurrences) | "331 phrases" | ✅ Applied |
| 2 | Table 4 per-label counts (DIARRHEA=14, etc.) | Corrected counts (DIARRHEA=17, etc.) | ✅ Applied |
| 3 | "307 curated phrases" in Stage 2 | "331 curated phrases" | ✅ Applied |
| 5 | "23 medicine entries" / "18 unique brands" | "24 medicine entries" / "19 unique brands" | ✅ Applied |
| 6 | Medicine Coverage missing Hydrite | Add "Rehydration (Hydrite ORS)" | ✅ Applied |
| 7 | "13 symptoms, 23 medicines" | "13 symptoms, 24 medicines" | ✅ Applied |
| 9 | Objective 3 grammar | "Release the annotated dataset..." | ✅ Applied |
| 12 | "Each of the 23 medicine entries contains 15 fields" | "Each of the 24 medicine entries" | ✅ Applied |
| 13 | "307-phrase" in comparative section | "331-phrase" | ✅ Applied |
| 14 | Table 8/9 "different scoring methods" explanation | Cough clarification override explanation | ✅ Applied |
| 15 | OLDCARTS Sample Implementation rewrite | Full rewrite with diarrhea scenario | ✅ Applied |
| 16 | "knowledge graph integration" (Introduction) | "curated JSON dataset" | ✅ Applied |
| 17 | Redundant "rubric" paragraph after Table 8/9 explanation | DELETE entirely | ✅ Applied |
| 18 | Anchor range "8–12 per label" | "5–12 per label" | ✅ Applied |
| 19 | "11 keyword gates per symptom label" | "11 keyword-gate groups covering all 13 labels" | ✅ Applied |
| 20 | OLDCARTS lists all 8 components | Qualify: "elements of... specifically Character, Onset, Aggravating, and Timing" | ✅ Applied |
| 21 | "traceability and safety critical" (grammar) | "traceability and safety — critical" | ❌ NOT APPLIED |
| 22 | Budget sections skip A, B, D (missing C) | Relabel D→C or add a C section | ❌ NOT APPLIED |

---

## 15. FIX: OLDCARTS Sample Implementation — Major Rewrite Needed

The current "OLDCARTS Sample Implementation" section describes a system that parses OLDCARTS fields (location, duration, severity) from free-text input, tracks which fields are "satisfied," and adaptively asks for missing ones. **The actual system does none of this.** The real system detects symptom labels (e.g., HEADACHE) as a whole, then asks at most one fixed clarification question per symptom domain when context clues are absent from the input.

**DELETE the entire OLDCARTS Sample Implementation section and REPLACE WITH:**

OLDCARTS Sample Implementation. To illustrate how the OLDCARTS-inspired clarification layer operates in the actual system, consider the following scenario. A user, 28 years old, approaches the pharmacy kiosk and types: "nagtatae ako" (I have diarrhea).

The system's hybrid pipeline detects a single symptom: DIARRHEA. Because diarrhea is the sole detected symptom and the input contains no contextual clues about food poisoning, fever, or other triggers, the system triggers a clarification question rather than immediately recommending a medicine:

> "Para mas tama ang i-recommend, pakisagot:
> • Kumain ka ba ng panis o expired na pagkain? (Did you eat spoiled or expired food?)
> • May lagnat ka ba? (Do you have fever?)"

The user selects "Oo, kumain ng panis" (Yes, ate spoiled food). This maps to the OLDCARTS Onset component — identifying the triggering event. The system now classifies the diarrhea as food-poisoning-related, which changes the recommendation strategy: it prioritizes Hydrite (ORS) for rehydration and Erceflora (probiotic), while explicitly excluding Loperamide (Diatabs) because anti-diarrheal agents can trap bacteria or toxins in the body during food poisoning.

Had the user instead answered "Hindi naman" (No, no bad food), the system would recommend standard anti-diarrheal medicine alongside ORS.

This pattern repeats across three other symptom domains. For cough, the system asks whether the cough is dry or with phlegm — mapping to the Character component — because dry cough requires a suppressant (e.g., Sinecod) while productive cough requires an expectorant (e.g., Solmux), and giving the wrong type can be harmful. For stomach ache, it asks whether the sensation is burning/acidic or cramping/bloating, again mapping to Character, to distinguish between an antacid (e.g., Kremil-S) and an antispasmodic (e.g., Buscopan). For runny nose, it asks about co-occurring symptoms, sneezing or itchy nose, and cold or rain exposure — touching the Character, Aggravating, and Timing components — to differentiate viral cold, allergic rhinitis, and weather-induced vasomotor rhinitis. The weather-induced case receives no medicine recommendation at all, only a rest-and-hydration advisory.

Two important design constraints shape this layer. First, clarification is only triggered when the symptom appears as the sole complaint and no contextual clues are detected in the original input text. If the user's input already contains enough information — for instance, "nagtatae ako, kumain kasi ako ng panis" — the system skips the question and acts on the detected context directly. Second, the system asks at most one follow-up question per consultation, keeping the kiosk interaction fast and minimally intrusive.

The system also applies passive context detection for headache. If the input contains hunger, dehydration, or fatigue clues, instead of asking a clarification question, it appends a safety advisory: "Your headache may be related to hunger, dehydration, or fatigue. Try eating a meal, drinking water, and resting first." This is an Onset-inspired detection that does not require user interaction.

When neither the dictionary extraction nor the semantic fallback detects any recognizable symptoms, the system does not return a blank screen. Instead, it displays a clear message telling the user that no OTC-related symptoms could be identified from their input, and suggests three options: (1) rephrasing with more specific symptom words, (2) trying a different language if non-standard phrasing was used, or (3) consulting a licensed pharmacist directly for an in-person assessment.
