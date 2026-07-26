# Copy-Paste Thesis Updates for Duration Safeguard Matrix

Below are all the sections in the thesis that need to be updated or added to reflect the Duration Safeguard implementation. Each section includes the **page/line location**, what to **find** in the current text, and the **replacement text** to paste in.

---

## UPDATE 1 — Introduction, Paragraph about OLDCARTS (around lines 204–206)

**FIND THIS TEXT:**

> To further improve the clinical interpretation of symptoms and enhance recommendation safety, the system incorporates elements of the OLDCARTS symptom assessment framework — specifically the Character, Onset, Aggravating, and Timing components — to guide targeted clarification questions for ambiguous symptoms [31, 32]. This structured representation allows the system to capture additional contextual information about symptoms that may influence appropriate medication selection.

**REPLACE WITH:**

> To further improve the clinical interpretation of symptoms and enhance recommendation safety, the system incorporates elements of the OLDCARTS symptom assessment framework — specifically the Character, Onset, Aggravating, Timing, and Duration components — to guide targeted clarification questions for ambiguous symptoms and enforce time-based safety limits [31, 32]. This structured representation allows the system to capture additional contextual information about symptoms that may influence appropriate medication selection, while also screening for cases that have persisted long enough to warrant professional medical evaluation rather than OTC self-treatment.

---

## UPDATE 2 — Objective 1 (around lines 228–231)

**FIND THIS TEXT:**

> Design and implement a multilingual natural language processing framework capable of detecting and interpreting user-described symptoms, including linguistic challenges such as negation, abbreviations, multi-symptom expressions, and mixed-language inputs, while incorporating structured symptom assessment through the OLDCARTS framework.

**REPLACE WITH:**

> Design and implement a multilingual natural language processing framework capable of detecting and interpreting user-described symptoms, including linguistic challenges such as negation, abbreviations, multi-symptom expressions, and mixed-language inputs, while incorporating structured symptom assessment through the OLDCARTS framework, including a duration-based safety check that screens for symptoms persisting beyond clinically safe thresholds for OTC self-medication.

---

## UPDATE 3 — Methods, Iteration 1: Design paragraph (around lines 326–329)

**FIND THIS TEXT:**

> Safety requirements were addressed through a dedicated triage layer at the front of the pipeline and a centralized safety filter at the end. The clarification mechanism was modeled after the OLDCARTS clinical assessment framework, adapted to only ask follow-up questions for symptom attributes that are genuinely ambiguous (such as cough type or diarrhea context).

**REPLACE WITH:**

> Safety requirements were addressed through a dedicated triage layer at the front of the pipeline, a centralized safety filter at the end, and a duration-based screening step that checks how long each detected symptom has persisted before proceeding with OTC recommendations. The clarification mechanism was modeled after the OLDCARTS clinical assessment framework, adapted to only ask follow-up questions for symptom attributes that are genuinely ambiguous (such as cough type or diarrhea context) and to screen for symptoms that have lasted beyond the safe limits for self-medication.

---

## UPDATE 4 — Methods, Iteration 1: Implementation paragraph (around lines 337–339)

**FIND THIS TEXT:**

> An OLDCARTS-inspired clarification layer was also implemented, particularly for context-sensitive complaints such as cough, diarrhea, headache, stomachache, and runny nose.

**REPLACE WITH:**

> An OLDCARTS-inspired clarification layer was also implemented, covering context-sensitive complaints such as cough, diarrhea, headache, stomachache, and runny nose. In addition, a duration safeguard was built into the recommendation flow as a universal safety measure applied across all nine symptom categories. For each detected symptom, the system asks the user how long the complaint has persisted, using bilingual multiple-choice buttons. If the reported duration exceeds a clinically defined threshold — for instance, more than three days for fever or more than fourteen days for cough — the system blocks all OTC recommendations for that symptom and advises the user to consult a licensed medical professional instead.

---

## UPDATE 5 — Conceptual Framework, Fifth Stage (around lines 572–576)

**FIND THIS TEXT:**

> In the fifth stage, validated symptoms are matched against the OTC medicine database using a recommendation engine that factors in symptom relevance, age restrictions, contraindications, and safety rules. The system presents appropriate recommendations with dosage guidance and safety reminders—or, if the case exceeds the safe scope of OTC use, advises the user to consult a healthcare professional.

**REPLACE WITH:**

> In the fifth stage, validated symptoms first pass through a duration screening step where the user is asked, for each detected symptom, how long the complaint has persisted. If the reported duration exceeds a clinically defined threshold specific to that symptom, the system blocks OTC recommendations and refers the user to a healthcare professional. Only symptoms that fall within safe self-medication timeframes proceed to the recommendation engine, which matches them against the OTC medicine database using symptom relevance, age restrictions, contraindications, and safety rules. The system presents appropriate recommendations with dosage guidance and safety reminders—or, if the case exceeds the safe scope of OTC use, advises the user to consult a healthcare professional.

---

## UPDATE 6 — System Architecture, traceability paragraph (around lines 594–596)

**FIND THIS TEXT:**

> This arrangement prioritizes traceability and safety critical in a pharmacy context where the system must explain and constrain its outputs rather than generate open-ended medical advice.

**REPLACE WITH:**

> This arrangement prioritizes traceability and safety in a pharmacy context where the system must explain and constrain its outputs rather than generate open-ended medical advice.

*(Note: This also fixes the grammar issue from Fix #21 — "safety critical" → "safety")*

---

## UPDATE 7 — OLDCARTS Clarification Layer (around lines 910–916)

**FIND THIS TEXT:**

> OLDCARTS Clarification Layer. Targeted clarification logic collects additional context for symptoms where the label alone is insufficient for a safe recommendation—such as cough type disambiguation, diarrhea context, or runny nose triggers. The clarification layer is treated as a practical assessment heuristic within the recommendation design, not as a core theoretical pillar [31, 32].

**REPLACE WITH:**

> OLDCARTS Clarification and Duration Screening Layer. The system uses targeted clarification logic to collect additional context for symptoms where the label alone is insufficient for a safe recommendation—such as cough type disambiguation, diarrhea context, or runny nose triggers. The clarification layer is treated as a practical assessment heuristic within the recommendation design, not as a core theoretical pillar [31, 32]. Beyond these context-specific clarifications, the system also implements the Duration component of the OLDCARTS framework as a universal safety measure applied across all nine symptom categories. After any applicable clarification questions are resolved, the system asks the user how long each detected symptom has persisted, presenting bilingual multiple-choice options (for example, "1–2 days / 1–2 araw", "3 days / 3 araw", "More than 3 days / Higit sa 3 araw" for fever). If the reported duration exceeds the clinically defined threshold for that particular symptom, the system blocks all OTC recommendations and displays a referral notice advising the user to consult a licensed healthcare professional, along with the clinical basis for the referral.

---

## UPDATE 8 — NEW TABLE: Insert right after the updated OLDCARTS Clarification Layer text above (after the replacement in Update 7)

**INSERT THIS NEW PARAGRAPH AND TABLE:**

> The duration thresholds were derived from Philippine Department of Health clinical guidelines, standard OTC package insert warnings, and published infectious disease surveillance protocols relevant to the Philippine setting. The thresholds are intentionally conservative: they represent the upper limit of safe self-medication rather than the point where clinical danger begins. Table X summarizes the duration safeguard matrix.

>

> *Table X: Duration Safeguard Matrix — Symptom-Specific Thresholds for OTC Self-Medication*

>

> | Symptom | Threshold | Action if Exceeded | Clinical Rationale |
> |---|---|---|---|
> | Fever | > 3 days | Block OTC, refer | Dengue, typhoid, malaria indicator (endemic PH) |
> | Diarrhea | > 2 days | Block OTC, refer | Dehydration risk; bacterial or parasitic infection |
> | Sore Throat | > 5 days | Block OTC, refer | Streptococcal infection; rheumatic fever risk |
> | Stomach Ache | > 7 days | Block OTC, refer | Peptic ulcer, gallstones, appendicitis |
> | Headache | > 7 days | Block OTC, refer | Hypertension, neurological issues, medication overuse headache |
> | Body Aches | > 7 days | Block OTC, refer | Inflammatory arthritis, nerve damage, post-viral sequelae |
> | Rashes | > 7 days | Block OTC, refer | Fungal infection, scabies, chronic immune condition |
> | Allergic Rhinitis | > 7 days | Block OTC, refer | Chronic immune issue requiring prescription treatment |
> | Nasal Congestion | > 10 days | Block OTC, refer | Bacterial sinusitis |
> | Runny Nose | > 10 days | Block OTC, refer | Bacterial sinus infection |
> | Cough (all types) | > 14 days | Block OTC, refer | TB screening protocol (DOH, endemic PH) |

>

> The duration check is performed per symptom. When the system detects multiple symptoms, it asks about each one sequentially, displaying a progress indicator (for example, "Symptom 1 of 3") so the user knows how many questions remain. If even one symptom exceeds its threshold, that symptom's recommendations are blocked and a referral is shown, while symptoms within safe timeframes proceed to the recommendation engine. This design ensures that cases where OTC treatment is still appropriate for some symptoms are not unnecessarily blocked entirely.

---

## UPDATE 9 — OLDCARTS Sample Implementation scenarios (around lines 950–957)

**FIND THIS TEXT:**

> This pattern repeats across three other symptom domains. For cough, the system asks whether the cough is dry or with phlegm — mapping to the Character component — because dry cough requires a suppressant (e.g., Sinecod) while productive cough requires an expectorant (e.g., Solmux), and giving the wrong type can be harmful. For stomach ache, it asks whether the sensation is burning/acidic or cramping/bloating, again mapping to Character, to distinguish between an antacid (e.g., Kremil-S) and an antispasmodic (e.g., Buscopan). For runny nose, it asks about co-occurring symptoms, sneezing or itchy nose, and cold or rain exposure — touching the Character, Aggravating, and Timing components — to differentiate viral cold, allergic rhinitis, and weather-induced vasomotor rhinitis. The weather-induced case receives no medicine recommendation at all, only a rest-and-hydration advisory.

**REPLACE WITH:**

> This pattern repeats across three other symptom domains. For cough, the system asks whether the cough is dry or with phlegm — mapping to the Character component — because dry cough requires a suppressant (e.g., Sinecod) while productive cough requires an expectorant (e.g., Solmux), and giving the wrong type can be harmful. For stomach ache, it asks whether the sensation is burning/acidic or cramping/bloating, again mapping to Character, to distinguish between an antacid (e.g., Kremil-S) and an antispasmodic (e.g., Buscopan). For runny nose, it asks about co-occurring symptoms, sneezing or itchy nose, and cold or rain exposure — touching the Character, Aggravating, and Timing components — to differentiate viral cold, allergic rhinitis, and weather-induced vasomotor rhinitis. The weather-induced case receives no medicine recommendation at all, only a rest-and-hydration advisory.
>
> After all applicable clarification questions have been resolved, the system then applies the Duration component. The user is asked how long the symptom has lasted through a set of bilingual multiple-choice buttons tailored to that symptom's threshold. For instance, a user who reported diarrhea from spoiled food would next see: "Gaano na katagal ang pagtatae? / How long have you had diarrhea?" with options like "1 day," "2 days," and "More than 2 days." If the user selects "More than 2 days," the system blocks the OTC recommendation and displays a referral notice explaining that diarrhea lasting beyond two days may indicate a bacterial or parasitic infection requiring medical evaluation. If the duration falls within the safe range, the system proceeds with the recommendation normally. This duration check applies universally to all nine symptom categories, not just those with context-specific clarifications.

---

## UPDATE 10 — Design constraints paragraph (around lines 960–967)

**FIND THIS TEXT:**

> Two important design constraints shape this layer. First, clarification is only triggered when the symptom appears as the sole complaint and no contextual clues are detected in the original input text. If the user's input already contains enough information — for instance, "nagtatae ako, kumain kasi ako ng panis" — the system skips the question and acts on the detected context directly. Second, the system asks at most one follow-up question per consultation, keeping the kiosk interaction fast and minimally intrusive.

**REPLACE WITH:**

> Two important design constraints shape the clarification layer. First, context-specific clarification (such as cough type or diarrhea onset) is only triggered when the symptom appears as the sole complaint and no contextual clues are detected in the original input text. If the user's input already contains enough information — for instance, "nagtatae ako, kumain kasi ako ng panis" — the system skips the question and acts on the detected context directly. Second, the system asks at most one context-specific follow-up question per consultation, keeping the interaction fast and minimally intrusive. The duration check, however, is asked for every detected symptom regardless of whether a clarification question was triggered, because the decision about whether OTC treatment is still appropriate depends on how long the condition has lasted, which cannot be inferred from the initial symptom description alone.

---

## UPDATE 11 — Recommendation Logic, Step 5 (around lines 1085–1090)

**FIND THIS TEXT:**

> 5. Safety Checks: (a) Paracetamol overlap detection warns when multiple paracetamol-containing medicines are recommended; (b) opposing mechanism warnings flag simultaneous expectorant and suppressant recommendations; (c) age filtering removes medicines below the user's minimum age requirement.

**REPLACE WITH:**

> 5. Safety Checks: (a) Paracetamol overlap detection warns when multiple paracetamol-containing medicines are recommended; (b) opposing mechanism warnings flag simultaneous expectorant and suppressant recommendations; (c) age filtering removes medicines below the user's minimum age requirement; (d) duration screening blocks OTC recommendations when the user reports symptom persistence beyond the clinically defined safe threshold for that symptom category (see Table X: Duration Safeguard Matrix).

---

## UPDATE 12 — Evaluation Methodology, Benchmark Design: Add Tier 5 (around lines 1162–1170)

**FIND THIS TEXT:**

> Tier 4: Triage Safety (24 tests) — Chest pain, breathing difficulty, blood symptoms, loss of consciousness, seizure, severe allergic reaction, high fever thresholds, mixed emergency/symptom cases.

**REPLACE WITH:**

> Tier 4: Triage Safety (24 tests) — Chest pain, breathing difficulty, blood symptoms, loss of consciousness, seizure, severe allergic reaction, high fever thresholds, mixed emergency/symptom cases.
>
> Tier 5: Duration Safeguard (31 tests) — Duration input parsing for various time expressions, question generation coverage across all symptom categories, safe-pass verification for durations within threshold, blocked-referral verification for durations exceeding threshold, exact-boundary edge cases at each threshold limit, API response format validation for safe, blocked, and multi-symptom chaining scenarios, and threshold completeness checks confirming all 13 symptom–duration entries are present.

---

## UPDATE 13 — Iteration 1 Testing paragraph (around lines 353–357)

**FIND THIS TEXT:**

> Testing. After implementation, the system underwent structured testing and validation. The baseline system was evaluated through structured benchmark cases, regression checks, and scenario-based safety validation. These tests verified whether the system could correctly recognize symptoms, suppress unsafe recommendations when red flags were present, and trigger clarification prompts when additional context was needed. Testing also confirmed that the modules work effectively as a complete pipeline rather than as isolated components.

**REPLACE WITH:**

> Testing. After implementation, the system underwent structured testing and validation. The baseline system was evaluated through structured benchmark cases, regression checks, and scenario-based safety validation. These tests verified whether the system could correctly recognize symptoms, suppress unsafe recommendations when red flags were present, trigger clarification prompts when additional context was needed, and block OTC recommendations when reported symptom duration exceeded safe thresholds. Testing also confirmed that the modules work effectively as a complete pipeline rather than as isolated components. The duration safeguard was validated through 31 dedicated regression tests covering input parsing, question generation, threshold enforcement at exact boundary values, and API response formatting for single-symptom and multi-symptom chaining scenarios.

---

## UPDATE 14 — Iteration 1 Review paragraph (around lines 364–370)

**FIND THIS TEXT:**

> Review. At the end of the first iteration, the researchers reviewed the system output to check whether it met the expected standards. The system evaluation confirmed 288/288 exact matches on the structured benchmark, 9/9 exact matches on the semantic stress set, and 72/80 (90%) exact matches on the real-user simulation set, with zero outright failures across all 377 test cases.

**REPLACE WITH:**

> Review. At the end of the first iteration, the researchers reviewed the system output to check whether it met the expected standards. The system evaluation confirmed 288/288 exact matches on the structured benchmark, 9/9 exact matches on the semantic stress set, and 72/80 (90%) exact matches on the real-user simulation set, with zero outright failures across all 377 test cases. Additionally, 74 regression tests — including 31 tests dedicated to the duration safeguard — all passed, confirming that the clarification logic, duration screening, and overall pipeline behavior remained stable.

---

## UPDATE 15 — Iteration 3 paragraph about system refinement (around lines 441–444)

**FIND THIS TEXT:**

> Implementation. Software refinements may include expanding the multilingual dictionary, adjusting semantic thresholds, improving clarification prompts, strengthening rule-based safety checks, and updating the medicine dataset based on expert feedback.

**REPLACE WITH:**

> Implementation. Software refinements may include expanding the multilingual dictionary, adjusting semantic thresholds, improving clarification prompts, refining duration thresholds based on pharmacist feedback and observed referral patterns, strengthening rule-based safety checks, and updating the medicine dataset based on expert feedback.

---

## UPDATE 16 — Why Not a Large Language Model, Point 1 (around lines 1398–1410)

**FIND THIS TEXT:**

> Safety and determinism. When a system recommends medicine, a wrong answer can cause real harm. LLMs produce text probabilistically. Run the same prompt twice and you might get different advice. They can hallucinate drug names, miss a negation in the input, or suggest a medicine that is contraindicated for a child. Our pipeline avoids this by design: paracetamol overlap checks, opposing-mechanism warnings, age-based formulation filters, and red-flag triage suppression are all hard-coded rules that fire on every single consultation without exception.

**REPLACE WITH:**

> Safety and determinism. When a system recommends medicine, a wrong answer can cause real harm. LLMs produce text probabilistically. Run the same prompt twice and you might get different advice. They can hallucinate drug names, miss a negation in the input, or suggest a medicine that is contraindicated for a child. Our pipeline avoids this by design: paracetamol overlap checks, opposing-mechanism warnings, age-based formulation filters, red-flag triage suppression, and duration-based referral thresholds are all hard-coded rules that fire on every single consultation without exception.

---

## UPDATE 17 — Error-Driven Iterative Refinement (around lines 1465–1470)

**FIND THIS TEXT:**

> During Iteration 1, the system was tested by deliberately feeding it tricky and unusual inputs to find weaknesses. This process revealed 19 issues spread across common problem areas like the system misunderstanding negation (e.g., "wala nako'y ubo" being read as a cough instead of "no cough"), mixing up similar symptom types, incorrectly identifying symptoms from unrelated words, and missing certain safety-critical patterns. Each issue was fixed one at a time, and after every fix the full 288-case benchmark was re-run to make sure nothing that was already working got broken.

**REPLACE WITH:**

> During Iteration 1, the system was tested by deliberately feeding it tricky and unusual inputs to find weaknesses. This process revealed 19 issues spread across common problem areas like the system misunderstanding negation (e.g., "wala nako'y ubo" being read as a cough instead of "no cough"), mixing up similar symptom types, incorrectly identifying symptoms from unrelated words, and missing certain safety-critical patterns. Each issue was fixed one at a time, and after every fix the full 288-case benchmark was re-run to make sure nothing that was already working got broken. In addition, the duration safeguard was developed and validated through its own dedicated set of 31 regression tests, covering duration parsing, threshold enforcement at exact boundary values, and API-level behavior for single-symptom and multi-symptom scenarios.

---

---

## NEW REFERENCES — Add to the References section after [32]

Paste these at the end of your References list. These support the Duration Safeguard Matrix thresholds (Table X) used in Updates 7, 8, and 11.

```
[33] World Health Organization. (2025, August 21). Dengue. WHO Fact Sheets.
https://www.who.int/news-room/fact-sheets/detail/dengue-and-severe-dengue

[34] Centers for Disease Control and Prevention. (2025, August 7). Symptoms of
dengue and testing. CDC.
https://www.cdc.gov/dengue/signs-symptoms/index.html

[35] Mayo Clinic Staff. (2025, January 18). Diarrhea — Symptoms and causes.
Mayo Clinic.
https://www.mayoclinic.org/diseases-conditions/diarrhea/symptoms-causes/syc-20352241

[36] World Health Organization. (2024, March 7). Diarrhoeal disease. WHO Fact
Sheets.
https://www.who.int/news-room/fact-sheets/detail/diarrhoeal-disease

[37] Mayo Clinic Staff. (2025, April 12). Sore throat — Symptoms and causes.
Mayo Clinic.
https://www.mayoclinic.org/diseases-conditions/sore-throat/symptoms-causes/syc-20351635

[38] World Health Organization. (2026, March 24). Tuberculosis. WHO Fact
Sheets.
https://www.who.int/news-room/fact-sheets/detail/tuberculosis

[39] Centers for Disease Control and Prevention. (2025, January 17). Signs and
symptoms of tuberculosis. CDC.
https://www.cdc.gov/tb/signs-symptoms/index.html

[40] Mayo Clinic Staff. (2023, August 29). Acute sinusitis — Symptoms and
causes. Mayo Clinic.
https://www.mayoclinic.org/diseases-conditions/acute-sinusitis/symptoms-causes/syc-20351671

[41] Mayo Clinic Staff. (2019, April 9). Chronic daily headaches — Symptoms
and causes. Mayo Clinic.
https://www.mayoclinic.org/diseases-conditions/chronic-daily-headaches/symptoms-causes/syc-20370891

[42] World Health Organization. (2025, October 24). Migraine and other headache
disorders. WHO Fact Sheets.
https://www.who.int/news-room/fact-sheets/detail/headache-disorders
```

---

## CITATION MAPPING — How to cite each threshold in the table/text

When the thesis mentions the Duration Safeguard Matrix or individual thresholds, use these in-text citations:

| Symptom | Threshold | Sources to Cite |
|---|---|---|
| **Fever > 3 days** | Dengue symptoms typically last 2–7 days; severe dengue warning signs appear within 24–48 hours after fever subsides (WHO). CDC: fever lasting beyond a few days warrants medical attention in dengue-endemic areas. | [33, 34] |
| **Diarrhea > 2 days** | Mayo Clinic: "See your doctor if your diarrhea doesn't get better or stop after two days." WHO: persistent diarrhea defined as lasting 14+ days; acute cases lasting several days signal dehydration risk. | [35, 36] |
| **Sore Throat > 5 days** | Mayo Clinic (citing American Academy of Otolaryngology): "A bad sore throat that lasts longer than a week" requires medical attention. System uses conservative 5-day threshold given streptococcal/rheumatic fever risk. | [37] |
| **Cough > 14 days** | CDC: "A bad cough that lasts 3 weeks or longer" is a common TB symptom. WHO: "prolonged cough (sometimes with blood)" is a key TB indicator. Philippines is 3rd highest TB burden country globally (6.8% of global total in 2024). System uses 14-day threshold per DOH community screening protocols. | [38, 39] |
| **Nasal Congestion / Runny Nose > 10 days** | Mayo Clinic: acute sinusitis "usually clears up within a week to 10 days unless there's also a bacterial infection." Symptoms lasting "more than a week" should trigger medical visit. | [40] |
| **Headache > 7 days** | Mayo Clinic: "two or more headaches a week" or taking pain relievers "most days" warrants medical attention. WHO: medication-overuse headache is the most common secondary headache disorder. | [41, 42] |
| **Stomach Ache / Body Aches / Rashes / Allergic Rhinitis > 7 days** | Conservative threshold based on OTC package insert warnings (typically 7-day maximum recommended usage without medical consultation) and general clinical practice that persistent symptoms beyond one week suggest an underlying condition requiring professional evaluation. | [General OTC practice — no single citation needed; the 7-day limit is standard on OTC package inserts in the Philippines] |

---

## HOW TO WEAVE CITATIONS INTO THE THESIS TEXT

In **Update 8** (the Duration Safeguard Matrix paragraph), revise the first sentence to include citations:

**Original (from Update 8):**
> The duration thresholds were derived from Philippine Department of Health clinical guidelines, standard OTC package insert warnings, and published infectious disease surveillance protocols relevant to the Philippine setting.

**Revised with citations:**
> The duration thresholds were derived from clinical guidelines published by the World Health Organization [33, 36, 38, 42], the United States Centers for Disease Control and Prevention [34, 39], the Mayo Clinic clinical reference database [35, 37, 40, 41], and standard OTC package insert warnings used in Philippine pharmacies. The 14-day cough threshold aligns with the DOH community-level TB screening protocol, given that the Philippines ranks among the top three countries in global TB burden [38]. The 3-day fever threshold accounts for the dengue-endemic status of the country, where dengue warning signs typically emerge within 24–48 hours after fever resolution [33, 34]. The 2-day diarrhea threshold follows established clinical advice that adult diarrhea lasting beyond 48 hours warrants medical evaluation due to dehydration risk and the possibility of bacterial or parasitic infection [35, 36].

---

## SUMMARY OF ALL CHANGES

| # | Location | What Changes |
|---|----------|-------------|
| 1 | Introduction, OLDCARTS paragraph | "4 components" → "5 components" (add Duration), add time-based safety mention |
| 2 | Objective 1 | Add duration-based safety check to the objective |
| 3 | Methods, Iteration 1 Design | Add duration screening to safety requirements |
| 4 | Methods, Iteration 1 Implementation | Expand OLDCARTS paragraph with duration safeguard details |
| 5 | Conceptual Framework, Stage 5 | Add duration screening step before recommendation engine |
| 6 | System Architecture, traceability | Fix grammar: "safety critical" → "safety" |
| 7 | OLDCARTS Clarification Layer heading + text | Rename to include Duration, add full duration description |
| 8 | NEW TABLE after Update 7 | Insert Duration Safeguard Matrix table with 11 rows |
| 9 | OLDCARTS Sample Implementation | Add duration follow-up example after clarification scenarios |
| 10 | Design constraints paragraph | Distinguish clarification constraints from duration (always asked) |
| 11 | Recommendation Logic Step 5 | Add (d) duration screening to safety checks list |
| 12 | Benchmark Design | Add Tier 5: Duration Safeguard (31 tests) |
| 13 | Iteration 1 Testing | Add duration safeguard validation details |
| 14 | Iteration 1 Review | Add 74 regression tests (including 31 duration) passing |
| 15 | Iteration 3 Implementation | Add duration threshold refinement to planned improvements |
| 16 | Why Not LLM, Point 1 | Add "duration-based referral thresholds" to safety rules list |
| 17 | Error-Driven Iterative Refinement | Add duration safeguard test development note |
