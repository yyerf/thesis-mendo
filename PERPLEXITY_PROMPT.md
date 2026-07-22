    # PROMPT FOR PERPLEXITY — FIX MY THESIS METHODOLOGY CHAPTER

    Copy-paste everything below this line to Perplexity:

    ---

    ## TASK

    I need you to rewrite/fix my thesis **Materials & Methods chapter** for my undergraduate CS thesis. My current methodology chapter has factual errors — it describes things the system does NOT actually do. I'm giving you:

    1. **My current methodology text** (with errors marked)
    2. **The FULL actual system data** (verified from source code)

    Please rewrite the complete methodology chapter to accurately reflect what the system actually does. Keep the academic tone, APA format, and structure of a CS thesis. Keep relevant citations. Remove all false claims.

    ---

    ## MY THESIS INFO

    - **Title:** MendoVendo v3.0: An AI-Enabled Multilingual OTC Medicine Recommendation System for Philippine Pharmacies  
    - **Degree:** Bachelor of Science in Computer Science
    - **Methodology Type:** Design Science Research (DSR)
    - **System Type:** Hybrid NLP pipeline for symptom extraction and OTC medicine recommendation
    - **Target Deployment:** Raspberry Pi 5-based physical dispensing kiosk

    ---

    ## ERRORS IN MY CURRENT METHODOLOGY (MUST FIX)

    ### Error 1: Wrong symptom count
    - ❌ CURRENT: "15 clinically meaningful symptom labels" including NAUSEA, VOMITING, DIZZINESS, FATIGUE
    - ✅ CORRECT: **13 symptom labels**: HEADACHE, FEVER, COUGH_DRY, COUGH_PRODUCTIVE, COUGH_GENERAL, RUNNY_NOSE, NASAL_CONGESTION, SORE_THROAT, STOMACH_ACHE, DIARRHEA, BODY_ACHES, ALLERGIC_RHINITIS, RASHES. No NAUSEA, VOMITING, DIZZINESS, or FATIGUE.

    ### Error 2: Fine-tuning never happened
    - ❌ CURRENT: Claims fine-tuning of MiniLM with CosineSimilarityLoss on 252 sentence pairs, batch size 16, 4 epochs, etc.
    - ✅ CORRECT: **NO fine-tuning was performed.** The model (`paraphrase-multilingual-MiniLM-L12-v2`, ~33M parameters) is used in **pre-trained inference-only mode**. No training loop exists in the codebase. This was a deliberate design choice for reproducibility and safety (no risk of overfitting to a small corpus).

    ### Error 3: 1,039-entry corpus doesn't exist
    - ❌ CURRENT: Claims a "1,039-entry corpus" annotated by a licensed pharmacist via web tool at mendo.diapana.dev
    - ✅ CORRECT: The pharmacist annotation was planned but **not completed** within the project timeline. The project adopted the **ASG (Authoritative-Source-Grounded) framework** instead — sourcing medicine data from package inserts, MIMS Philippines, and DOH Philippines. The dictionary has ~260+ phrases (not 1,039), and the test benchmark has 288 cases.

    ### Error 4: Wrong phrase count
    - ❌ CURRENT: "522 curated phrases across 15 symptom labels"
    - ✅ CORRECT: **~260+ curated multilingual phrases across 13 symptom labels** (Tagalog, Bisaya/Cebuano, English, Taglish/Conyo, Jejemon/Leetspeak)

    ### Error 5: Wrong drug count
    - ❌ CURRENT: "26 OTC drugs" and "knowledge graph for 26 drugs"
    - ✅ CORRECT: **23 medicine entries (18 unique brands)** in a **structured JSON dataset** (not a knowledge graph — no graph database, no nodes/edges)

    ### Error 6: Wrong evaluation corpus
    - ❌ CURRENT: "threshold sweep (0.40 to 0.85) on a 2,170-entry symptom evaluation corpus"
    - ✅ CORRECT: Threshold is **fixed at 0.65** (determined empirically). No 2,170-entry corpus exists. The evaluation benchmark is **288 structured test cases** across 59 categories in 4 tiers, plus 9 semantic stress cases and 80 real-user simulation cases.

    ### Error 7: Not a knowledge graph
    - ❌ CURRENT: "knowledge graph" mentioned repeatedly
    - ✅ CORRECT: It's a **structured JSON dataset with 16 fields per medicine entry**, including 7 ASG fields. Call it a "structured medicine dataset" or "rule-based lookup table."
    in pro
    ### Error 8: Pipeline is 5 stages, not 4
    - ❌ CURRENT: "four-stage cascaded pipeline"
    - ✅ CORRECT: **5-stage pipeline**: (0) Triage/Red-Flag Safety → (1) Dictionary-Based Extraction → (2) Semantic Fallback → (3) Hybrid Merge + Lexical Guards + Safety Filters → (4) ASG Recommendation Engine

    ### Error 9: Iteration 2 is wrong
    - ❌ CURRENT: Iteration 2 describes expert annotation, fine-tuning, and threshold optimization
    - ✅ CORRECT: Iteration 2 should describe: **dictionary expansion to ~260+ phrases, negation handling implementation (11 negation words, window-based detection, consumed negation), fuzzy rescue development (7 families with exclusion sets), contrastive boundary logic (pero/but/kaso splitting), benchmark creation (288 test cases across 59 categories)**

    ---

    ## THE FULL ACTUAL SYSTEM (VERIFIED FROM SOURCE CODE)

    ### Architecture Overview
    A 5-stage cascaded hybrid NLP pipeline running on Flask (Python 3.12.3), deployed on a Raspberry Pi 5-based kiosk with Arduino Mega for dispensing hardware.

    ### Stage 0: Triage / Red-Flag Safety Layer (file: step3_hybrid.py)
    8 emergency categories with multilingual regex: chest_pain, difficulty_breathing, blood_in_stool, blood_vomit, severe_allergic_reaction, high_fever_prolonged (≥40°C), seizure, loss_of_consciousness. Uses LIGHT normalization (lowercase + whitespace only, preserves digits for temperature values). If triggered, Stage 4 suppresses OTC recommendations and advises "CONSULT A DOCTOR."

    ### Stage 1: Dictionary-Based Extraction (file: step1.py, 1,229 lines)
    - **Symptom Dictionary:** ~260+ multilingual phrases across 13 labels (Tagalog, Bisaya/Cebuano, English, Taglish, Jejemon)
    - **Normalization:** Leetspeak conversion (`@→a, 0→o, 1→i, 3→e, 4→a, 5→s, 7→t, 8→b, $→s, !→i, |→i`), lowercase, whitespace collapse
    - **Phrase matching:** Word-boundary regex for single words, substring for multi-word phrases
    - **Negation handling:** 11 negation words (hindi, walang, walay, dili, no, not, without, etc.), 0-2 word window, consumed negation (28 intervening symptom words), negated-label tracking
    - **Contrastive boundary splitting:** Splits on `pero|but|kaso|however|though`, evaluates negation per segment independently
    - **Cough-type qualification:** 7-step decision tree (itchy throat → COUGH_DRY, chest-rattle → COUGH_PRODUCTIVE, etc.), plema-filler exemption, explicit DRY beats WET priority
    - **Headache heuristic:** head_word + pain_word within ≤5 tokens
    - **Sore throat proximity:** throat_word + pain_word within ≤5 tokens with dual negation
    - **Per-cue-group nasal inference:** 3 independent groups (allergy, runny, congestion) with independent negation
    - **Allergen-trigger heuristic:** RASHES + allergen word → also ALLERGIC_RHINITIS
    - **Fuzzy rescue:** 7 Levenshtein families with exclusion sets (e.g., "tubo"≠"ubo"), max distance 1-2, checked against negated_labels
    - **Strong negation overrides:** Contrastive-boundary-aware for FEVER, COUGH, HEADACHE, RUNNY_NOSE, BODY_ACHES

    ### Stage 2: Semantic Fallback (file: step2.py, 321 lines)
    - **Model:** `paraphrase-multilingual-MiniLM-L12-v2` (~33M params, 384-dim embeddings)
    - **Usage:** Pre-trained inference ONLY — no fine-tuning
    - **~130 anchor sentences** (8-12 per label) pre-encoded at initialization
    - **Cosine similarity threshold:** 0.65 (fixed)
    - **Precision-first switching:** ONLY activates when Stage 1 returns zero symptoms (dictionary results always trusted)
    - **Device:** CPU by default (configurable via env var)

    ### Stage 3: Hybrid Merge + Lexical Guards + Safety (file: step3_hybrid.py, 932 lines)
    - **11 keyword gates** per symptom label (semantic detection must be grounded in original text keywords)
    - **7 explicit negation functions** (fever, headache, cough, diarrhea, sore_throat, nasal, allergy)
    - **Centralized safety filter:** Applies all negation checks + red-flag suppression (blood_in_stool → suppress DIARRHEA, severe_allergic → suppress SORE_THROAT)
    - **Top-N selection:** Score-ranked, returns best 2 semantic symptoms

    ### Stage 4: ASG Recommendation Engine (file: step4_recommend.py, 398 lines)
    - **Medicine dataset:** 23 entries × 16 fields (8 original + 7 ASG from Package Insert / MIMS Philippines / DOH Philippines)
    - **Triage gate:** Red flags → suppress all OTC, return "CONSULT A DOCTOR"
    - **COUGH_GENERAL handling:** Sole symptom → ask clarification; with others → defer cough
    - **Rule-based symptom→medicine matching** with score ranking
    - **Brand merging** (keep highest score, combine reasons)
    - **Safety checks:** Paracetamol overlap detection, opposing mechanism warning (expectorant + suppressant)

    ### 23 OTC Medicines in Dataset
    Bioflu, Neozep (2 variants), Decolgen (2 variants), Symdex-D (2 forms), Tuseran Forte, Ascof Forte, Solmux (2 forms), Robitussin, Sinecod Forte, Biogesic (2 forms), Advil (2 forms), Cetirizine (2 forms), Loperamide/Diatabs, Erceflora, Kremil-S, Buscopan.

    ### Benchmark & Evaluation
    - **288-case structured benchmark** (59 categories, 4 tiers): 288/288 exact match (F1 = 1.000)
    - **9-case semantic stress set**: 9/9 exact match
    - **80-case real-user simulation**: 72 exact + 8 partial + 0 failed
    - **Combined:** 369/377 exact (97.9%), 0 failures
    - **4-tier testing:** Functional (100) → Robustness (100) → Adversarial (64) → Safety (24)
    - **Metrics:** Exact match, partial match, F1 score per test
    - **19 bugs discovered and fixed** through adversarial probing
    - **External AI audit** (Gemini 2.5 Pro): 6/7 suggestions already implemented

    ### Languages
    Tagalog (primary), Bisaya/Cebuano (primary), English (full), Taglish/Conyo code-switch (full), Jejemon/Leetspeak (full)

    ### Key Innovations
    1. Contrastive boundary negation (pero/but/kaso)
    2. Fuzzy rescue with false-positive exclusion sets
    3. COUGH_GENERAL defer strategy
    4. ASG (Authoritative-Source-Grounded) framework for medicine data
    5. Paracetamol overlap detection
    6. Universal negation with negated-label tracking
    7. Per-cue-group nasal inference
    8. Precision-first switching (dictionary → semantic)
    9. Chest-rattle bypass (COUGH_PRODUCTIVE without "cough" word)
    10. Allergen-trigger heuristic (RASHES + allergen → ALLERGIC_RHINITIS)
    11. Red-flag triage layer with multilingual regex
    12. Centralized semantic safety filters
    13. Adversarial testing methodology (64 targeted edge cases)

    ---

    ## WHAT TO KEEP FROM CURRENT METHODOLOGY

    - Research Design section (DSR with 3 iterations) — but fix Iteration 2 content
    - Research Philosophy section — keep
    - Theoretical Framework (Rule-Based NLP, Distributional Semantics, Knowledge-Based Expert Systems) — keep but update details
    - Conceptual Framework — keep but align with 5-stage (not 4-stage) pipeline
    - Academic references [1]–[10] — keep
    - General structure and APA formatting — keep

    ## WHAT TO ADD (MISSING FROM CURRENT)

    - Triage/red-flag safety layer description
    - Negation handling details (window, consumed negation, contrastive boundary)
    - Fuzzy rescue methodology
    - Lexical guard mechanism
    - Centralized safety filter
    - ASG framework explanation (why pharmacist annotation was replaced)
    - Actual benchmark methodology (288 cases, 4 tiers, 59 categories)
    - Evaluation metrics and results
    - Bug-driven iterative refinement (19 bugs)
    - Language support details

    ---

    Please rewrite my complete Materials & Methods chapter incorporating all of the above corrections and additions. Maintain academic CS thesis tone, APA formatting, and proper citation style. The chapter should be thorough enough for a thesis defense.
