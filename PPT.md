# MendoVendo v3.0 — Presentation Guide & Defense Preparation

---

## PART 1: DEFENSE READINESS ANALYSIS

### What's Strong (Defense-Ready)
- **Introduction & Problem Statement** — Well-grounded: 92.6% self-medication stat, v1/v2 precision-safety gap (78.08% precision), adversarial challenge set proving v2 fails (Table 1 & 2). Panel will appreciate the concrete failure examples.
- **Literature Review** — 6 studies covering hybrid architectures, multi-symptom decomposition, knowledge graphs. Good positioning against Ada Health, Babylon Health, Isabel Healthcare.
- **System Architecture** — Very detailed 5-stage pipeline. Duration Safeguard with WHO/CDC/Mayo Clinic references [33]-[42]. OLDCARTS well-applied.
- **Comparative Benchmarking** — Honest: acknowledges transformer data-scarcity caveat, doesn't overclaim. 81.2% vs 55.9% (SVM) vs 22.6% (XLM-RoBERTa).
- **"Why Not LLM?"** section — Panel-killer. 6 strong reasons. Will save you from the "why not just use ChatGPT?" question.
- **Error-Driven Iterative Refinement** — 19 issues found and fixed. Gemini 2.5 Pro supplementary check adds credibility.
- **References** — 42 refs, all 2023-2026 range. Solid.

### Potential Gaps / Things Panel Might Flag

1. **Testing section doesn't mention the 74 regression tests** — The PDF says "structured benchmark cases, regression checks, and scenario-based safety validation" but never mentions the exact count of 74 regression tests (43 original + 31 duration). Add "74 regression tests — including 31 dedicated to the duration safeguard — all passed" to the Testing paragraph.

2. **Iteration 2 & 3 are entirely future work** — The paper is honest about this, but panelists may push: "So you only completed Iteration 1?" Be ready to explain that Iteration 1 is a fully functional, tested artifact — not a prototype — and that Iterations 2-3 are validation/deployment phases requiring ethical clearance.

3. **No real-user data yet** — The 80-case "real-user simulation" was researcher-constructed, not from actual pharmacy users. Panel will catch this. Defense: "This is why Iteration 2 exists — controlled field deployment to collect real data. The simulation was designed to stress-test the pipeline before exposing it to real users."

4. **Dataset size is small** — 288 benchmark cases, 331 dictionary phrases, 24 medicines. Panel may ask if this is enough. Defense: This is a bounded problem (13 symptoms, 24 medicines) — not open-ended. The dictionary covers the actual language people use in Davao pharmacies. Iteration 2 will expand from real consultation data.

5. **No pharmacist validation yet** — The ASG framework is a workaround. "Pharmacist review remains part of Iteration 2." Be transparent about this.

6. **The "gi ubo ko" scenario is now in the paper but the diarrhea scenario appears to have been removed** — Your OLDCARTS Sample Implementation only shows the cough scenario. If the diarrhea example was in an earlier draft, make sure it's still there or be ready to walk through it verbally.

---

## PART 2: SYSTEM ARCHITECTURE SLIDES — WHAT TO PUT & WHAT TO SAY

---

### SLIDE: System Architecture Overview

**Put on slide:**
```
MendoVendo v3.0 — 5-Stage Hybrid Pipeline

User Input (Bisaya/Tagalog/English)
         │
    ┌────▼────┐
    │ Stage 0 │  Triage / Red-Flag Safety Layer
    └────┬────┘
         │ (pass if no emergency)
    ┌────▼────┐
    │ Stage 1 │  Dictionary-Based Symptom Extraction
    └────┬────┘  331 phrases × 13 labels × 5 languages
         │
    ┌────▼────┐
    │ Stage 2 │  Semantic Embedding Fallback
    └────┬────┘  MiniLM-L12-v2 (33M params, 384-dim)
         │      only activates if Stage 1 finds nothing
    ┌────▼────┐
    │ Stage 3 │  Hybrid Merge + Lexical Guards + Safety Filters
    └────┬────┘  Negation, red-flag suppression, cough-type tree
         │
    ┌────▼────┐
    │ Stage 4 │  OLDCARTS Clarification + Duration + Recommendation
    └─────────┘  24 medicines, ASG dataset, age/safety filtering
```

**What to say:**
> "MendoVendo v3.0 uses a five-stage pipeline that separates symptom detection from recommendation. This is the key design shift from v2 — instead of directly matching text to drugs, we first figure out what the user's symptoms are, then we decide what medicine is appropriate under safety constraints. Each stage is modular and independently testable. The pipeline processes multilingual input — Bisaya, Tagalog, English, code-switching, even Jejemon — and applies safety checks at every level."

---

### SLIDE: Stage 0 — Triage / Red-Flag Safety Layer

**Put on slide:**
```
Stage 0: Red-Flag Triage
━━━━━━━━━━━━━━━━━━━━━━

Method: Proximity-Based Co-occurrence + Exclusion Tokens

┌───────────────────┬─────────────────────────┬───────────────────┐
│ Red Flag          │ Trigger Pattern         │ Exclusion Tokens  │
├───────────────────┼─────────────────────────┼───────────────────┤
│ GI Hemorrhage     │ [blood] + [stool/vomit] │ —                 │
│ Cardiac Emergency │ [pain] + [chest]        │ cough, plema, ubo │
│ Respiratory       │ [difficulty] + [breath] │ —                 │
│ Dengue Warning    │ [fever] + [rashes]      │ bite, allergy     │
│ Stroke            │ [numb] + [face/half]    │ tooth, ngipin     │
│ Severe Dehydration│ [diarrhea] + [no urine] │ —                 │
│ Pregnancy Block   │ [buntis/pregnant]       │ asawa, sister     │
│ Hyperthermia      │ [fever] + [40-42°C]     │ kilo, years old   │
│ Direct Emergency  │ seizure / fainted       │ —                 │
└───────────────────┴─────────────────────────┴───────────────────┘

→ If triggered: BLOCK all OTC. "Consult a licensed medical expert."
→ If not triggered: proceed to Stage 1.
```

**What to say:**
> "Before anything else, Stage 0 screens for emergencies. It uses co-occurrence detection — it looks for specific word combinations within a lexical window. For example, 'blood' near 'stool' triggers GI hemorrhage. But the critical design here is the exclusion tokens. Without them, someone saying 'masakit dibdib ko dahil sa ubo' — chest hurting from coughing — would get flagged as a cardiac emergency and blocked from getting cough medicine. The exclusion tokens prevent that false alarm. Same with 'high blood pressure' — the word 'blood' alone won't trigger GI bleeding because the pattern requires a stool or vomit word nearby."

**They might ask:**
- **Q: "What if someone has a real chest pain emergency but also mentions coughing?"**
  > A: "The exclusion tokens only suppress the cardiac flag when cough-related words are the ONLY context around 'chest pain.' If someone says 'masakit ang dibdib ko, nahihirapan huminga' — chest pain with difficulty breathing — the respiratory emergency flag triggers independently, and the system still blocks OTC. The exclusion is narrow, not blanket."

- **Q: "How did you decide on these red-flag categories?"**
  > A: "The nine categories were selected based on WHO emergency triage guidelines and common pharmacy-walk-in scenarios in the Philippine context. We prioritized conditions where giving OTC medicine could mask a serious problem — like fever plus rashes hiding dengue, or diarrhea with no urination indicating severe dehydration."

- **Q: "What about the pregnancy exclusion — 'asawa, sister'? Why exclude those?"**
  > A: "In Filipino pharmacies, people commonly buy medicine for family members. Someone saying 'buntis ang asawa ko, may lagnat siya' — my pregnant wife has a fever — is purchasing for a proxy. The system should recommend fever medicine for the wife, not block the consultation entirely because it detected the word 'pregnant.'"

---

### SLIDE: Stage 1 — Dictionary-Based Symptom Extraction

**Put on slide:**
```
Stage 1: Dictionary Extraction
━━━━━━━━━━━━━━━━━━━━━━━━━━━

331 phrases → 13 symptom labels → 5 language variants

Processing Pipeline:
1. Text Normalization
   - lowercase, leetspeak decode (s@k1t → sakit), whitespace collapse
   
2. Cough-Type Decision Tree (7-step)
   - Dry vs Productive vs General before main scan
   
3. Phrase Matching
   - Multi-word: substring match
   - Single-word: regex word-boundary (\b)
   
4. Negation Handling
   - 11-word negation lexicon (Tag/Bis/Eng)
   - 0-2 word proximity window
   - Consumed negation logic
   - Contrastive boundary splitting (pero, but, kaso)
   
5. Fuzzy Rescue
   - Levenshtein distance for misspellings (7 families)
   - Exclusion sets to prevent false rescues
```

**What to say:**
> "Stage 1 is the workhorse — it handles the vast majority of detections. It's a handcrafted dictionary of 331 phrases covering Tagalog, Bisaya, English, Taglish, and Jejemon. The design is precision-first: we'd rather miss a symptom than detect a wrong one, because a false positive in medicine recommendation is more dangerous than a false negative. Key features: the cough decision tree runs BEFORE the main scan so we can distinguish dry from productive cough early. The negation handler catches 'wala akong lagnat' — I don't have fever — using a proximity window. And the fuzzy rescue recovers typos like 'laganat' for 'lagnat' using Levenshtein distance, but with exclusion sets — 'ubo' has a distance-1 exclusion for 'ulo' so we don't confuse cough with headache."

**They might ask:**
- **Q: "Why not just use the semantic model for everything? Why maintain 331 phrases manually?"**
  > A: "Two reasons. First, the dictionary is deterministic — if I type 'ubo,' I know with 100% certainty it maps to COUGH. No probability, no threshold tuning. That matters for safety-critical recommendations. Second, performance: dictionary lookup is essentially instant. The semantic model takes ~93ms per query. On a Raspberry Pi serving walk-in customers, that difference matters."

- **Q: "How did you build the 331 phrases? Is it comprehensive enough?"**
  > A: "We started from clinical references and MIMS Philippines symptom descriptions, then expanded it through fieldwork — observing how people actually describe symptoms at pharmacies in Davao City. The real-user simulation showed 90% exact match, with the 10% gap coming from severe misspellings and dual cough-type mentions. Iteration 2 will expand the dictionary from actual consultation logs."

- **Q: "How does 'consumed negation' work exactly?"**
  > A: "If someone says 'walang lagnat pero masakit ulo' — no fever but headache — the negation word 'walang' is consumed by the first symptom it negates (lagnat/fever). It doesn't carry over to 'masakit ulo' (headache) after the contrastive boundary 'pero.' Each segment is evaluated independently."

---

### SLIDE: Stage 2 — Semantic Embedding Fallback

**Put on slide:**
```
Stage 2: Semantic Fallback
━━━━━━━━━━━━━━━━━━━━━━━━

Model: paraphrase-multilingual-MiniLM-L12-v2
  - 33M parameters, 384-dim embeddings
  - 50+ languages (incl. Filipino, Cebuano)
  - Inference-only — NO fine-tuning

118 anchor sentences (5-12 per symptom label)
  ↓
  cosine similarity ≥ 0.65 threshold
  ↓
  candidate symptoms

Activation Rule: ONLY when Stage 1 finds ZERO symptoms
  → Precision-first: dictionary results always take priority

Lazy singleton loading — model loads only on first semantic query
  → Saves ~500MB RAM until needed
```

**What to say:**
> "Stage 2 only activates when the dictionary finds nothing. This is a deliberate precision-first design decision. 118 anchor sentences are pre-encoded at startup. When a user's input doesn't match any dictionary phrase — maybe they used a metaphor or a regional expression we didn't anticipate — the system encodes their text and compares it against all anchors using cosine similarity. The 0.65 threshold was empirically tuned: below that, too many false positives. Above that, valid multilingual paraphrases get dropped. The model is used inference-only — no fine-tuning — for three reasons: safety, reproducibility, and because the pre-trained multilingual knowledge already covers Filipino and Cebuano."

**They might ask:**
- **Q: "Why 0.65? How was it determined?"**
  > A: "Empirically, through iterative testing. At 0.40, everything matched — gibberish would score above threshold. At 0.50, false positives dropped but still too many. At 0.60, we had good coverage but some figurative expressions were missed. At 0.65, the balance was right. At 0.70+, valid multilingual paraphrases were being rejected. We plan a formal sensitivity analysis in Iteration 3 with real consultation data."

- **Q: "Why not fine-tune the model to improve Filipino/Bisaya performance?"**
  > A: "Fine-tuning on a small corpus risks overfitting — the model might perform great on our data but degrade on unseen expressions. The pre-trained model already covers 50+ languages including Filipino. And it's a fixed, publicly available artifact, which helps reproducibility. If Iteration 2 yields a large enough dataset, we'll reconsider fine-tuning."

- **Q: "What are the 8 partial matches in the real-user simulation?"**
  > A: "Cases where the dictionary caught the primary symptom but missed a secondary one expressed idiomatically. Because the semantic layer only activates when the dictionary finds NOTHING, it won't augment partial dictionary results. We accepted this trade-off: a missed secondary symptom gives an incomplete recommendation, but a false positive could trigger a contraindicated medicine."

---

### SLIDE: Stage 3 — Hybrid Merge + Lexical Guards + Safety Filters

**Put on slide:**
```
Stage 3: Hybrid Merge & Safety
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Processing Order:
1. Run Stage 0 (triage)     → red_flags
2. Run Stage 1 (dictionary) → dict_symptoms
3. Cough negation override
4. If dict_symptoms found → SKIP semantic (precision-first)
5. If empty → Load semantic model (lazy)
6. Run Stage 2 → raw semantic detections
7. Lexical Guard: 11 keyword gates × 13 labels
   → semantic detection must have keyword in original text
   → prevents "hallucinated" symptoms
8. Centralized Safety Filter:
   → 7 negation functions (regex, word-boundary safe)
   → 2 red-flag suppression rules
9. Score-rank, select top-N (default: 2)
10. Return final symptom set with source attribution
```

**What to say:**
> "Stage 3 is the orchestration layer — it merges results from Stages 0-2 and applies filtering. The most important mechanism here is the lexical guard. The semantic model is good at finding meaning similarity, but it can 'hallucinate' — it might detect DIARRHEA from an input that merely mentions stomach issues. The lexical guard requires that at least one keyword related to that symptom actually appears in the user's text. So if the model says COUGH_PRODUCTIVE but the input has no cough-related word, the detection is silently dropped. This is our defense against the model generating false positives."

**They might ask:**
- **Q: "What if the semantic model correctly identifies a symptom but uses a word your lexical guard doesn't know?"**
  > A: "Each of the 13 symptom labels has a keyword gate with multiple words across Tagalog, Bisaya, and English. For example, the cough gate includes: ubo, cough, inuubo, gi-ubo, nagaubo, nag-ubo. If the user expressed coughing and we can't find ANY of these words, the input likely wasn't about coughing. But this is a known limitation — Iteration 2's real data will help us discover gaps in the keyword gates."

- **Q: "What are the red-flag suppression rules?"**
  > A: "Two specific cases: if blood_in_stool is detected as a red flag, we suppress DIARRHEA as a symptom — because it's an emergency, not treatable with OTC anti-diarrheal. Similarly, a severe_allergic_reaction flag suppresses SORE_THROAT to prevent the system from recommending lozenges for anaphylaxis."

---

### SLIDE: Stage 4 — OLDCARTS + Duration + Recommendation

**Put on slide:**
```
Stage 4: Clarification → Duration → Recommendation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STEP A — OLDCARTS Context Clarification (if needed):
┌─────────────┬──────────────────────────────────────┐
│ Symptom     │ OLDCARTS Component → Question        │
├─────────────┼──────────────────────────────────────┤
│ Cough       │ Character → Dry or with phlegm?      │
│ Diarrhea    │ Onset → Spoiled food trigger?         │
│ Stomach     │ Character → Burning or cramping?      │
│ Runny Nose  │ Char+Aggr+Timing → Allergy/cold/rain?│
│ Headache    │ Onset → Passive hunger/dehydration    │
└─────────────┴──────────────────────────────────────┘
→ Only triggers when symptom is sole + no context clues

STEP B — Duration Safeguard (always):
┌────────────────────┬───────────┬────────────────────────┐
│ Symptom            │ Threshold │ Clinical Basis         │
├────────────────────┼───────────┼────────────────────────┤
│ Fever              │ > 3 days  │ Dengue/typhoid [33,34] │
│ Diarrhea           │ > 2 days  │ Dehydration risk[35,36]│
│ Sore Throat        │ > 5 days  │ Strep infection [37]   │
│ Stomach/Head/Body/ │ > 7 days  │ Various chronic [41,42]│
│   Rash/Allergy     │           │                        │
│ Nasal/Runny Nose   │ > 10 days │ Bacterial sinusitis[40]│
│ Cough (all types)  │ > 14 days │ TB screening [38,39]   │
└────────────────────┴───────────┴────────────────────────┘
→ Exceeds threshold: BLOCK OTC, refer to doctor
→ Within threshold: proceed to recommendation

STEP C — ASG Recommendation Engine:
24 medicines, 19 brands, 15 fields per entry
Safety: paracetamol overlap, opposing mechanisms, age filter
```

**What to say:**
> "Stage 4 is where OLDCARTS comes in. It has three steps. First, if the symptom is ambiguous — like a general cough with no context about dry or wet — the system asks one clarification question. This maps to the Character, Onset, or Aggravating components of OLDCARTS. Second, the Duration Safeguard. For EVERY detected symptom, the system asks how long it's lasted using bilingual buttons. If it exceeds the threshold — for example, cough for more than 14 days — OTC is blocked and the user is told to see a doctor. The 14-day cough threshold specifically aligns with the DOH TB screening protocol — the Philippines is top 3 globally in TB burden. Third, the recommendation engine matches symptoms to our 24-medicine ASG dataset with age filtering, paracetamol overlap detection, and opposing mechanism warnings."

**They might ask:**
- **Q: "Who validated the duration thresholds? Are they evidence-based?"**
  > A: "All thresholds are sourced from WHO, CDC, and Mayo Clinic clinical guidelines — references [33] through [42] in the paper. The 3-day fever threshold accounts for the Philippines being a dengue-endemic country. The 14-day cough threshold follows the DOH community-level TB screening protocol. The 2-day diarrhea threshold follows WHO guidelines on adult diarrhea persistence. These aren't arbitrary numbers."

- **Q: "What if a user lies about their duration to get medicine?"**
  > A: "The system relies on self-reported duration, same as a pharmacist asking 'how long have you had this?' We can't verify the answer, but we can make the question clear and simple. The bilingual buttons reduce ambiguity. Also, the system is a support tool, not a replacement for the pharmacist — the pharmacist is still present and can intervene."

- **Q: "What is the ASG framework? Why not have a pharmacist build the dataset?"**
  > A: "ASG — Authoritative Source Grounded — means every piece of data comes from package inserts, MIMS Philippines, or DOH guidelines. We adopted this after the planned pharmacist annotation couldn't be completed within the project timeline. The advantage is reproducibility — anyone can verify our data against the published sources. Pharmacist review is planned for Iteration 2."

- **Q: "Only 24 medicines — isn't that too limited?"**
  > A: "24 entries covering 19 brands represents the most common OTC medicines actually available in Philippine pharmacies for our 13 symptom scope. We intentionally kept it bounded because safety is the priority — every medicine entry has verified contraindications, warnings, drug interactions, and age restrictions. Expanding the dataset without proper safety verification would defeat the purpose."

- **Q: "What happens when multiple symptoms are detected?"**
  > A: "The system generates complementary recommendations — a fever+cough input can yield both Biogesic for fever and Sinecod for cough, with paracetamol overlap detection warning if both contain paracetamol. Duration is checked per symptom sequentially with a progress indicator ('Symptom 1 of 3'). If even one symptom exceeds its threshold, that symptom's recommendations are blocked while others proceed normally."

---

### SLIDE: Live Demo Flow — "gi ubo ko"

**Put on slide:**
```
DEMO: "gi ubo ko" (Cebuano: "I'm coughing")

Input: "gi ubo ko"
  ↓
Stage 0: No red flags ✓
  ↓
Stage 1: Dictionary matches "ubo" → COUGH_GENERAL
  ↓
Stage 3: No negation, pass through
  ↓
Stage 4A: Sole symptom, no context clues
  → OLDCARTS Character: "Dry or with phlegm?"
  → User picks: "Dry cough" → COUGH_DRY
  ↓
Stage 4B: Duration check
  → "Gaano na katagal ang tuyong ubo?"
  → Buttons: <1 day | 1-7 days | 8-14 days | >2 weeks
  → User picks: "1-7 days" → 4 days → SAFE (≤14)
  ↓
Stage 4C: Recommendation
  → Tuseran Forte (Dextromethorphan)
  → Sinecod Forte (Butamirate citrate)
  ✓ No expectorants (dry cough = suppressant only)
```

**What to say:**
> "Let me walk you through an actual scenario. A Bisaya-speaking user types 'gi ubo ko' — 'I'm coughing' in Cebuano. Stage 0 checks for emergencies — none found. Stage 1 dictionary matches 'ubo' to COUGH_GENERAL. Since it's the only symptom and there's no dry/wet context, Stage 4 triggers the Character clarification: 'Is your cough dry or with phlegm?' The user selects dry cough. Now the system asks how long — less than a day, 1-7 days, 8-14 days, or more than 2 weeks. If they pick '1-7 days,' that's 4 days — within the 14-day threshold, so it's safe. The system recommends Tuseran Forte and Sinecod Forte — both are cough suppressants. It does NOT recommend Solmux or any expectorant, because giving an expectorant for a dry cough serves no therapeutic purpose."

---

### SLIDE: Evaluation Results

**Put on slide:**
```
Evaluation Summary
━━━━━━━━━━━━━━━━━━

                        Exact Match    Partial    Failed
288-case structured     288/288 (100%)    0         0
9-case semantic stress    9/9  (100%)     0         0
80-case real-user sim    72/80  (90%)     8         0
                        ─────────────────────────────
COMBINED (377 total)    369/377 (97.9%)   8         0
                        ZERO OUTRIGHT FAILURES

74 Regression Tests: 74/74 PASSED
  - 43 core pipeline tests
  - 31 duration safeguard tests

Comparative Benchmark (288 cases):
  Mendo Hybrid    81.2% exact | F1: 0.852
  SVM (TF-IDF)    55.9% exact | F1: 0.731
  mBERT           38.2% exact | F1: 0.550
  XLM-RoBERTa     22.6% exact | F1: 0.033
```

**What to say:**
> "Three evaluation sets, 377 total cases, zero outright failures. The structured benchmark hit 100% exact match — but we're transparent that this was researcher-constructed and may carry implicit bias. The real-user simulation at 90% is the more realistic indicator. The 8 partial matches came from severely misspelled body-part words and dual cough-type mentions — both are on the fix list for Iteration 3. Against five baseline models including fine-tuned XLM-RoBERTa and mBERT, our hybrid pipeline led by over 25 percentage points. But we're upfront: the transformer scores reflect data scarcity, not architectural inferiority. With 230 training samples across 8,192 possible label combinations, no transformer can learn meaningful patterns."

**They might ask:**
- **Q: "The benchmark was built by the same team that built the system. Isn't that biased?"**
  > A: "Yes, there's a risk of implicit bias, and we explicitly say so in the paper. That's exactly why we built the 80-case real-user simulation with realistic misspellings and rambling input that stress-tests the boundaries. The 10% gap between 100% and 90% shows where researcher familiarity ends and real-world messiness begins. Iteration 2 will use actual pharmacy consultation logs for validation."

- **Q: "Why did XLM-RoBERTa score so low?"**
  > A: "Data scarcity. 230 training samples per fold across 13 labels means 2^13 = 8,192 possible label combinations — far too few for a 278M-parameter transformer. It learned to predict almost nothing (recall: 0.017) rather than risk errors. This isn't a flaw in transformers — it's the wrong tool for a small-data problem."

---

### SLIDE: Multilingual Support

**Put on slide:**
```
5 Language Variants Supported
━━━━━━━━━━━━━━━━━━━━━━━━━━━

Tagalog    "masakit ang ulo ko at nilalagnat"
Bisaya     "labad akong ulo, garas akong tilaok"
English    "I have a headache and fever"
Taglish    "masakit head ko, may cough ako"
Jejemon    "s@k1t ul0", "lgnat ako"

How it works:
- Tagalog/Bisaya: 331 dictionary phrases + 118 semantic anchors
- Taglish: dictionary + cross-lingual embedding similarity
- Jejemon: normalization layer (@ → a, 0 → o, 1 → i, 3 → e)
```

**What to say:**
> "Mendo handles five language variants. Tagalog and Bisaya get primary support through the dictionary and semantic anchors. Taglish code-switching — mixing Filipino and English mid-sentence — works through combined dictionary and cross-lingual embeddings. Jejemon is handled at the normalization layer, converting leetspeak characters before matching. This matters because in Davao City pharmacies, people don't speak one language — they mix all of these."

---

## PART 3: GENERAL DEFENSE QUESTIONS TO PREPARE FOR

**Q: "What's new in v3 compared to v2?"**
> "Three fundamental changes. First, we separated symptom detection from recommendation — v2 matched text directly to drugs. Second, we added safety layers that v2 completely lacked: red-flag triage, negation handling, contraindication checks, age filtering, duration safeguards. Third, we added semantic understanding for inputs the dictionary can't handle. The result: v2 had 78% precision — roughly 1 in 5 recommendations could be wrong. V3 has zero outright failures across 377 test cases."

**Q: "Why not use a cloud API or online model?"**
> "Five reasons: (1) pharmacy kiosks have unreliable internet — the system can't go down every time wifi drops; (2) cloud APIs charge per token — hundreds of daily consultations add up; (3) sending patient symptom data to external servers creates privacy issues under RA 10173; (4) a Raspberry Pi 5 with 8GB RAM can't run even small LLMs locally; (5) our 33M-parameter MiniLM model fits in under 500MB and runs in 93ms on CPU."

**Q: "What are the ethical considerations?"**
> "The system is a decision-support tool, not a replacement for the pharmacist. It has hard-coded safety limits: red-flag emergencies are blocked, durations exceeding safe thresholds are blocked, contraindicated medicines are excluded. The pharmacist is always present and can override. For Iteration 2, we need ethical clearance from the institutional review body before any real-user consultation is recorded. Privacy measures include minimizing bystander exposure and limiting log access to authorized researchers."

**Q: "What are the limitations?"**
> "Main limitations: (1) 13 symptom labels — doesn't cover all possible complaints; (2) 24 medicines — only common OTC drugs in PH pharmacies; (3) no real-user validation yet — Iteration 2; (4) no pharmacist annotation yet — ASG framework as interim; (5) dictionary may miss very creative misspellings or rare dialectal expressions; (6) precision-first design means some secondary symptoms in multi-symptom inputs get missed (the 8 partial matches)."

**Q: "How does the system handle if someone enters something completely unrelated, like 'hello' or 'I want to buy shampoo'?"**
> "The system returns a clear 'no symptom detected' message with three suggestions: rephrase with specific symptom words, try a different language, or consult the pharmacist directly. It never guesses. Gibberish input is also handled — the semantic threshold at 0.65 filters out non-symptom text, and the lexical guards prevent hallucinated detections."

**Q: "How scalable is this? Can it work for more symptoms or medicines?"**
> "The architecture is modular. Adding a new symptom means: (1) adding phrases to the dictionary, (2) adding anchor sentences for the semantic layer, (3) adding keyword gates in the lexical guard, (4) adding duration thresholds, and (5) adding medicine entries to the ASG dataset. Each step is independent. But every addition must be safety-verified — we can't just bulk-add medicines without checking contraindications and interactions."

**Q: "Your paper mentions Gemini 2.5 Pro was used for supplementary review. Doesn't that undermine the research?"**
> "No — it was used as a supplementary probe to check for blind spots AFTER the iterative testing was complete. It found 7 potential issues, 6 of which had already been fixed. It wasn't used to build the system, generate code, or create test cases. The benchmark and regression tests are the primary basis for evaluating correctness."
