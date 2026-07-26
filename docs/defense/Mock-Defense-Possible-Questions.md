# Mock Defense — Possible Panel Questions & Answers
## MENDOv3: An Improved AI-Enabled Medicine Recommender for an OTC Drug Dispenser

---

### ARCHITECTURE & DESIGN

**1. Why did you choose a five-stage pipeline instead of a simpler end-to-end model?**

We separated the task into distinct stages because each one does something different and needs different guarantees. The triage layer has to be 100% deterministic — we cannot let a probabilistic model decide whether chest pain is an emergency. The dictionary layer gives us speed and traceability. The semantic layer handles paraphrases the dictionary cannot anticipate. Splitting them means we can test, debug, and explain each stage independently. An end-to-end model would be a black box, which is not acceptable when the output is a medicine recommendation.

**2. Why use dictionary matching first instead of going straight to the transformer model?**

The dictionary is faster, fully deterministic, and covers the most common symptom expressions. On a Raspberry Pi 5 with no GPU, loading the transformer model takes time and uses memory. By running the dictionary first and only falling back to the semantic model when it returns nothing, we avoid unnecessary computation for straightforward inputs. In our benchmark, the vast majority of inputs — including misspelled, Jejemon, and code-switched ones — are already caught by the dictionary, so the semantic model rarely needs to activate.

**3. Why not fine-tune the MiniLM model on your domain data?**

Three reasons. First, safety — fine-tuning on a small corpus risks overfitting, which means the model might perform great on familiar phrasing but fail unpredictably on novel input. For a medicine recommendation system, unpredictable behavior is not acceptable. Second, reproducibility — the stock pre-trained model is a fixed, publicly available artifact that any researcher can download and get the same results. Third, multilingual coverage — the model already supports 50+ languages including Filipino. Fine-tuning on a few hundred Filipino sentences could actually degrade its broader multilingual capability. We verified this was the right call: the system achieves 9/9 on the semantic stress test using inference-only mode.

**4. Why is the semantic threshold set at 0.65 and how did you arrive at that number?**

We tested different thresholds iteratively. At 0.40 and 0.50, too many unrelated inputs were clearing the bar, which gave us false positives. At 0.60, most valid paraphrases were captured but some figurative or idiomatic expressions got dropped. At 0.65, the system kept coverage for meaningful symptom paraphrases while filtering out adversarial inputs like gibberish and non-symptom text. Going above 0.70 started rejecting valid multilingual paraphrases that were just slightly below the cutoff. We plan to run a more formal sensitivity analysis in Iteration 3 once we have real consultation data.

**5. What happens when neither the dictionary nor the semantic model detects anything?**

The system does not return a blank screen. It tells the user that no OTC-treatable symptoms could be identified and suggests three things: rephrase with more specific symptom words, try describing in a different language, or go directly to the pharmacist for an in-person assessment. The user is never left without guidance.

---

### SAFETY & TRIAGE

**6. How does the triage layer work and how many emergency conditions does it cover?**

The triage layer runs before symptom extraction. It uses proximity-based co-occurrence matching — it looks for specific clinical term pairs appearing within a defined word window, like "blood" near "stool" or "pain" near "chest." It covers 18 unique red-flag types through 19 triage rules, including GI hemorrhage, cardiac emergencies, respiratory distress, dengue, stroke, severe dehydration, pregnancy contraindication, hyperthermia above 40°C, seizure, loss of consciousness, severe allergic reaction, various types of body bleeding, blood in urine, and hypertension risk. Some rules also have exclusion tokens — for example, chest pain is not flagged if the context is cough-related chest congestion.

**7. Why does the triage layer not short-circuit the pipeline?**

Symptoms are still extracted even when a red flag is detected. This is so the benchmark can still validate symptom detection accuracy on those cases. The triage gate activates at Stage 4, where it suppresses all OTC recommendations and returns a "consult a doctor" referral instead. This way, we test symptom extraction and safety gating independently.

**8. What if someone mentions both a red flag and a regular symptom?**

The red flag always takes priority. If someone says "chest pain at masakit ang ulo ko," the system detects chest_pain as a red flag and HEADACHE as a symptom. But the output action is "triage" — no OTC medicines are recommended. The headache is still logged for pipeline accuracy, but the user sees only the referral message.

**9. How do you prevent paracetamol overdose from multiple recommendations?**

The system has a dedicated paracetamol overlap detection check. If multiple paracetamol-containing products end up in the recommendation list — like Bioflu, Neozep, and Biogesic — it flags a warning telling the user not to take them together because of overdose risk. It advises choosing only one.

**10. What about opposing drug mechanisms?**

If the system recommends both an expectorant (like Solmux, which loosens mucus) and a cough suppressant (like Sinecod, which stops coughing) at the same time, it warns the user that these have opposing mechanisms and they should use only one type.

---

### NLP & LINGUISTIC HANDLING

**11. How does the system handle negation in multilingual input?**

We use a negation lexicon of 11 words covering English, Tagalog, and Bisaya — words like "hindi," "walang," "walay," "dili," "no," "not," and "without." The system checks for these words within a 0-to-2 word window before a symptom phrase. We also handle consumed negation: if another symptom keyword sits between the negation word and the target, the negation gets absorbed by the closer keyword instead of propagating further. On top of that, contrastive boundary splitting on words like "pero," "but," and "kaso" lets us evaluate negation per segment — so "walang lagnat pero masakit ang ulo" correctly negates fever but detects headache.

**12. What is the fuzzy rescue mechanism and why do you need exclusion sets?**

The fuzzy rescue uses Levenshtein distance to catch misspelled symptom words. For example, if someone types "lgnat" instead of "lagnat," it is within edit distance 1 and gets recognized as FEVER. But the problem is that some completely unrelated Filipino words are also within edit distance 1 of symptom keywords — "ulo" (head) is distance 1 from "ubo" (cough), "tubo" (sugarcane) is distance 1 from "ubo," "pantalon" (pants) is distance 1 from "pantal" (rashes). Without exclusion sets, these would cause false positives constantly. So each fuzzy rescue family has a curated list of words that are close in edit distance but have nothing to do with the symptom.

**13. How do you handle Jejemon or leetspeak input?**

The normalization layer does character-level substitution before phrase matching: @ becomes a, 0 becomes o, 1 becomes i, 3 becomes e, 4 becomes a, and so on. So "s@k1t ul0" normalizes to "sakit ulo" and matches the HEADACHE dictionary entry. This is purely deterministic — no machine learning needed.

**14. Why split cough into three labels?**

Because different cough types need different medicines. A dry non-productive cough is treated with cough suppressants like Sinecod or Tuseran. A productive wet cough is treated with expectorants like Solmux or Ascof. Giving a suppresant for a productive cough can trap mucus in the lungs, which is dangerous. If the system cannot determine the type, it labels it COUGH_GENERAL and asks the user to clarify before recommending anything.

**15. How does the lexical guard work?**

The lexical guard is a filtering step that prevents the semantic model from hallucinating symptoms. Even if the embedding model says the user's input is semantically similar to HEADACHE, the guard checks whether any headache-related keyword actually appears in the text — words like "ulo," "head," "labad," "migraine." If none are present, the detection is dropped. There are 11 keyword-gate groups that cover all 13 symptom labels — some labels share gates (e.g., all three cough types use the same cough keyword gate). This significantly reduces false positives from the semantic layer.

---

### EVALUATION & BENCHMARKING

**16. Your benchmark shows 288/288 exact match. Is that not suspiciously perfect?**

We get that concern. A few points to address it. First, the 288/288 result in Table 8 includes the cough clarification override — when the benchmark specifies a cough type (dry or productive), the test simulates the user answering the follow-up question. Without that override, the same 288 cases score 234/288 (81.2%) because 54 cases detect COUGH_GENERAL instead of the specific cough type, which is exactly Table 9's result. So the two tables are not different scoring rubrics — they reflect the pipeline with and without the clarification step.

Second, the benchmark was designed by us Researchers, so there is the risk of implicit bias. That is exactly why we also ran the 80-case real-user simulation with messy, realistic inputs — and that scored 90% exact match with 8 partial matches. The 10-point gap is informative: it tells us where the system's limits are. Across all 377 cases combined, zero resulted in outright failure — the system never detected a wrong symptom.

**17. What were the 8 partial matches in the real-user simulation?**

Two patterns. First, severely misspelled body-part words that fell outside what fuzzy rescue can handle — like "bdy" for "body" or "tultunlan" for "lalamunan." Second, inputs where the user mentioned both a productive cough and a general cough in the same sentence, which the cough decision tree cannot handle because it only assigns one cough type per input. Both are addressable in Iteration 3 through dictionary expansion and modified cough logic.

**18. Why did the transformers perform so poorly in your comparative benchmark?**

Data scarcity. Transformer models are built to learn from thousands or tens of thousands of labeled examples. In our setup, each cross-validation fold only gave the transformers about 230 training samples spread across 13 symptom labels — that is a combinatorial space of 2^13 = 8,192 possible label combinations. XLM-RoBERTa, despite having 278 million parameters, achieved 1.000 precision but only 0.017 recall, meaning it basically learned to predict almost nothing to avoid errors. Given enough training data and proper GPU hardware, transformers would likely do much better. Our benchmark answers a practical question: given the resources we actually have, does hand-encoded domain knowledge outperform supervised learning from limited labeled data? For this project, the answer was yes.

**19. How do you ensure no training-test leakage between your dictionary and benchmark?**

No benchmark case was copied from or derived from the dictionary phrase inventory. The 288-case benchmark was finalized only after the rule inventory and semantic anchor set were frozen. The benchmark includes adversarial categories like gibberish, non-symptom text, and universal negation that are specifically designed to test failure modes the dictionary cannot cover.

**20. Why do Table 8 and Table 9 show different numbers on the same 288 cases?**

The key difference is the cough clarification step. In Table 8, when a test case specifies a cough type (dry or productive), the benchmark simulates the user answering the follow-up question — so COUGH_GENERAL gets resolved to COUGH_DRY or COUGH_PRODUCTIVE. Under that condition, all 288 cases are exact matches.

In Table 9 (the comparative benchmark), this override is removed so all six models are evaluated on the same raw pipeline output. Without the override, 54 cases where the system detects COUGH_GENERAL instead of the specific type become partial mismatches, giving Mendo 234/288 (81.2%) exact match and an F1 of 0.852.

We use the raw-output evaluation in Table 9 because it is fairer — the baseline models do not have a clarification mechanism either. Both tables show the same system on the same 288 cases; the only difference is whether the cough clarification step is simulated.

---

### DATA & ASG FRAMEWORK

**21. Why did you adopt the ASG framework instead of pharmacist annotation?**

The original plan was for a licensed pharmacist to annotate OTC medicine entries with clinical indications, contraindications, and safety metadata. The domain expert was unable to complete the annotation within the thesis timeline. Instead of delaying the project or fabricating data, we adopted the Authoritative-Source-Grounded framework, where every data field comes from verifiable published sources: drug package inserts, MIMS Philippines, and DOH Philippines guidelines. This makes every recommendation traceable and reproducible by any researcher with access to the same package inserts.

**22. How many medicines are in your dataset and how did you select them?**

The dataset contains 24 medicine entries covering 19 unique brands. These represent the most commonly dispensed OTC medications in Philippine pharmacies for the 13 symptom categories we cover. Multiple entries exist for the same brand when it comes in different dosage forms — like Biogesic Tablet and Biogesic Syrup — to support age-appropriate form selection. Each entry has 15 data fields sourced from package inserts, MIMS, and DOH.

**23. Why only 13 symptom labels? Why not more?**

We scoped to 13 labels because they represent the most common OTC-treatable complaints seen in Philippine pharmacies — headache, fever, various cough types, runny nose, nasal congestion, sore throat, stomachache, diarrhea, body aches, allergic rhinitis, and rashes. Adding more labels like nausea or dizziness was considered but dropped because we did not have OTC medicines in our dataset that specifically target those symptoms. We would rather have a smaller but fully covered set than a larger one with gaps.

**24. Where does the 5,000 data collection target come from?**

The 5,000 target was set based on comparable multilingual symptom dataset studies in low-resource languages, which typically range from 2,000 to 10,000 entries for initial corpus development. We adjusted for the expected daily foot traffic at selected Botika ng Bayan pharmacy branches over the planned four-week collection period. This collection is part of Iteration 2 and has not yet been completed — it requires ethical clearance first.

---

### DEPLOYMENT & HARDWARE

**25. Why a Raspberry Pi 5 and not a more powerful device?**

Cost and deployability. The whole point of this project is an affordable pharmacy kiosk. The Pi 5 with 8 GB RAM costs around ₱5,000, which is within budget for a small pharmacy. The MiniLM model at 33 million parameters fits comfortably in under 500 MB of memory and returns results in about 93 milliseconds on CPU. Going bigger — like a laptop or mini PC — would double or triple the hardware cost without meaningful improvement in response time for our use case.

**26. Can the system work offline?**

Yes. Everything runs locally — the dictionary, the semantic model, the medicine dataset, the Flask app. No internet connection is needed for any consultation. Patient symptom data never leaves the device, which avoids data privacy concerns under Republic Act 10173.

**27. Why not use a cloud-based LLM like GPT-4 or Gemini?**

Six reasons: (1) safety — LLMs produce probabilistic outputs and can hallucinate drug names or miss negations; (2) explainability — we can trace exactly which dictionary phrase matched or which anchor activated, while an LLM's reasoning is opaque; (3) offline deployment — cloud APIs require internet, which is unreliable in some pharmacy locations; (4) cost — API charges per token add up for hundreds of daily consultations over medicines that cost a few pesos each; (5) privacy — sending patient symptoms to external servers raises compliance issues under Philippine data privacy law; (6) the problem is bounded — 13 symptoms, 24 medicines, deterministic safety rules. LLMs shine on open-ended tasks, not narrow, well-defined ones.

---

### METHODOLOGY & RESEARCH DESIGN

**28. Why Design Science Research and not experimental or quasi-experimental?**

Because we are building and evaluating an artifact, not testing a hypothesis about an existing phenomenon. Design Science Research fits naturally — we define requirements, build the system iteratively, evaluate it, and refine it across multiple cycles. The outcome is both a working system and a documented set of design decisions. Traditional experimental designs would require a control group and treatment group, which does not match what we are doing here.

**29. What is the role of OLDCARTS in your system?**

OLDCARTS stands for Onset, Location, Duration, Character, Aggravating, Relieving, Timing, and Severity. We use it as an inspiration for our clarification layer — it is a partial, adapted implementation, not a full clinical OLDCARTS interview. In a kiosk setting, we cannot expect users to answer eight structured questions, so we only trigger one follow-up per symptom and only when the detected symptom is the sole complaint with no contextual clues.

Concretely, we implemented four OLDCARTS-inspired clarification triggers:

1. **Cough clarification** — asks "Is your cough dry or with phlegm?" when COUGH_GENERAL is detected but no dry/productive qualifier is found. This maps to the **Character** component.
2. **Diarrhea context** — asks "Did you eat spoiled food?" and "Do you have fever?" to distinguish food poisoning from non-infectious diarrhea. This maps to **Onset** (cause/trigger event).
3. **Stomach ache context** — asks "Is it burning/acidic or cramping/bloating?" to differentiate hyperacidity from spasms. This maps to **Character**.
4. **Sipon/runny nose context** — asks about co-occurring fever/cough, frequent sneezing or itchy nose, and cold/rain exposure to distinguish viral cold, allergy, or weather-induced runny nose. This covers **Character**, **Aggravating**, and light **Timing** (e.g., "every morning").

On top of these active questions, we also do passive context detection — for example, if the user's input already contains clues like "kumain ng panis" or "makati ilong," the system skips the question and acts on that context directly.

The components we do NOT implement are **Location** (no body-part clarification), **Duration** (no "how long" questions), **Relieving** (no "what makes it better"), and actively queried **Severity** (though severity is logged if provided). We kept the scope minimal because a pharmacy kiosk interaction should be fast — one clarification question at most.

**30. How do you handle the ethical considerations of recommending medicine without a pharmacist?**

The system is explicitly designed as a decision-support tool, not a replacement for a pharmacist. It does not diagnose — it only recommends OTC products within their approved indication scope. The triage layer catches emergencies and refers users to a doctor. Age filtering removes medicines below the user's minimum age. The ASG framework ensures every recommendation is traceable to published pharmaceutical sources. The system is intended to be deployed in a pharmacy setting where a licensed pharmacist is still present and accessible. We also plan to obtain ethical clearance before any real-user deployment.

---

### ADDITIONAL QUESTIONS

**31. What is consumed negation and why is it important?**

Consumed negation handles cases like "hindi pala ubo sipon" — where "hindi" is a negation word, "ubo" is a cough keyword, and "sipon" is a runny nose keyword. Without consumed negation, "hindi" would negate both "ubo" and "sipon" because both are within its window. With consumed negation, we check if another symptom keyword sits between the negation and the target. Since "ubo" is closer, it absorbs the negation, and "sipon" is left unnegated. This prevents over-negation in multi-symptom inputs, which is common in how Filipino speakers naturally describe their conditions.

**32. What were the 19 bugs you found through adversarial probing?**

They spread across common problem areas: negation not being applied to certain symptom labels, fuzzy rescue re-adding symptoms that were explicitly negated, cough-type logic breaking on edge cases like negated phlegm phrases, false positive matches from unrelated Filipino words that happened to be similar in spelling to symptom keywords, nasal inference that was too aggressive when one nasal group was negated, and reversed word order not being caught by the dictionary. Each bug was fixed one at a time, and after every fix the full 288-case benchmark was re-run to make sure nothing that was already working got broken.

**33. How does the system handle mixed Bisaya-Tagalog-English input in a single sentence?**

The dictionary has phrases in all three languages plus common code-switched patterns like "masakit head ko" or "may cough ako." The normalization layer handles Jejemon regardless of the base language. For novel mixed expressions not in the dictionary, the semantic fallback uses the paraphrase-multilingual-MiniLM model, which was pre-trained on 50+ languages and can map cross-lingual paraphrases into the same embedding space. The lexical guard then checks that any semantic detection is grounded in at least one relevant keyword from the original text.

**34. Why does the system not handle nausea, vomiting, dizziness, or fatigue?**

Those symptoms were in an earlier version of the plan but were removed because we did not have specific OTC medicines in our dataset that target them as primary indications. We chose to scope the system to only cover symptoms where we can provide a concrete, ASG-verified medicine recommendation. Adding labels without corresponding medicines would create a bad user experience — you detect the symptom but have nothing to recommend.

**35. What is your plan for Iteration 2 and Iteration 3?**

Iteration 2 has two tracks: (1) software — deploying the system in a controlled pharmacy setting so real users interact with it, with a pharmacist reviewing the consultation logs to create an expert-annotated dataset; and (2) hardware — building the physical vendo kiosk with the Raspberry Pi, touchscreen, and dispensing mechanism. Iteration 3 brings everything together: refining the software based on the expert-annotated data, integrating the software into the hardware, running end-to-end dispensing tests, and final deployment. Both iterations require ethical clearance before any real-user data collection.

---

### SYSTEM ARCHITECTURE DEEP-DIVE

**36. Walk us through the complete data flow from user input to final recommendation.**

The user types a symptom description in the kiosk interface. The Flask route receives the text, age, and any prior clarification answer. First, the text is normalized — lowercased, leetspeak characters substituted, non-alphanumeric characters removed, whitespace collapsed. Then Stage 0 (triage) scans for red-flag co-occurrences like "blood + stool" or "pain + chest." If a red flag is found, it is recorded but extraction still continues. Stage 1 runs the 331-phrase dictionary against the normalized text, applying contrastive boundary splitting, negation detection, consumed negation logic, cough-type qualification, and fuzzy rescue. If the dictionary returns results, those become the final symptom set. If not, Stage 2 loads the MiniLM model (lazy singleton), encodes the input, compares it against 118 anchors, and returns detections above 0.65. Stage 3 applies 11 lexical-guard keyword gates to filter semantic detections, then runs 7 explicit negation functions and 2 red-flag suppression rules. The top-N semantic symptoms are selected. At Stage 4, the recommendation engine checks if clarification is needed (cough type, diarrhea context, stomach context, sipon context). If yes, it returns a question. If not, it matches symptoms against the 24-entry JSON dataset, scores candidates, merges brand duplicates, applies paracetamol overlap warnings, opposing-mechanism warnings, and age filtering, then returns the ranked recommendations. The entire consultation is logged to a JSONL file.

**37. Why is your system a Flask monolith and not a microservices architecture?**

Because the deployment target is a single Raspberry Pi 5 in a pharmacy kiosk. A microservices architecture introduces networking overhead, container orchestration complexity, and higher memory use — none of which make sense for a single offline device with 8 GB of RAM running one application. Flask gives us a clean request-response cycle with modular Python packages. Each pipeline stage is in its own module (step1.py, step2.py, step3_hybrid.py, step4_recommend.py), so we get logical separation without the operational cost of separate services.

**38. How are the pipeline modules organized in the codebase?**

The core logic lives in the `mendo_core/` package: `step1.py` handles dictionary extraction, normalization, negation, and fuzzy rescue; `step2.py` holds the semantic anchor definitions and embedding extractor class; `step3_hybrid.py` orchestrates the stages — triage, dictionary, semantic fallback, lexical guards, safety filters, and clarification routing; `step4_recommend.py` handles symptom-to-medicine matching, scoring, safety checks, and clarification question generation. There is also `symptom_models.py` for shared data structures and `interaction_logger.py` for JSONL logging. The web layer (`web/app.py`) handles Flask routes, and the POS module (`pos/`) handles inventory and admin. This separation means the NLP pipeline can be tested independently of the web interface.

**39. How does the lazy singleton pattern work for the semantic model, and why is it needed?**

The MiniLM model is loaded only on the first query where the dictionary returns zero results. A module-level flag (`_SEMANTIC_LOADED`) prevents reloading on subsequent queries. This matters because on the Raspberry Pi 5, loading the model takes several seconds and uses ~500 MB of memory. If every consultation loaded the model — even when the dictionary handles the input fine — startup time and memory pressure would be unnecessarily high. Most consultations never need the semantic layer, so lazy loading keeps the common path fast.

**40. What is the role of the interaction logger and what does it capture?**

Every consultation is logged as a JSON line in `logs/interactions.jsonl`. Each entry records: the raw user input, normalized text, detected symptoms with their source (dictionary or semantic with anchor and score), any red flags triggered, the cough type if applicable, the clarification question asked and user's response, the final recommendation list, safety warnings issued, and timestamps. This creates a full audit trail so a pharmacist can review any consultation after the fact. It also forms the basis for the real-user evaluation corpus in Iteration 2.

**41. How does the system handle concurrent users on the kiosk?**

In the current iteration, the kiosk is designed for single-user sequential consultations — one person at a time, as you would expect at a pharmacy counter. Flask runs in a single-threaded WSGI mode. Session state for a multi-step consultation (e.g., initial input → clarification response → recommendation) is managed through the HTTP request-response cycle and client-side state, not server-side sessions. This keeps the architecture simple and avoids concurrency issues entirely.

**42. How does the POS integration work with the recommendation engine?**

The POS module manages inventory through a SQLite database. When recommendations are generated, the system can cross-reference available stock. If a recommended medicine is out of stock, the system can either flag it or suggest the next-best alternative within the same drug category. Admin routes allow pharmacy staff to update inventory, add items, and view sales records. The POS module and recommendation engine communicate through Python function calls within the same process — no API boundary needed.

**43. Why did you choose SQLite instead of PostgreSQL or MySQL for the POS?**

SQLite is file-based — no separate database server to install, configure, or maintain. On a Raspberry Pi in a pharmacy, the simpler the stack, the better. Our POS data is low-volume (dozens of products, maybe hundreds of transactions per day), well within SQLite's capabilities. SQLite also works perfectly offline, which matches our deployment requirement. If we needed multi-device synchronization or high concurrent writes, we would upgrade, but that is not the case here.

**44. If the dictionary catches the primary symptom but misses a secondary one expressed idiomatically, the semantic layer does not activate. Is that not a design flaw?**

We acknowledge this trade-off explicitly in the paper. The precision-first switching logic means the semantic layer only activates when Stage 1 returns zero symptoms. Our reasoning: in an OTC recommendation context, a false positive (hallucinating a symptom that is not there) is more dangerous than a false negative (missing a secondary symptom). A missed secondary symptom leads to an incomplete but still safe recommendation. A false positive could trigger a contraindicated medicine. The 8 partial matches in the 80-case real-user simulation are a direct result of this design choice. Relaxing the logic so the semantic layer runs as augmentation is planned for Iteration 3 with proper false-positive evaluation.

**45. How does the system scale if you add more symptoms or medicines in the future?**

Adding a new medicine is straightforward — add a JSON entry with 15 fields to the dataset. Adding a new symptom label requires: adding phrases to the dictionary in step1.py, adding anchor sentences in step2.py, adding a keyword gate in step3_hybrid.py, and mapping the label to medicines in step4_recommend.py. Each step is in a separate file, so expansion is modular. The system is not trained on a fixed label set — it is rule-based, so changes take effect immediately without retraining.

**46. What happens if the kiosk loses power mid-consultation?**

The consultation state is not persisted between requests. If power is lost, the user simply starts a new consultation when the system comes back up. No partial state to clean up, no database corruption risk (SQLite handles its journal safely). The interaction log uses append-only JSONL writes, so a power failure at most loses the current incomplete log line — all previously logged consultations remain intact.

**47. You mention "contrastive boundary splitting." How is this implemented architecturally?**

The system uses a regex-based splitter that divides the normalized input on contrastive conjunctions — "pero," "but," "kaso," "however," "though." Each resulting segment is then evaluated independently for negation. This is important because Filipino speakers commonly say things like "walang lagnat pero masakit ang ulo" — without splitting, the negation on "lagnat" would incorrectly propagate to "ulo." The split happens early in Stage 1 before phrase matching, so every downstream component works on properly scoped segments.

**48. How do you handle the case where a user describes symptoms for someone else — like a parent describing a child's symptoms?**

The system handles third-person descriptions through dictionary coverage — phrases like "anak ko may lagnat" (my child has fever) or "asawa ko masakit ulo" (my spouse has headache) are matched. The triage layer also has exclusion tokens for proxy contexts — for example, "buntis" (pregnant) triggers a red flag, but "asawa ko buntis" (my wife is pregnant) uses the exclusion token "asawa" to suppress the flag, since the person at the kiosk is buying for someone else. Age is provided separately through the interface, so the system applies correct age filtering regardless of who is typing.

**49. What is the architectural rationale for having the triage check run at Stage 0 but the triage gate fire at Stage 4?**

Triage detection (finding red flags) runs at Stage 0 so it can see the raw input before any symptom extraction modifies the context. But the triage gate (suppressing recommendations) fires at Stage 4 because we still want the intermediate stages to extract symptoms — this allows the benchmark to validate symptom detection accuracy even on triage cases. The red_flags list is simply passed through the pipeline and checked at the final recommendation step. If any red flag is present, all OTC recommendations are suppressed and the user gets a referral message instead. This separation makes testing much easier because we can verify symptom extraction and triage independently.

**50. Your paper mentions your system does NOT use a knowledge graph. How is your medicine dataset different from a knowledge graph?**

A knowledge graph typically means a graph database with explicit nodes (entities) and edges (relationships) — like Neo4j or RDF triples — where you can traverse relationships computationally. Our medicine dataset is a flat JSON file: a list of 24 dictionary objects, each with 15 key-value fields. There are no explicit relationship edges between medicines. Contraindication checks, paracetamol overlap detection, and opposing-mechanism warnings are implemented as hard-coded rules in Python, not as graph traversal queries. Calling it a knowledge graph would be inaccurate — it is a structured lookup table with rule-based safety logic on top.

---

### HYBRID APPROACH & PERFORMANCE JUSTIFICATION

**51. Why is the hybrid pipeline the right architecture? Why not just use a single fine-tuned transformer end-to-end?**

This is a question of matching your architecture to your actual constraints, not chasing leaderboard numbers. We have three hard constraints that rule out a single transformer: (1) **data scarcity** — we only have 288 labeled cases across 13 symptom labels. That gives a combinatorial space of 2^13 = 8,192 possible label combinations. Transformers need thousands of examples per class to learn meaningful patterns. We proved this empirically: XLM-RoBERTa (278M parameters) achieved only 22.6% exact match after fine-tuning; mBERT (178M parameters) managed only 38.2%. The hybrid pipeline hit 81.2% without seeing a single training example from the benchmark. (2) **hardware constraint** — the target is a Raspberry Pi 5 with 8 GB RAM, no GPU. Running a 178M–278M parameter fine-tuned transformer in real-time is impractical on that hardware. Our 33M-parameter MiniLM runs inference-only (no gradients, no training overhead) in under 500 MB. (3) **safety and traceability** — a pharmacy system cannot be a black box. With the hybrid pipeline, every detection is traceable: you can see exactly which dictionary phrase matched, which semantic anchor activated with what similarity score, which negation word cancelled which detection. A fine-tuned classifier gives you a probability distribution over labels and no explanation of why.

The hybrid approach is not novel architecture for its own sake — it is the only architecture that satisfies all three constraints simultaneously. Pure rule-based fails on paraphrases. Pure ML fails on limited data. Hybrid gives us the best of both: deterministic rules for known patterns, and ML fallback for novel expressions, with guards to prevent the ML layer from producing false positives.

**52. Your system has 93.07ms latency while SVM and Logistic Regression have 0.05ms and 0.06ms. Isn't the hybrid pipeline slow?**

The 93ms is the per-query latency measured on CPU (Raspberry Pi 5, no GPU). Let us put this in perspective:

First, **93ms is less than one-tenth of a second.** In a pharmacy kiosk context, the user types a symptom description and presses submit. A 93ms processing time is instantaneous from the user's perspective — the bottleneck is the human typing, not the system processing. Users will not perceive any delay. For comparison, a typical web page load takes 1,000–3,000ms. A blink of an eye is ~300ms. Our system responds 3x faster than a blink.

Second, **the SVM and Logistic Regression latencies (0.05ms and 0.06ms) are misleading.** Yes, they are technically faster — but they only achieved 55.9% and 33.0% exact match respectively. An SVM that gives you a wrong answer in 0.05 milliseconds is not better than a hybrid pipeline that gives you the right answer in 93 milliseconds. Speed is meaningless if accuracy is too low to be clinically useful. You would not deploy a medicine recommendation system that gets the wrong answer 44% of the time just because it is fast.

Third, the 93ms includes the full pipeline: text normalization, triage scanning, 331-phrase dictionary matching, Levenshtein fuzzy rescue, negation detection, contrastive boundary splitting, AND (when needed) the MiniLM transformer inference with cosine similarity against 118 anchors. The dictionary-only path (which handles most inputs) is significantly faster than 93ms — the average is pulled up by the semantic fallback cases that load the transformer model.

Fourth, compared to models of similar accuracy ambitions: mBERT takes 35.45ms and only achieves 38.2% exact match. Random Forest takes 23.77ms for 50.0%. Our pipeline takes 93ms for 81.2%. The latency-to-accuracy ratio overwhelmingly favors the hybrid approach.

**53. If the transformer baselines had more training data, would they beat your hybrid pipeline? Is this a fair comparison?**

We are transparent about this in the paper. Yes — given thousands of labeled examples and GPU hardware for training and optionally inference, transformer models would very likely perform much better. XLM-RoBERTa's 1.000 precision / 0.017 recall pattern is a textbook sign of insufficient training data, not a flaw in the model itself.

But that is precisely the point: the comparison answers a **practical** question, not a theoretical one. We do not have thousands of labeled examples — we have 288. We do not have GPU hardware at deployment — we have a Raspberry Pi 5.  We cannot collect more data before our defense — ethical clearance for real-user data collection is part of Iteration 2, which has not happened yet.

Given the resources we actually have today, the hybrid pipeline outperforms everything else by 25+ percentage points. The comparison is fair because all six models were evaluated on the same 288 test cases, with the same cross-validation splits (seed=42), the same feature extraction settings, and the same hyperparameters within each model class. The baselines even had a structural advantage: they trained on ~80% of the benchmark per fold (~230 samples), while the Mendo pipeline was evaluated cold with zero training samples from the benchmark.

We acknowledge the caveat openly. We are not claiming hybrid pipelines are universally better than transformers. We are claiming that for this specific problem, with these specific resource constraints, the hybrid approach was the right engineering decision — and the benchmark numbers back that up.

**54. 93ms is the average — what is the worst-case latency? Could some queries take much longer?**

The 93ms figure is the mean latency across all 288 benchmark cases. The worst-case scenario is a query where: (1) the dictionary finds nothing (forcing the semantic model to load), (2) the semantic model runs cosine similarity against all 118 anchors, and (3) multiple post-processing steps (negation, lexical guards, clarification logic) all execute. Even in this worst case, latency stays well under 500ms on the Raspberry Pi 5. The first-ever query after system startup is the slowest because it triggers lazy loading of the MiniLM model (~2–3 seconds to load into memory). After that, the model stays resident as a singleton, so subsequent semantic queries only pay the inference cost (~100–150ms), not the loading cost. For a kiosk interaction where the user spends 10–30 seconds typing their symptoms, even a 500ms processing time is imperceptible.

**55. Why not use a lighter model than MiniLM to reduce the 93ms latency even further?**

We considered this. Smaller models like TinyBERT or DistilBERT exist and would be faster. The problem is multilingual coverage. MiniLM (paraphrase-multilingual-MiniLM-L12-v2) was specifically trained for cross-lingual paraphrase detection across 50+ languages including Filipino. Smaller models either lack Filipino support, produce lower-quality embeddings for non-English text, or were not trained for paraphrase tasks. Since our semantic fallback needs to match Tagalog, Bisaya, and code-switched expressions to English anchor sentences, the multilingual paraphrase capability is non-negotiable. At 33M parameters and 93ms latency, MiniLM sits in the sweet spot between accuracy and speed for our hardware constraint. Going smaller would save maybe 30–40ms but risk missing valid multilingual paraphrases — a bad trade-off when 93ms is already imperceptible to the user.
