3.2.2 Iteration 2: Dataset Refinement, Expert Validation, and Domain Adaptation

The second iteration focuses on three key priorities: constructing a cleaner, more representative dataset, obtaining expert validation from a licensed pharmacist, and adapting semantic models to the specific domain. The researchers identified the need to address training-test leakage — a documented limitation of Mendo v2.0 — and to ensure multilingual coverage across English, Filipino/Tagalog, Cebuano/Bisaya, code-switched combinations, and informal slang. Key activities include:

	Phase 2A: Dataset Construction and Leakage Remediation

Multilingual Corpus Construction: A corpus of 1,039 realistic patient-style utterances was constructed, covering Bisaya, Tagalog, English, code-switched combinations, and informal slang to reflect real-world input patterns observed during Iteration 1 deployment. Each entry was designed to exercise the full range of pipeline behaviors including negation, multi-symptom combinations, cough-type ambiguity, and triage triggers.
Training-Test Leakage Identification: Systematic audit of the v2.0 evaluation methodology revealed overlap between training anchors and test inputs, inflating reported accuracy. The Iteration 2 dataset was constructed with strict separation to ensure no anchor sentence or close paraphrase appeared in the evaluation corpus, addressing this documented limitation.
Symptom Taxonomy Expansion: The symptom label set was expanded from 13 to 15 clinically meaningful labels to accommodate additional OTC-treatable conditions identified through pharmacist consultation and real-world interaction log analysis from Iteration 1 deployment.

	Phase 2B: Expert Annotation Infrastructure and Validation

Web-Based Annotation Tool Development: To facilitate structured expert annotation, a web-based annotation tool was developed and deployed at mendo.diapana.dev. The tool presented each utterance with structured input fields for symptom labels, recommended OTC drugs, age restrictions, dosage guidance, and safety referral flags, producing machine-readable JSON outputs for downstream evaluation.
Pharmacist Annotation Process: A licensed pharmacist annotated the full 1,039-entry corpus using the deployed annotation tool, producing gold-standard evaluation data with symptom labels, medication recommendations, safety considerations, and clinical appropriateness assessments. The structured annotation workflow ensured consistency across all entries and eliminated subjective interpretation variance.
Gold-Standard Corpus Finalization: The pharmacist-annotated corpus was validated for internal consistency, with ambiguous or conflicting annotations resolved through follow-up consultation. The finalized gold-standard dataset serves as the authoritative reference for all Iteration 2 and Iteration 3 evaluations.

	Phase 2C: Domain-Specific Model Adaptation and Dictionary Expansion

Embedding Model Fine-Tuning: Domain-specific adaptation of the paraphrase-multilingual-MiniLM-L12-v2 embedding model was performed using 252 sentence-pair similarity samples derived from the annotated corpus. Training was conducted using CosineSimilarityLoss with a batch size of 16, 4 epochs, 50 warmup steps, and the AdamW optimizer at a learning rate of 2×10⁻⁵. The fine-tuned model retains the original 384-dimensional embedding space while improving cosine similarity alignment for Philippine pharmacy domain terminology.
Multilingual Dictionary Expansion: The rule-based symptom dictionaries were iteratively expanded from 307 phrases (Iteration 1) to 522 curated phrases across the 15 symptom labels, based on observed linguistic patterns from the interaction logs and domain expert input. New entries addressed Bisaya spelling variants (e.g., lisod/lisud, moginhawa/muginhawa), informal medical terminology, and previously unrecognized pain descriptors (e.g., gakurot, kabutohon for headache).
Negation and Safety Filter Updates: The negation handling system and semantic safety filters were updated to accommodate the expanded label set and newly identified edge cases from the interaction log analysis, including nonproductive cough misclassification, expanded red-flag pattern coverage, and additional Bisaya triage triggers.

	Phase 2D: Threshold Optimization and Evaluation Infrastructure

Threshold Sweep Analysis: A systematic threshold sweep ranging from 0.40 to 0.85 was conducted on a 2,170-entry symptom evaluation corpus to identify the F1-maximizing cosine similarity cutoff for symptom detection. This data-driven approach replaced the manually selected 0.65 threshold from Iteration 1, eliminating manual threshold bias and ensuring the cutoff is empirically optimal for the domain-adapted model.
Clean Evaluation Split Finalization: The evaluation split was finalized with strict verification that no training-test leakage carried over from the dataset construction process. Anchor sentences, dictionary phrases, and fine-tuning pairs were cross-referenced against evaluation inputs to guarantee zero overlap.
Annotation Tool Deployment and Monitoring: The annotation tool developed in Phase 2B was maintained throughout the evaluation phase, with logging and audit trails ensuring traceability of all expert annotations back to their source utterances.

	Phase 2E: Evaluation and Comparative Analysis

Gold-Standard Evaluation: The fine-tuned MiniLM model and the expanded rule dictionaries were evaluated against the expert-annotated gold-standard corpus. Performance was assessed using the optimized cosine similarity threshold identified through the sweep analysis, measuring precision, recall, and F1-score across all 15 symptom labels.
Baseline Comparison: Results were compared against the v2.0 baseline benchmarks established in Iteration 1, quantifying improvements in precision (particularly for negated and adversarial inputs), multilingual coverage, and safety-critical detection accuracy.
Iteration Review: The outputs of Iteration 2 were reviewed, including the deployed annotation tool, the domain-adapted MiniLM embedding model, the validated 15-label symptom set, the expert-annotated gold-standard corpus, and the clean evaluation split free of training-test leakage. These outputs directly addressed the documented limitations of Mendo v2.0 and established a solid foundation for the final integration and refinement work in Iteration 3.

Iteration 2 produces a validated, expert-annotated gold-standard corpus of 1,039 entries, a domain-adapted embedding model fine-tuned on 252 sentence pairs, an expanded 522-phrase multilingual dictionary covering 15 symptom labels, an empirically optimized similarity threshold, and a clean evaluation split free of training-test leakage.
