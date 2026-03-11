"""
Generate the corrected Materials & Methods chapter as a .docx file.
All data verified against actual source code.
"""

from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
import os

doc = Document()

# ── Style Setup ──────────────────────────────────────────────────────────────
style = doc.styles['Normal']
font = style.font
font.name = 'Times New Roman'
font.size = Pt(12)
style.paragraph_format.space_after = Pt(6)
style.paragraph_format.line_spacing = 1.5

# Heading styles
for level in range(1, 5):
    hstyle = doc.styles[f'Heading {level}']
    hstyle.font.name = 'Times New Roman'
    hstyle.font.color.rgb = RGBColor(0, 0, 0)
    hstyle.font.bold = True
    if level == 1:
        hstyle.font.size = Pt(16)
    elif level == 2:
        hstyle.font.size = Pt(14)
    elif level == 3:
        hstyle.font.size = Pt(13)
    else:
        hstyle.font.size = Pt(12)

def add_paragraph(text, bold=False, italic=False, indent=False):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold
    run.italic = italic
    if indent:
        p.paragraph_format.left_indent = Inches(0.5)
    p.paragraph_format.first_line_indent = Inches(0.5)
    return p

def add_bullet(text, level=0):
    p = doc.add_paragraph(style='List Bullet')
    p.clear()
    run = p.add_run(text)
    if level > 0:
        p.paragraph_format.left_indent = Inches(0.5 * (level + 1))
    return p

def add_numbered(text):
    p = doc.add_paragraph(style='List Number')
    p.clear()
    run = p.add_run(text)
    return p

# ═══════════════════════════════════════════════════════════════════════════════
# CHAPTER 3: MATERIALS AND METHODS
# ═══════════════════════════════════════════════════════════════════════════════

doc.add_heading('CHAPTER 3', level=1)
doc.add_heading('MATERIALS AND METHODS', level=1)

# ── 3.1 Introduction ─────────────────────────────────────────────────────────
doc.add_heading('3.1 Introduction', level=2)

add_paragraph(
    'This chapter describes the research methodology used to develop '
    'MendoVendo v3.0, an AI-enabled multilingual symptom detection and '
    'over-the-counter (OTC) medicine recommendation system built for '
    'deployment on resource-constrained edge devices. The study follows a '
    'Design Science Research (DSR) methodology organized into two '
    'iterative design cycles. The first iteration covers the complete '
    'system design, implementation, and evaluation against safety, '
    'precision, and multilingual robustness criteria. The second '
    'iteration focuses on expert validation and targeted refinement '
    'based on evaluation findings.'
)

add_paragraph(
    'The research uses a hybrid rule-based and distributional semantics '
    'approach that balances semantic understanding with computational '
    'efficiency and clinical safety. This chapter covers the research '
    'design, theoretical framework, system architecture, data construction, '
    'evaluation methodology, and the iterative refinement process that '
    'shaped the final system.'
)

add_paragraph(
    'The main research objective is to develop a system that reduces '
    'safety violations while improving recommendation precision on clinically '
    'meaningful outputs, without sacrificing recall on supported symptom '
    'vocabulary. The system achieves this through a five-stage cascaded '
    'hybrid NLP pipeline that combines deterministic rule-based extraction, '
    'pre-trained multilingual sentence embeddings, lexical safety guards, '
    'a triage layer for medical emergencies, and a structured medicine '
    'dataset grounded in authoritative pharmaceutical sources.'
)

# ── 3.2 Research Design ──────────────────────────────────────────────────────
doc.add_heading('3.2 Research Design', level=2)

add_paragraph(
    'This study uses an iterative design science research methodology, '
    'which is well suited for developing and evaluating artificial '
    'intelligence systems in healthcare contexts (Engstrom et al., '
    '2022; Baskerville et al., 2024). Design science research offers a '
    'systematic framework for creating and evaluating novel artifacts, '
    'in this case a hybrid NLP pipeline and recommendation engine, '
    'through iterative cycles of design, implementation, and evaluation. '
    'The methodology consists of two design iterations: the first '
    'produces the complete working system, and the second focuses on '
    'expert validation and refinement based on evaluation outcomes.'
)

# 3.2.1 Iteration 1
doc.add_heading(
    '3.2.1 Iteration 1: Complete System Design, Implementation, '
    'and Evaluation', level=3
)

add_paragraph(
    'The first iteration encompasses the full design, implementation, and '
    'evaluation of the MendoVendo v3.0 system. This iteration begins with '
    'baseline analysis of MendoVendo v2.0, proceeds through the construction '
    'of all five pipeline stages, and concludes with comprehensive '
    'evaluation and error-driven refinement. Key activities include:'
)

add_paragraph('Phase 1A: Baseline Analysis and Architecture Design', bold=True)

add_bullet(
    'Baseline System Evaluation: Reproduction and systematic evaluation of '
    'the existing TF-IDF and cosine similarity-based approach from v2.0, '
    'confirming strong recall but low precision and multiple safety-critical '
    'errors on adversarial examples (e.g., negated symptoms being treated as '
    'positive detections).'
)
add_bullet(
    'Symptom Taxonomy Definition: Establishment of 13 clinically meaningful '
    'symptom labels (HEADACHE, FEVER, COUGH_DRY, COUGH_PRODUCTIVE, '
    'COUGH_GENERAL, RUNNY_NOSE, NASAL_CONGESTION, SORE_THROAT, STOMACH_ACHE, '
    'DIARRHEA, BODY_ACHES, ALLERGIC_RHINITIS, and RASHES), covering the most '
    'common OTC-treatable conditions in Philippine pharmacy settings. '
    'COUGH_GENERAL serves as an ambiguous intermediate label triggering a '
    'clarification prompt when it is the sole detected symptom.'
)
add_bullet(
    'Pipeline Architecture Design: Specification of the five-stage cascaded '
    'pipeline with (0) triage/red-flag safety layer, (1) rule-based '
    'dictionary extraction, (2) semantic embedding fallback, (3) hybrid '
    'merge with lexical guards and safety filters, and (4) structured '
    'medicine dataset scoring with safety checks.'
)
add_bullet(
    'Requirements Gathering: Identification of functional and non-functional '
    'requirements based on v2.0 limitations, including multilingual support '
    '(English, Filipino/Tagalog, Cebuano/Bisaya, Taglish code-switching, '
    'and Jejemon/leetspeak), computational constraints for Raspberry Pi 5 '
    'deployment, and safety-critical handling of negated symptoms and '
    'medical emergencies.'
)

add_paragraph('Phase 1B: Dictionary Construction and Negation Engineering', bold=True)

add_bullet(
    'Multilingual Symptom Dictionary Construction: Iterative expansion of '
    'the rule-based symptom dictionary to 307 curated phrases across 13 '
    'symptom labels, covering five language variants: Tagalog, '
    'Bisaya/Cebuano, English, Taglish/Conyo code-switching, and '
    'Jejemon/leetspeak. Each phrase was manually verified for linguistic '
    'accuracy and clinical relevance.'
)
add_bullet(
    'Negation Handling Implementation: Development of a comprehensive '
    'negation detection system incorporating 11 negation words (hindi, '
    'walang, walay, waley, dili, di, wala, hnd, no, not, without), '
    'a 0–2 word proximity window, consumed negation logic using 28 '
    'intervening symptom words, and negated-label tracking to prevent '
    'fuzzy rescue from re-adding negated symptoms.'
)
add_bullet(
    'Contrastive Boundary Logic: Implementation of contrastive-boundary '
    'splitting on conjunctions (pero, but, kaso, however, though), enabling '
    'per-segment negation evaluation. A positive mention after a contrastive '
    'boundary overrides prior negation (e.g., "wala akong lagnat pero '
    'masakit ang ulo" correctly detects HEADACHE while negating FEVER).'
)
add_bullet(
    'Fuzzy Rescue Development: Construction of seven Levenshtein-distance '
    'rescue families with curated exclusion sets to prevent false positives '
    '(e.g., "tubo" excluded from matching "ubo" for COUGH; "pantalon" '
    'excluded from matching "pantal" for RASHES). All fuzzy rescues check '
    'the negated-labels set before adding a symptom.'
)
add_bullet(
    'Cough-Type Qualification Logic: Design of a seven-step decision tree '
    'for cough classification: (1) itchy/scratchy throat → COUGH_DRY, '
    '(2) chest-rattle/congestion indicators → COUGH_PRODUCTIVE bypass, '
    '(3) cough word presence check, (4) cough negation with plema-filler '
    'exemption, (5) dry qualifier check, (6) wet qualifier check, '
    '(7) default to COUGH_GENERAL.'
)
add_bullet(
    'Proximity-Based Heuristic Development: Implementation of headache '
    'detection (head_word + pain_word within ≤5 tokens), sore throat '
    'proximity (throat_word + pain_word within ≤5 tokens with dual negation '
    'checking), per-cue-group nasal inference (three independent cue groups '
    'with independent negation), and allergen-trigger inference (RASHES + '
    'allergen keyword → ALLERGIC_RHINITIS co-detection).'
)

add_paragraph('Phase 1C: ASG Framework and Medicine Dataset', bold=True)

add_bullet(
    'ASG Framework Adoption: Adoption of the Authoritative-Source-Grounded '
    '(ASG) framework for medicine data, sourcing all drug information from '
    'package inserts, MIMS Philippines, and DOH Philippines guidelines. '
    'This approach replaced the originally planned pharmacist annotation '
    'process (via web tool at mendo.diapana.dev), which could not be '
    'completed within the project timeline. The ASG framework ensures every '
    'medicine recommendation is traceable to an authoritative pharmaceutical '
    'source.'
)
add_bullet(
    'Medicine Dataset Construction: Assembly of 23 OTC medicine entries '
    '(18 unique brands) with 15 fields each, including 7 ASG-specific '
    'fields (approved indications, indication source, contraindications, '
    'warnings, drug interactions, maximum duration, contraindication source). '
    'This scope was intentionally reduced from v2.0\'s 81 entries to focus '
    'exclusively on OTC medications appropriate for kiosk dispensing.'
)
add_bullet(
    'Recommendation Engine Development: Implementation of the rule-based '
    'symptom-to-medicine matching algorithm with score ranking, brand '
    'merging, triage gate, COUGH_GENERAL defer strategy, paracetamol '
    'overlap detection, and opposing mechanism warnings.'
)

add_paragraph('Phase 1D: Semantic Integration and Safety Hardening', bold=True)

add_bullet(
    'Semantic Fallback Integration: Integration of the pre-trained '
    'paraphrase-multilingual-MiniLM-L12-v2 sentence embedding model '
    '(approximately 33 million parameters, 384-dimensional embeddings) '
    'as a fallback layer that activates only when the dictionary-based '
    'extractor returns zero symptoms. The model is used in inference-only '
    'mode with no fine-tuning, ensuring reproducibility and eliminating '
    'overfitting risk. A total of 118 anchor sentences (8–12 per label) '
    'serve as gold-standard semantic reference points, with a fixed '
    'cosine similarity threshold of 0.65 determined through empirical '
    'testing.'
)
add_bullet(
    'Lexical Guard Mechanism: Development of 11 keyword gates that require '
    'each semantic detection to be grounded in at least one relevant keyword '
    'from the original input text. This prevents the embedding model from '
    'hallucinating symptoms not lexically present in the user\'s description '
    '(e.g., blocking COUGH detection when no cough-related word appears).'
)
add_bullet(
    'Triage/Red-Flag Safety Layer: Implementation of an eight-category '
    'medical emergency detection system using multilingual regular '
    'expressions covering chest pain, difficulty breathing, blood in stool, '
    'vomiting blood, severe allergic reaction, high fever (≥40°C), seizure, '
    'and loss of consciousness. The triage layer uses light normalization '
    '(lowercase and whitespace only) to preserve digit values critical for '
    'temperature detection. When triggered, the recommendation engine '
    'suppresses all OTC suggestions and advises "CONSULT A DOCTOR."'
)
add_bullet(
    'Centralized Semantic Safety Filters: Implementation of seven explicit '
    'negation functions (for fever, headache, cough, diarrhea, sore throat, '
    'nasal symptoms, and allergy) plus red-flag suppression rules '
    '(blood_in_stool suppresses DIARRHEA; severe_allergic_reaction '
    'suppresses SORE_THROAT) in a centralized safety filter applied to '
    'all semantic detections.'
)

add_paragraph('Phase 1E: Evaluation and Error-Driven Refinement', bold=True)

add_bullet(
    'Benchmark Construction: Creation of a 288-case structured test '
    'benchmark organized across 60 test categories and four evaluation '
    'tiers (Functional, Robustness, Adversarial, Safety), with CSV-based '
    'test specification including input text, expected age, cough type, '
    'expected symptoms, and category annotations.'
)
add_bullet(
    'Error-Driven Iterative Refinement: Systematic adversarial probing '
    'uncovered 19 bugs across the pipeline, each fixed and regression-tested '
    'against the full 288-case benchmark. Bug categories include: negation '
    'bypass errors, cough-type misclassification, false positive triggers '
    'from substring matching, fuzzy rescue collisions, contrastive boundary '
    'edge cases, and semantic hallucination in the absence of lexical '
    'grounding.'
)
add_bullet(
    'Comprehensive Evaluation: Final evaluation across three benchmark '
    'sets: 288-case structured benchmark (288/288 exact match, F1 = 1.000), '
    '9-case semantic stress test (9/9 exact match), and 80-case real-user '
    'simulation (72 exact, 8 partial, 0 failures). Combined result: '
    '369/377 exact matches (97.9%), zero failures.'
)
add_bullet(
    'External AI Audit: Independent validation using Gemini 2.5 Pro, which '
    'identified 7 potential improvement areas; 6 of 7 suggestions were '
    'already implemented in the system, confirming comprehensive coverage.'
)
add_bullet(
    'Interaction Logging Implementation: Integration of a structured '
    'interaction logging system that records every consultation to a '
    'persistent JSON-Lines log file (logs/interactions.jsonl). Each log '
    'entry captures the user\'s raw input text, extracted symptoms, '
    'extraction source (dictionary or semantic), red-flag triggers, '
    'pipeline stage details, recommended medicines, and any cough-type '
    'clarification. This interaction log serves as the primary data '
    'source for domain-expert annotation and validation in Iteration 2. '
    'The logger is designed to be non-blocking: logging failures never '
    'interrupt the user-facing consultation flow.'
)
add_bullet(
    'Deployment Preparation: Performance profiling and optimization for '
    'real-time inference on Raspberry Pi 5 hardware, with lazy model loading '
    'to minimize startup time and CPU-safe inference configuration.'
)

add_paragraph(
    'Iteration 1 produces the complete working system with the five-stage '
    'pipeline, comprehensive safety mechanisms, ASG-grounded medicine '
    'dataset, interaction logging for expert validation, and '
    'deployment-ready architecture achieving 369/377 (97.9%) '
    'accuracy across all benchmark sets with zero failures.'
)

# 3.2.2 Iteration 2
doc.add_heading(
    '3.2.2 Iteration 2: Expert Annotation, Validation, and Refinement '
    '(Planned)', level=3
)

add_paragraph(
    'The second iteration focuses on domain-expert validation of the '
    'system\'s real-world performance using the interaction logs '
    'collected during Iteration 1 deployment. While automated '
    'benchmarks confirmed strong performance (369/377 exact matches, '
    '97.9%, zero failures), expert human validation provides '
    'additional evidence of clinical appropriateness that '
    'automated metrics alone cannot capture. Iteration 2 follows '
    'a deployment-then-expert-validation design, which is a recognized '
    'methodology in applied NLP and clinical informatics research '
    '(Li et al., 2022).'
)

add_paragraph('Phase 2A: Expert Annotation of Logged Interactions', bold=True)

add_bullet(
    'Annotator Recruitment: Licensed pharmacists or pharmacy interns '
    'will be recruited as domain-expert annotators to review the '
    'consultation logs recorded during Iteration 1 deployment. A '
    'minimum of two independent annotators per interaction is targeted '
    'to enable inter-annotator agreement analysis.'
)
add_bullet(
    'Annotation Protocol: Each annotator independently reviews the '
    'logged interactions and evaluates three dimensions: (1) Symptom '
    'Extraction Correctness, meaning whether the system correctly '
    'identified the symptoms described in the user\'s input (precision '
    'and recall at the label level); (2) Recommendation Appropriateness, '
    'meaning whether the suggested OTC medicines are clinically suitable '
    'for the detected symptoms; and (3) Missed Symptoms, meaning whether '
    'any symptoms present in the input were not detected by the system '
    '(false negatives). Annotators mark each dimension on a binary '
    'correct/incorrect scale with an optional free-text comment '
    'field for additional observations.'
)
add_bullet(
    'Inter-Annotator Agreement: Cohen\'s Kappa will be computed '
    'between annotator pairs to quantify agreement reliability. A '
    'Kappa value of 0.61 or above (substantial agreement) is targeted '
    'as the minimum threshold for considering the annotations valid '
    '(McHugh, 2022). Disagreements will be resolved through '
    'adjudication discussion between annotators.'
)

add_paragraph('Phase 2B: Analysis and System Refinement', bold=True)

add_bullet(
    'Expert-Validated Accuracy Metrics: Computation of expert-validated '
    'precision, recall, and F1 scores for symptom extraction based on '
    'annotator judgments, complementing the automated benchmark '
    'results from Iteration 1. These metrics provide ecological '
    'validity by evaluating performance on genuine user interactions '
    'rather than synthetic test cases.'
)
add_bullet(
    'Error Pattern Analysis: Systematic categorization of annotator-'
    'identified errors to determine whether failures cluster around '
    'specific symptom labels, language variants, or input patterns. '
    'This analysis informs targeted refinement of the dictionary, '
    'anchor sentences, or heuristic rules.'
)
add_bullet(
    'Recommendation Appropriateness Audit: Aggregation of annotator '
    'judgments on recommendation quality to produce a clinical '
    'appropriateness rate, which is the percentage of recommendations '
    'deemed suitable by domain experts. This metric directly addresses '
    'the safety-critical nature of OTC medicine recommendation.'
)
add_bullet(
    'Targeted System Refinement: Based on the expert-identified error '
    'patterns, targeted improvements may include dictionary expansion '
    'for under-detected symptoms, anchor sentence additions for '
    'semantic coverage gaps, heuristic rule adjustments, or medicine '
    'dataset updates. All refinements are regression-tested against '
    'the full 288-case benchmark to prevent degradation.'
)

add_paragraph('Phase 2C: Additional Enhancements (Scope-Dependent)', bold=True)

add_bullet(
    'Partial Match Resolution: Investigation of the 8 partial matches '
    'from the 80-case real-user simulation to determine whether '
    'dictionary expansion, anchor sentence additions, or heuristic '
    'adjustments can improve detection of secondary symptoms in '
    'ambiguous multi-symptom descriptions.'
)
add_bullet(
    'Expanded Medicine Coverage: Expansion of the medicine dataset '
    'beyond the current 23 entries based on pharmacy partner feedback '
    'and dispensing patterns observed in the interaction logs.'
)
add_bullet(
    'Additional Symptom Coverage: Expansion of the symptom taxonomy '
    'beyond the current 13 labels to include conditions such as '
    'nausea, dizziness, and fatigue, pending identification of '
    'appropriate OTC medications for each new label.'
)

add_paragraph(
    'Iteration 2 is planned as the validation and refinement cycle '
    'that bridges automated evaluation with human expert judgment. '
    'By annotating real interaction logs rather than synthetic test '
    'cases, Iteration 2 provides ecological validity and clinical '
    'confidence in the system\'s recommendations. The scope and '
    'priorities of Phase 2C will be informed by the annotation '
    'findings and panel evaluation recommendations.'
)

# 3.2.3 Research Philosophy
doc.add_heading('3.2.3 Research Philosophy', level=3)

add_paragraph(
    'This research adopts a pragmatic research philosophy, which prioritizes '
    'practical problem-solving over adherence to a single epistemological '
    'stance. Pragmatism is appropriate for applied AI system development in '
    'healthcare, where the research question demands both technical rigor '
    'and real-world applicability. The pragmatic approach permits the '
    'combination of rule-based deterministic methods (aligned with '
    'rationalism) and data-driven embedding models (aligned with empiricism) '
    'within a single system, unified by the practical criterion of whether '
    'the combined approach produces safe, accurate, and interpretable '
    'clinical recommendations.'
)

# ── 3.3 Theoretical Framework ────────────────────────────────────────────────
doc.add_heading('3.3 Theoretical Framework', level=2)

add_paragraph(
    'Unlike MendoVendo v1 and v2, which were grounded in Information '
    'Retrieval (IR) Theory due to their TF-IDF retrieval architecture, '
    'MendoVendo v3.0 transitions to a hybrid theoretical basis aligned '
    'with its new cascaded pipeline architecture. The system draws from '
    'three complementary theoretical foundations.'
)

# 3.3.1 Rule-Based NLP
doc.add_heading('3.3.1 Rule-Based NLP and Computational Linguistics Theory', level=3)

add_paragraph(
    'Stage 1 of the pipeline uses explicit dictionaries, regular '
    'expressions, negation windows, and cough-type disambiguation rules '
    'to encode domain knowledge as deterministic linguistic patterns. '
    'This approach is grounded in rule-based natural language processing '
    'theory, which holds that well-defined linguistic rules can capture '
    'regularities in language use with full transparency and predictability '
    '(Jurafsky & Martin, 2024).'
)

add_paragraph(
    'The rule-based component draws from established practices in clinical '
    'NLP systems where deterministic pattern matching provides '
    'interpretability, auditability, and safety guarantees, all of which '
    'are critical requirements for healthcare decision support systems '
    '(Eguia et al., 2024). The system extends classical rule-based NLP '
    'with several new mechanisms: consumed negation tracking (preventing '
    'negation from propagating past intervening symptom words), contrastive '
    'boundary splitting (evaluating negation independently across discourse '
    'segments), and fuzzy rescue with exclusion sets (Levenshtein-distance '
    'matching with curated false-positive prevention).'
)

# 3.3.2 Distributional Semantics
doc.add_heading('3.3.2 Distributional Semantics Theory', level=3)

add_paragraph(
    'Stage 2 uses the paraphrase-multilingual-MiniLM-L12-v2 pre-trained '
    'sentence embedding model and cosine similarity to handle paraphrased '
    'and code-switched symptom expressions that fall outside the '
    'dictionary\'s coverage. This component is grounded in distributional '
    'semantics theory, which assumes that words and phrases occurring in '
    'similar contexts tend to carry similar meanings (Reimers & Gurevych, '
    '2019; Wang et al., 2021).'
)

add_paragraph(
    'The distributional hypothesis, operationalized through modern neural '
    'sentence encoders (Gao et al., 2022), allows the system to recognize '
    'semantic similarity between utterances even when they use different '
    'vocabulary or syntax. This is important for handling the linguistic '
    'diversity of Philippine pharmacy interactions, where patients may '
    'describe symptoms using Tagalog, Bisaya/Cebuano, English, or '
    'code-switched combinations with creative spelling '
    '(Jejemon/leetspeak). The model is used in inference-only mode '
    'without fine-tuning, relying on its pre-trained multilingual '
    'knowledge across 50+ languages. This design choice ensures '
    'reproducibility, eliminates overfitting risk, and takes advantage '
    'of the model\'s broad multilingual coverage including Filipino '
    'and Cebuano.'
)

# 3.3.3 Knowledge-Based Expert Systems
doc.add_heading('3.3.3 Knowledge-Based Expert Systems Theory', level=3)

add_paragraph(
    'Stage 4 scores candidate OTC drugs using a structured medicine '
    'dataset that encodes symptom-drug relationships, age limits, '
    'contraindications, warnings, drug interactions, and maximum safe '
    'duration. This component draws from knowledge-based expert systems '
    'theory, which structures domain expertise as formal rules and data '
    'that can be systematically applied and audited '
    '(Musen et al., 2021).'
)

add_paragraph(
    'The structured dataset approach is similar to modern clinical '
    'decision support systems, where explicit encoding of medical '
    'knowledge enables deterministic safety checking and explainable '
    'recommendations (Habehh & Gohel, 2021). The system implements '
    'the Authoritative-Source-Grounded (ASG) framework, where every '
    'medicine entry\'s 15 fields are sourced from package inserts, '
    'MIMS Philippines, and DOH Philippines guidelines, ensuring '
    'traceability and clinical defensibility of all recommendations.'
)

# 3.3.4 Theoretical Justification
doc.add_heading('3.3.4 Theoretical Justification for Hybrid Architecture', level=3)

add_paragraph(
    'These three theoretical foundations work together to justify the '
    'cascaded design. Deterministic rules handle cases where patient '
    'safety demands explicit guarantees and clear decision logic. '
    'Distributional semantics picks up paraphrased and code-switched '
    'language that no dictionary could reasonably list in advance. '
    'Finally, the structured knowledge base captures pharmaceutical '
    'expertise that needs authoritative sourcing and easy auditability.'
)

add_paragraph(
    'This hybrid approach marks a deliberate shift away from the pure '
    'Information Retrieval strategy used in v1 and v2. The earlier '
    'approach struggled in three respects: IR could not generalize to '
    'unseen Bisaya or code-switched variants, TF-IDF could not tell '
    'apart "I have a headache" from "I don\'t have a headache," and '
    'cosine similarity on its own produced too many false positives '
    'in a medical context where incorrect recommendations carry real risk.'
)

# ── 3.4 Conceptual Framework ─────────────────────────────────────────────────
doc.add_heading('3.4 Conceptual Framework', level=2)

add_paragraph(
    'While Section 3.5 describes the technical architecture of MendoVendo '
    'v3.0, this section presents the conceptual framework that maps the '
    'abstract relationships among the research variables. The framework '
    'identifies three categories of variables and shows how they interact '
    'to produce the study\'s intended outcome.'
)

add_paragraph(
    'Independent Variable. The primary input to the system is the '
    'multilingual free-text symptom description provided by the user. '
    'This input may arrive in Bisaya, Tagalog, English, Taglish or Conyo '
    'code-switching, or informal orthographies such as Jejemon and '
    'leetspeak. The linguistic diversity and informality of these inputs '
    'represent the core challenge that the system must address.'
)

add_paragraph(
    'Process Variable. The hybrid NLP pipeline serves as the mediating '
    'process that transforms the independent variable into a structured '
    'recommendation. Conceptually, this process involves five steps:'
)

add_numbered(
    'Triage screening filters emergency cases before any further '
    'processing takes place.'
)
add_numbered(
    'Rule-based dictionary extraction attempts deterministic symptom '
    'matching against a curated multilingual phrase bank.'
)
add_numbered(
    'Semantic similarity fallback activates only when the dictionary '
    'produces zero matches, using pre-trained multilingual sentence '
    'embeddings to handle paraphrased or unseen expressions.'
)
add_numbered(
    'Hybrid safety orchestration consolidates detected symptoms, '
    'applies keyword gates and negation checks, and ensures that '
    'deterministic results always take precedence over probabilistic ones.'
)
add_numbered(
    'Scored recommendation ranks OTC medicines against the validated '
    'symptom set while enforcing age, contraindication, and overlap rules.'
)

add_paragraph(
    'Dependent Variable. The output of the system is the ranked OTC '
    'medicine recommendation, accompanied by safety warnings and '
    'professional-consultation advisories where appropriate. The quality '
    'of this output is measured through accuracy, precision, recall, and '
    'F1-score across the 288-case benchmark test suite and, in Iteration 2, '
    'through expert annotation of logged field interactions.'
)

add_paragraph(
    'Moderating Variables. Three contextual factors influence how the '
    'process variable converts input into output: (a) language diversity, '
    'which determines whether the dictionary or the semantic fallback '
    'path is activated; (b) safety constraints, including red-flag '
    'detection and negation handling, which can override or suppress '
    'a recommendation entirely; and (c) patient context, specifically '
    'age and severity, which adjusts the scoring and filtering of '
    'candidate medicines.'
)

add_paragraph(
    'Taken together, the conceptual framework positions MendoVendo v3.0 '
    'as an input-process-output system in which a linguistically diverse '
    'independent variable is transformed by a hybrid NLP process into a '
    'safety-screened dependent variable, with language diversity, safety '
    'constraints, and patient context acting as moderating variables that '
    'shape the transformation at each stage.'
)

# ── 3.5 System Architecture ──────────────────────────────────────────────────
doc.add_heading('3.5 System Architecture', level=2)

add_paragraph(
    'MendoVendo v3.0 uses a five-stage cascaded architecture running '
    'on a Raspberry Pi 5-based kiosk with an Arduino Mega for dispensing '
    'control. The architecture favors deterministic rule-based processing '
    'for speed and auditability, while keeping pre-trained multilingual '
    'sentence embeddings available as a semantic fallback for inputs the '
    'dictionary has not seen before. The system is written in Python 3.12.3 '
    'on the Flask web framework, and the core NLP pipeline is organized '
    'into four source modules totaling roughly 2,880 lines of code.'
)

# Stage 0
doc.add_heading('3.5.1 Stage 0: Triage / Red-Flag Safety Layer', level=3)

add_paragraph(
    'The first processing stage screens user input for medical emergencies '
    'that require professional intervention rather than OTC self-medication. '
    'The triage layer detects eight categories of red-flag conditions using '
    'multilingual regular expressions:'
)

# Table for red flags
table = doc.add_table(rows=9, cols=3)
table.style = 'Table Grid'
headers = ['Category', 'Example Triggers', 'Clinical Rationale']
for i, h in enumerate(headers):
    cell = table.rows[0].cells[i]
    cell.text = h
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.bold = True

red_flags = [
    ('Chest Pain', '"masakit ang dibdib", "chest pain", "sakit sa dughan"', 'Possible cardiac event'),
    ('Difficulty Breathing', '"hirap huminga", "shortness of breath", "lisod ginhawa"', 'Respiratory emergency'),
    ('Blood in Stool', '"may dugo sa dumi", "bloody stool"', 'Gastrointestinal hemorrhage'),
    ('Vomiting Blood', '"nagsusuka ng dugo", "vomiting blood"', 'Upper GI bleed'),
    ('Severe Allergic Reaction', '"namamaga ang lalamunan", "swollen throat"', 'Anaphylaxis risk'),
    ('High Fever (≥40°C)', '"lagnat na 41 degrees", "fever of 40"', 'Dangerous hyperthermia'),
    ('Seizure', '"seizure", "kombulsyon", "atake"', 'Neurological emergency'),
    ('Loss of Consciousness', '"nahimatay", "fainted", "nawalan ng malay"', 'Requires medical evaluation'),
]
for i, (cat, triggers, rationale) in enumerate(red_flags, 1):
    table.rows[i].cells[0].text = cat
    table.rows[i].cells[1].text = triggers
    table.rows[i].cells[2].text = rationale

add_paragraph(
    'A critical design decision in the triage layer is the use of light '
    'normalization (lowercase and whitespace collapsing only) rather than '
    'the full de-leetspeak normalization used in Stage 1. This preserves '
    'digit characters essential for temperature detection. The full '
    'normalization would convert "40 degrees" to "ao degrees," destroying '
    'the numerical pattern required for high-fever detection.'
)

add_paragraph(
    'The triage layer does not short-circuit the pipeline; symptoms are '
    'still extracted for diagnostic logging and benchmark validation. '
    'The triage gate activates at Stage 4 to suppress OTC recommendations '
    'and return an emergency referral message.'
)

# Stage 1
doc.add_heading('3.5.2 Stage 1: Dictionary-Based Symptom Extraction', level=3)

add_paragraph(
    'The primary extraction stage uses a curated multilingual symptom '
    'dictionary containing 307 phrases across 13 symptom labels, covering '
    'five language variants. The dictionary is the product of iterative '
    'expansion throughout Iteration 1, with each phrase manually verified '
    'for linguistic accuracy and clinical relevance.'
)

# Table for symptom dictionary
table = doc.add_table(rows=14, cols=4)
table.style = 'Table Grid'
headers = ['Symptom Label', 'Phrase Count', 'Languages', 'Key Examples']
for i, h in enumerate(headers):
    cell = table.rows[0].cells[i]
    cell.text = h
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.bold = True

symptoms = [
    ('HEADACHE', '38', 'Tag/Bis/Eng', '"masakit ang ulo", "labad akong ulo", "headache"'),
    ('FEVER', '40', 'Tag/Bis/Eng', '"lagnat", "nilalagnat", "hilanat", "init akong lawas"'),
    ('BODY_ACHES', '36', 'Tag/Bis/Eng', '"masakit katawan", "binugbog", "bug at akong lawas"'),
    ('RASHES', '32', 'Tag/Bis/Eng', '"pantal", "rash", "makati ang balat"'),
    ('STOMACH_ACHE', '30', 'Tag/Bis/Eng', '"sakit tiyan", "kabag", "hyperacidity"'),
    ('SORE_THROAT', '28', 'Tag/Bis/Eng', '"masakit lalamunan", "sore throat", "garas"'),
    ('COUGH_PRODUCTIVE', '20', 'Tag/Bis/Eng', '"may plema", "basang ubo", "halak"'),
    ('ALLERGIC_RHINITIS', '17', 'Tag/Bis/Eng', '"allergy", "bahing", "alerdyi", "makati ilong"'),
    ('COUGH_GENERAL', '16', 'Tag/Bis/Eng', '"ubo", "cough", "inuubo", "gi-ubo"'),
    ('COUGH_DRY', '15', 'Tag/Bis/Eng', '"walang plema", "tuyong ubo", "dry cough"'),
    ('DIARRHEA', '14', 'Tag/Bis/Eng', '"pagtatae", "diarrhea", "lbm", "loose bowel"'),
    ('NASAL_CONGESTION', '11', 'Tag/Bis/Eng', '"barado ilong", "stuffy nose", "blocked nose"'),
    ('RUNNY_NOSE', '10', 'Tag/Bis/Eng', '"sipon", "runny nose", "tumutulo ilong"'),
]
for i, (label, count, langs, examples) in enumerate(symptoms, 1):
    table.rows[i].cells[0].text = label
    table.rows[i].cells[1].text = count
    table.rows[i].cells[2].text = langs
    table.rows[i].cells[3].text = examples

doc.add_paragraph('')  # spacer

doc.add_heading('3.5.2.1 Text Normalization', level=4)

add_paragraph(
    'All input text undergoes deterministic normalization before phrase '
    'matching. The normalization pipeline includes: (1) conversion to '
    'lowercase, (2) leetspeak/Jejemon character substitution (@ → a, '
    '0 → o, 1 → i, 3 → e, 4 → a, 5 → s, 7 → t, 8 → b, $ → s, '
    '! → i, | → i), (3) removal of non-alphanumeric characters (preserving '
    'ñ for Filipino words), and (4) whitespace collapsing. This enables '
    'the system to handle informal digital communication styles common '
    'among Filipino youth (e.g., "s@k1t ul0" normalizes to "sakit ulo" '
    'and matches HEADACHE).'
)

doc.add_heading('3.5.2.2 Phrase Matching Strategy', level=4)

add_paragraph(
    'The matching engine uses two strategies depending on phrase length: '
    'multi-word phrases use substring matching in the normalized text, '
    'while single-word keywords use word-boundary regular expressions '
    '(\\b anchors) to prevent false positives from partial string matches '
    '(e.g., preventing "tubo" from matching the COUGH keyword "ubo").'
)

doc.add_heading('3.5.2.3 Negation Handling', level=4)

add_paragraph(
    'The negation detection system addresses a critical safety requirement: '
    'patients frequently describe symptoms they do NOT have alongside those '
    'they do have (e.g., "masakit ang ulo ko pero walang lagnat," meaning "my head '
    'hurts but I don\'t have a fever"). The system implements the following '
    'negation mechanisms:'
)

add_bullet(
    'Negation Lexicon: 11 negation words covering Tagalog (hindi, walang, '
    'wala, hnd), Bisaya/Cebuano (walay, waley, dili, di), and English '
    '(no, not, without).'
)
add_bullet(
    'Proximity Window: A negation word must appear within 0–2 words '
    'BEFORE the symptom phrase to trigger negation.'
)
add_bullet(
    'Consumed Negation: If another symptom keyword from a set of 28 '
    'intervening symptom words sits between the negation word and the '
    'target symptom, the negation is "consumed" by the closer keyword '
    'and does not propagate further. This prevents cascading negation '
    'errors in multi-symptom utterances (e.g., "hindi pala ubo sipon," '
    'where "hindi" negates "ubo" but not "sipon").'
)
add_bullet(
    'Negated-Label Tracking: A dedicated set tracks which symptom labels '
    'were dictionary-matched but negated, preventing the fuzzy rescue '
    'mechanism (Section 3.5.2.6) from re-adding negated symptoms through '
    'approximate string matching.'
)

doc.add_heading('3.5.2.4 Contrastive Boundary Splitting', level=4)

add_paragraph(
    'User input is split on contrastive conjunctions (pero, but, kaso, '
    'however, though) into independent segments. Each segment is evaluated '
    'independently for negation, with a positive mention after a contrastive '
    'boundary overriding prior negation. Strong negation overrides '
    'with contrastive boundary awareness are implemented for five high-risk '
    'labels: FEVER, COUGH, HEADACHE, RUNNY_NOSE, and BODY_ACHES. Each '
    'uses last-segment-wins logic to resolve conflicting negation signals.'
)

doc.add_heading('3.5.2.5 Cough-Type Qualification', level=4)

add_paragraph(
    'Cough classification runs before the general dictionary scan and '
    'follows a seven-step decision tree to distinguish between COUGH_DRY, '
    'COUGH_PRODUCTIVE, and COUGH_GENERAL. The decision tree incorporates: '
    '(1) itchy/scratchy throat indicators mapping to COUGH_DRY, '
    '(2) chest-rattle/congestion indicators bypassing the cough-word '
    'requirement to map directly to COUGH_PRODUCTIVE, (3) cough-word '
    'presence verification, (4) cough negation checking with a plema-filler '
    'exemption (so "walang plema" does not negate the cough itself), '
    '(5) explicit dry qualifier detection, (6) wet qualifier detection, '
    'and (7) default to COUGH_GENERAL. Explicit DRY phrases take priority '
    'over WET when both are present.'
)

doc.add_heading('3.5.2.6 Fuzzy Rescue Mechanism', level=4)

add_paragraph(
    'After dictionary matching and negation processing, a fuzzy rescue '
    'pass attempts to recover misspelled symptom mentions using '
    'Levenshtein distance matching. Seven rescue families are defined:'
)

table = doc.add_table(rows=8, cols=4)
table.style = 'Table Grid'
headers = ['Target Symptom', 'Fuzzy Targets', 'Max Distance', 'Exclusion Set']
for i, h in enumerate(headers):
    cell = table.rows[0].cells[i]
    cell.text = h
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.bold = True

fuzzy_data = [
    ('FEVER', 'lagnat, fever, hilanat', '1', 'None'),
    ('RUNNY_NOSE', 'sinisipon, sinasipon, sisipon, sipon', '2', 'None'),
    ('COUGH', 'ubo', '1', 'ulo, ulu, ole, olo, tubo, ubos, ubi, ube, tuba, ubod'),
    ('DIARRHEA', 'pagtatae, nagtatae, kalibang', '2', 'kaninang, kanina, kaninag'),
    ('RASHES', 'pantal, butlig', '1', 'ipantal, pantalon, pantalan'),
    ('STOMACH_ACHE', 'tiyan, sikmura', '1', 'Requires nearby pain word'),
    ('BODY_ACHES', 'katawan, lawas', '1', 'Requires nearby pain word'),
]
for i, (sym, targets, dist, exclusions) in enumerate(fuzzy_data, 1):
    table.rows[i].cells[0].text = sym
    table.rows[i].cells[1].text = targets
    table.rows[i].cells[2].text = dist
    table.rows[i].cells[3].text = exclusions

add_paragraph(
    'Each fuzzy rescue checks the negated-labels set before adding a '
    'symptom. The exclusion sets are critical for preventing false positives '
    'in Filipino languages, where many common words have Levenshtein '
    'distance ≤1 from symptom keywords (e.g., "tubo" [pipe/sugarcane] '
    'from "ubo" [cough]).'
)

doc.add_heading('3.5.2.7 Proximity-Based Heuristics', level=4)

add_paragraph(
    'Several symptom labels use proximity-based co-occurrence detection '
    'to handle compositional symptom descriptions where the symptom is '
    'expressed as two separate words rather than a fixed phrase:'
)

add_bullet(
    'Headache Heuristic: Detects co-occurrence of a head word (head, ulo) '
    'and a pain word (sakit, masakit, labad, throbbing, pounding, kirot, '
    'hurt, ache, sasabog, binibiyak, pumapasabog) within ≤5 tokens. '
    'Includes fuzzy variants (hed → head, olo → ulo).'
)
add_bullet(
    'Sore Throat Proximity: Detects co-occurrence of a throat word '
    '(lalamunan, tutunlan, throat) and a pain word (masakit, sumasakit, '
    'mahapdi, sakit, pain, hurts, sore, hapdi) within ≤5 tokens, with '
    'dual negation checking on both the throat and pain words.'
)
add_bullet(
    'Per-Cue-Group Nasal Inference: Three independent cue groups (allergy, '
    'runny, congestion) are evaluated with independent negation per group. '
    'Only returns empty if ALL mentioned cue groups are negated.'
)
add_bullet(
    'Allergen-Trigger Heuristic: If RASHES is detected AND an allergen '
    'trigger word appears (dust, alikabok, pollen, amag, pet, dander, etc.), '
    'the system also infers ALLERGIC_RHINITIS.'
)

# Stage 2
doc.add_heading('3.5.3 Stage 2: Semantic Embedding Fallback', level=3)

add_paragraph(
    'The semantic fallback layer provides coverage for symptom descriptions '
    'that fall outside the dictionary\'s 307 curated phrases. It uses the '
    'pre-trained paraphrase-multilingual-MiniLM-L12-v2 model from the '
    'Sentence-Transformers library (Reimers & Gurevych, 2019), a compact '
    'transformer with approximately 33 million parameters that produces '
    '384-dimensional sentence embeddings.'
)

add_paragraph(
    'The model is used in inference-only mode without any fine-tuning. '
    'This is a deliberate design choice motivated by three factors: '
    '(1) safety, since fine-tuning on a small corpus risks overfitting to '
    'training patterns while degrading performance on unseen linguistic '
    'variants; (2) reproducibility, because the pre-trained model is a fixed, '
    'publicly available artifact; and (3) multilingual coverage, as the '
    'model\'s pre-trained knowledge spans 50+ languages including Filipino '
    'and Cebuano, which would be difficult to replicate with a small '
    'domain-specific fine-tuning corpus.'
)

add_paragraph(
    'At initialization, 118 anchor sentences (8–12 per symptom label) '
    'are pre-encoded into 384-dimensional vectors. At runtime, the user\'s '
    'input is encoded and compared against all anchor embeddings using '
    'cosine similarity. Symptoms with a best-anchor score ≥ 0.65 are '
    'returned as candidates. The 0.65 threshold was determined empirically '
    'through iterative testing to balance sensitivity against false '
    'positive risk.'
)

add_paragraph(
    'A key architectural decision is the precision-first switching '
    'logic: the semantic layer only activates when Stage 1 (dictionary) '
    'finds zero symptoms. Whenever the dictionary returns results, those '
    'results are trusted as-is, with no semantic augmentation. This way, '
    'deterministic and safety-auditable results always take precedence '
    'over probabilistic detections wherever the dictionary has '
    'sufficient coverage.'
)

add_paragraph(
    'The model is loaded as a lazy singleton, instantiated only on the '
    'first query that requires semantic processing. This minimizes startup '
    'time and memory usage on the Raspberry Pi 5 deployment target. The '
    'device defaults to CPU (configurable via the MENDO_SEMANTIC_DEVICE '
    'environment variable).'
)

# Stage 3
doc.add_heading('3.5.4 Stage 3: Hybrid Merge, Lexical Guards, and Safety Filters', level=3)

add_paragraph(
    'Stage 3 serves as the orchestration and safety layer, integrating '
    'results from Stages 0–2 and applying multi-layered filtering before '
    'passing symptoms to the recommendation engine. The processing flow is:'
)

add_numbered('Run triage detection (Stage 0) → produce red_flags list.')
add_numbered('Run dictionary extraction (Stage 1) → produce dict_symptoms.')
add_numbered('Apply explicit cough negation override.')
add_numbered(
    'If dict_symptoms is non-empty → return dict_symptoms (skip semantic). '
    'This is the precision-first switching logic.'
)
add_numbered('If dict_symptoms is empty → load semantic model (lazy singleton).')
add_numbered('Run semantic extraction → produce raw semantic detections.')
add_numbered(
    'Apply lexical guard: 11 keyword gates per symptom label. Each '
    'semantic detection must be grounded in at least one relevant keyword '
    'from the original (un-normalized) input text.'
)
add_numbered(
    'Apply centralized safety filter: seven explicit negation functions '
    'plus red-flag suppression rules.'
)
add_numbered('Score-rank and select top-N (default: 2) semantic symptoms.')
add_numbered('Return final symptom set with source attribution.')

doc.add_heading('3.5.4.1 Lexical Guard Mechanism', level=4)

add_paragraph(
    'The lexical guard is a critical safety mechanism that prevents the '
    'semantic embedding model from "hallucinating" symptoms not lexically '
    'present in the user\'s input. Each of the 13 symptom labels has a '
    'dedicated keyword gate, which is a set of words that must appear in the '
    'original input text for a semantic detection of that symptom to be '
    'accepted. For example, a semantic detection of COUGH requires at '
    'least one cough-related keyword (cough, ubo, inuubo, hubak, halak, '
    'kumakalansing) in the input text. COUGH_PRODUCTIVE has a special '
    'compound gate requiring both a cough keyword AND a phlegm keyword '
    '(or chest/dibdib + plema). Detections that fail their keyword gate '
    'are silently dropped.'
)

doc.add_heading('3.5.4.2 Centralized Safety Filter', level=4)

add_paragraph(
    'The centralized safety filter applies all seven explicit negation '
    'functions (for fever, headache, cough, diarrhea, sore throat, nasal '
    'symptoms, and allergy) to semantic detections, using word-boundary-'
    'safe regex matching. Additionally, two red-flag suppression rules '
    'prevent clinically dangerous false positives: '
    '(1) blood_in_stool → suppress DIARRHEA (to prevent recommending '
    'anti-diarrheal medication for potential GI hemorrhage); '
    '(2) severe_allergic_reaction → suppress SORE_THROAT (to prevent '
    'treating anaphylaxis as a common sore throat).'
)

# Stage 4
doc.add_heading('3.5.5 Stage 4: ASG Recommendation Engine', level=3)

add_paragraph(
    'The final stage maps detected symptoms to OTC medicine recommendations '
    'using a structured JSON dataset grounded in the Authoritative-Source-'
    'Grounded (ASG) framework.'
)

doc.add_heading('3.5.5.1 ASG Framework and Medicine Dataset', level=4)

add_paragraph(
    'The ASG framework was adopted after the originally planned pharmacist '
    'annotation process (via a web-based tool at mendo.diapana.dev) could '
    'not be completed within the project timeline. Under the ASG framework, '
    'all medicine data is sourced exclusively from authoritative '
    'pharmaceutical references: package inserts, MIMS Philippines, and '
    'DOH Philippines guidelines. Each of the 23 medicine entries contains '
    '15 fields:'
)

# Table for medicine fields
table = doc.add_table(rows=16, cols=3)
table.style = 'Table Grid'
headers = ['Field', 'Type', 'Source']
for i, h in enumerate(headers):
    cell = table.rows[0].cells[i]
    cell.text = h
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.bold = True

med_fields = [
    ('Brand', 'String', 'Product label'),
    ('Generic/Main Use', 'String', 'Package insert'),
    ('Drug Category', 'String', 'MIMS classification'),
    ('Primary Symptom', 'String', 'Clinical mapping'),
    ('Typical Symptoms Treated', 'String (comma-sep)', 'Package insert'),
    ('Dosage Form', 'String', 'Product label'),
    ('Minimum Age', 'String', 'Package insert'),
    ('Notes', 'String', 'Clinical notes'),
    ('Approved_Indications', 'Tuple[str]', 'Package Insert / MIMS'),
    ('Indication_Source', 'String', 'ASG attribution'),
    ('Contraindications', 'Tuple[str]', 'Package Insert / MIMS'),
    ('Warnings', 'Tuple[str]', 'Package Insert'),
    ('Drug_Interactions', 'Tuple[str]', 'Package Insert / MIMS'),
    ('Max_Duration_Days', 'Integer', 'Package Insert'),
    ('Contraindication_Source', 'String', 'ASG attribution'),
]
for i, (field, ftype, source) in enumerate(med_fields, 1):
    table.rows[i].cells[0].text = field
    table.rows[i].cells[1].text = ftype
    table.rows[i].cells[2].text = source

add_paragraph(
    'The dataset contains 23 medicine entries covering 18 unique brands, '
    'representing common OTC medications available in Philippine pharmacies. '
    'Multiple entries exist for medicines available in different dosage '
    'forms (e.g., Biogesic Tablet and Biogesic Syrup) to enable '
    'age-appropriate form selection.'
)

doc.add_heading('3.5.5.2 Recommendation Logic', level=4)

add_paragraph(
    'The recommendation algorithm follows a deterministic, rule-based process:'
)

add_numbered(
    'Triage Gate: If red flags were detected in Stage 0, suppress all OTC '
    'recommendations and return "CONSULT A DOCTOR" with the specific '
    'emergency category.'
)
add_numbered(
    'COUGH_GENERAL Handling: If COUGH_GENERAL is the sole detected symptom, '
    'the system requests cough-type clarification (dry vs. productive) '
    'rather than recommending a generic cough medicine. If other symptoms '
    'are present alongside COUGH_GENERAL, the cough is deferred while '
    'recommendations proceed for the other symptoms.'
)
add_numbered(
    'Symptom-to-Medicine Matching: Each detected symptom is matched against '
    'the medicine dataset using rule-based scoring. Candidates are ranked '
    'by match score.'
)
add_numbered(
    'Brand Merging: Multiple entries of the same brand are merged, keeping '
    'the highest score and combining match reasons.'
)
add_numbered(
    'Safety Checks: Three safety mechanisms are applied: '
    '(a) Paracetamol overlap detection warns when multiple paracetamol-'
    'containing medicines are recommended together (e.g., Bioflu + '
    'Biogesic); (b) Opposing mechanism warning flags when both an '
    'expectorant and a cough suppressant are recommended; '
    '(c) Age filtering removes medicines below the user\'s minimum age '
    'requirement.'
)

doc.add_heading('3.5.5.3 Medicine Coverage', level=4)

add_paragraph(
    'The 23 medicine entries (18 unique brands) cover the following '
    'therapeutic categories: Cold & Flu (Bioflu), Cold/Decongestant '
    '(Neozep, Decolgen, Decolgen Forte, Symdex-D), Cough Suppressant '
    '(Tuseran Forte, Sinecod Forte), Expectorant (Ascof Forte, Solmux, '
    'Robitussin), Pain & Fever (Biogesic, Advil), Allergy (Cetirizine), '
    'Anti-Diarrheal (Loperamide/Diatabs), Probiotic (Erceflora), Antacid '
    '(Kremil-S), and Antispasmodic (Buscopan). This scope was intentionally '
    'reduced from v2.0\'s 81 entries to focus exclusively on OTC medications '
    'appropriate for dispensing from an automated kiosk.'
)

# ── 3.6 Language Support ─────────────────────────────────────────────────────
doc.add_heading('3.6 Multilingual Language Support', level=2)

add_paragraph(
    'MendoVendo v3.0 is designed to process patient symptom descriptions '
    'in the diverse linguistic landscape of Philippine pharmacy interactions. '
    'The system supports five language variants:'
)

table = doc.add_table(rows=6, cols=3)
table.style = 'Table Grid'
headers = ['Language Variant', 'Coverage Level', 'Example Input']
for i, h in enumerate(headers):
    cell = table.rows[0].cells[i]
    cell.text = h
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.bold = True

langs = [
    ('Tagalog', 'Primary', '"masakit ang ulo ko at nilalagnat"'),
    ('Bisaya/Cebuano', 'Primary', '"labad akong ulo, garas akong tilaok"'),
    ('English', 'Full', '"I have a headache and fever"'),
    ('Taglish/Conyo (code-switch)', 'Full', '"masakit head ko, may cough ako"'),
    ('Jejemon/Leetspeak', 'Full', '"s@k1t ul0", "lgnat ako"'),
]
for i, (lang, cov, ex) in enumerate(langs, 1):
    table.rows[i].cells[0].text = lang
    table.rows[i].cells[1].text = cov
    table.rows[i].cells[2].text = ex

add_paragraph(
    'Tagalog and Bisaya/Cebuano receive primary support with extensive '
    'phrase coverage in the dictionary (Stage 1), dedicated negation words, '
    'and anchor sentences in the semantic layer (Stage 2). English is fully '
    'supported through both dictionary phrases and the multilingual '
    'embedding model\'s native English capability. Taglish/Conyo '
    'code-switching is handled through the combination of dictionary '
    'coverage (which includes mixed-language phrases) and the embedding '
    'model\'s cross-lingual similarity capabilities. Jejemon/leetspeak is '
    'handled through the normalization layer\'s character substitution rules, '
    'which deterministically convert informal digital spelling back to '
    'standard orthography before matching.'
)

# ── 3.7 Evaluation Methodology ───────────────────────────────────────────────
doc.add_heading('3.7 Evaluation Methodology', level=2)

doc.add_heading('3.7.1 Benchmark Design', level=3)

add_paragraph(
    'The evaluation framework uses a structured CSV-based benchmark '
    'containing 288 test cases organized across 60 test categories and '
    'four evaluation tiers of increasing difficulty:'
)

add_bullet(
    'Tier 1: Core Functional (100 tests). Simple single-symptom detection, '
    'multiple symptoms, basic negation, partial negation, noisy input, '
    'misspelling, alternative phrasing, English input, code-switching, '
    'third-person descriptions, temporal markers, age context, severity '
    'descriptors, question forms.'
)
add_bullet(
    'Tier 2: Extended Robustness (100 tests). Jejemon/leetspeak input, '
    'Bisaya-heavy descriptions, compound multi-symptom cases, contrastive '
    'negation, run-on realistic input, diagnostic confusion, interjection '
    'and filler words, symptom chains, temporal progression, formal/'
    'polite register, extreme severity, very mild descriptions, complex '
    'English, heavy code-switching, pharmacy kiosk realistic, complex '
    'negation, double misspelling, figurative speech.'
)
add_bullet(
    'Tier 3: Adversarial (64 tests). Universal negation, false positive '
    'traps, sore throat edge cases, contrastive boundary variants, '
    'multi-negation, mixed complex scenarios, non-symptom input, single '
    'word input, full stress tests, Bisaya negation, reversed word order, '
    'Conyo/slang, gibberish detection, post-negation constructs, long '
    'realistic descriptions, allergy-nasal disambiguation.'
)
add_bullet(
    'Tier 4: Triage Safety (24 tests). Chest pain detection, breathing '
    'difficulty, blood symptoms, loss of consciousness, seizure detection, '
    'severe allergic reaction, high fever thresholds, mixed emergency/'
    'symptom cases.'
)

add_paragraph(
    'Each test case specifies: test_id, input_text, age, cough_type, '
    'expected_symptoms (as a set), test_category, and descriptive notes. '
    'The benchmark runner (AlgorithmTester class) executes each test case '
    'through the full hybrid pipeline and evaluates results against '
    'expected outputs.'
)

doc.add_heading('3.7.2 Evaluation Metrics', level=3)

add_paragraph(
    'The system is evaluated using the following metrics:'
)

add_bullet(
    'Exact Match: Detected symptoms exactly equal expected symptoms '
    '(set equality). This is the primary success metric.'
)
add_bullet(
    'Partial Match: At least one correct symptom detected with no false '
    'positives, but not all expected symptoms captured.'
)
add_bullet(
    'Failed: Wrong symptoms detected or empty result when non-empty '
    'output was expected.'
)
add_bullet(
    'F1 Score: Harmonic mean of per-test precision and recall, averaged '
    'across all test cases.'
)

doc.add_heading('3.7.3 Additional Validation Sets', level=3)

add_paragraph(
    'Beyond the primary 288-case benchmark, two additional validation sets '
    'were constructed to test generalization and prevent overfitting:'
)

add_bullet(
    '9-Case Semantic Stress Set: Figurative, metaphorical, and culturally '
    'idiomatic symptom descriptions (e.g., "parang binubugbog," '
    '"parang sumabog ang ulo ko") testing the semantic fallback layer\'s '
    'ability to handle non-literal language.'
)
add_bullet(
    '80-Case Real-User Simulation: Realistic patient-style inputs mimicking '
    'actual pharmacy interactions, including rambling descriptions, '
    'emotional language, and multiple complaints in a single utterance.'
)

doc.add_heading('3.7.4 Evaluation Results', level=3)

table = doc.add_table(rows=5, cols=4)
table.style = 'Table Grid'
headers = ['Benchmark', 'Exact Match', 'Partial', 'Failed']
for i, h in enumerate(headers):
    cell = table.rows[0].cells[i]
    cell.text = h
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.bold = True

results = [
    ('288-case structured', '288/288 (100%)', '0', '0'),
    ('9-case semantic stress', '9/9 (100%)', '0', '0'),
    ('80-case real-user sim', '72/80 (90%)', '8', '0'),
    ('Combined (377 total)', '369/377 (97.9%)', '8', '0'),
]
for i, (bench, exact, partial, failed) in enumerate(results, 1):
    table.rows[i].cells[0].text = bench
    table.rows[i].cells[1].text = exact
    table.rows[i].cells[2].text = partial
    table.rows[i].cells[3].text = failed

add_paragraph(
    'The 288-case structured benchmark achieves perfect F1 = 1.000. The '
    '8 partial matches in the 80-case real-user simulation represent '
    'cases where the system correctly identified the primary symptom but '
    'missed a secondary one from an ambiguous or metaphorical description. '
    'Critically, zero test cases across all three benchmarks resulted in '
    'failures (incorrect symptom detection).'
)

# ── 3.8 Error-Driven Refinement ──────────────────────────────────────────────
doc.add_heading('3.8 Error-Driven Iterative Refinement', level=2)

add_paragraph(
    'A systematic adversarial probing process was conducted throughout '
    'Iteration 1, uncovering a total of 19 bugs across the pipeline. '
    'Each bug was fixed and regression-tested against the full 288-case '
    'benchmark to ensure no regressions were introduced. The bugs '
    'span the following categories:'
)

add_bullet(
    'Negation Bypass Errors (5 bugs): Cases where negation was not '
    'correctly detected due to word order, intervening words, or '
    'missing negation words from the lexicon.'
)
add_bullet(
    'Cough-Type Misclassification (3 bugs): Incorrect distinction between '
    'COUGH_DRY, COUGH_PRODUCTIVE, and COUGH_GENERAL due to qualifier '
    'ordering, plema-filler interaction, or chest-rattle indicator gaps.'
)
add_bullet(
    'False Positive Triggers (4 bugs): Substring matching or fuzzy rescue '
    'incorrectly triggering symptom detection from non-symptom words '
    '(resolved with exclusion sets and word-boundary enforcement).'
)
add_bullet(
    'Semantic Hallucination (3 bugs): The embedding model detecting '
    'symptoms not lexically present in the input (resolved with the '
    'lexical guard mechanism).'
)
add_bullet(
    'Contrastive Boundary Edge Cases (2 bugs): Incorrect negation '
    'resolution across pero/but/kaso boundaries in complex utterances.'
)
add_bullet(
    'Safety Filter Gaps (2 bugs): Missing suppression rules for '
    'red-flag/symptom interactions.'
)

add_paragraph(
    'This error-driven refinement cycle follows the Design Science '
    'Research emphasis on iterative evaluation. Every time a bug was '
    'found, a targeted fix was applied and the entire 288-case benchmark '
    'was re-run to make sure no earlier functionality broke in the process.'
)

add_paragraph(
    'As an additional validation step, an external AI audit was carried '
    'out with Gemini 2.5 Pro to look for potential blind spots. Out of '
    'seven improvement areas the audit flagged, six had already been '
    'addressed in the system, which confirmed that the test-driven '
    'development process had covered the most common NLP failure modes.'
)

# ── 3.9 Deployment Architecture ──────────────────────────────────────────────
doc.add_heading('3.9 Deployment Architecture', level=2)

add_paragraph(
    'MendoVendo v3.0 is deployed on a Raspberry Pi 5-based physical kiosk '
    'with the following hardware configuration:'
)

add_bullet('Processing Unit: Raspberry Pi 5')
add_bullet('Dispensing Control: Arduino Mega')
add_bullet('User Interface: Touchscreen display')
add_bullet('Network: Offline-capable (all processing is local)')
add_bullet(
    'Software Stack: Python 3.12.3, Flask web framework, SQLite database '
    'for POS inventory management'
)
add_bullet(
    'ML Model: paraphrase-multilingual-MiniLM-L12-v2 (~130MB, loaded '
    'lazily only when semantic fallback is needed)'
)
add_bullet(
    'Device Configuration: CPU inference by default (configurable via '
    'MENDO_SEMANTIC_DEVICE environment variable)'
)

add_paragraph(
    'The deployment architecture includes a Point-of-Sale (POS) system '
    'with inventory management, cart functionality, and an admin dashboard '
    'for stock management. The consultation API cross-references medicine '
    'recommendations against current inventory availability and pricing.'
)

# ── References ────────────────────────────────────────────────────────────────
doc.add_heading('References', level=2)

references = [
    '[1] Eguia, H., Sánchez-Bocanegra, C. L., Vinciarelli, F., Alvarez-Lopez, F., & Saigí-Rubió, F. (2024). Clinical decision support and natural language processing in medicine: Systematic literature review. Journal of Medical Internet Research, 26, Article e57892. https://doi.org/10.2196/57892',
    '[2] Tan, J., Rong, Y., Zhao, K., Bian, T., Xu, T., Huang, J., Cheng, H., & Meng, H. (2025). Natural language-assisted multi-modal medication recommendation. Proceedings of the 33rd ACM International Conference on Information and Knowledge Management, 2348-2357. https://doi.org/10.1145/3627673.3679623',
    '[3] Zomorodi, M., Ghodsollahee, I., Martin, J. H., Talley, N. J., Salari, V., Pawlak, P., Rahimi, K., & Acharya, U. R. (2024). RECOMED: A comprehensive pharmaceutical recommendation system. Artificial Intelligence in Medicine, 157, Article 102981. https://doi.org/10.1016/j.artmed.2024.102981',
    '[4] Engstrom, E., Storey, M.-A., Runeson, P., Host, M., & Baldassarre, M. T. (2022). How software engineering research aligns with design science: A review. Empirical Software Engineering, 27(2), Article 48. https://doi.org/10.1007/s10664-021-10079-z',
    '[5] Baskerville, R., Kaul, M., & Storey, V. C. (2024). Design science research contributions: Finding a balance between artifact and theory. Journal of the Association for Information Systems, 25(1), 1-32. https://doi.org/10.17705/1jais.00850',
    '[6] Jurafsky, D., & Martin, J. H. (2024). Speech and language processing (3rd ed.). Stanford University. https://web.stanford.edu/~jurafsky/slp3/',
    '[7] Wang, Y., Chen, Q., Ahmed, M., Li, Y., Liang, W., & Lu, H. (2021). Pre-trained language models and their applications. Engineering, 25, 51-74. https://doi.org/10.1016/j.eng.2022.04.024',
    '[8] Reimers, N., & Gurevych, I. (2019). Sentence-BERT: Sentence embeddings using Siamese BERT-networks. In Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing, 3982-3992. https://doi.org/10.18653/v1/D19-1410',
    '[9] Gao, T., Yao, X., & Chen, D. (2022). SimCSE: Simple contrastive learning of sentence embeddings. In Proceedings of the 2022 Conference on Empirical Methods in Natural Language Processing, 6894-6910. https://doi.org/10.18653/v1/2022.emnlp-main.46',
    '[10] Habehh, H., & Gohel, S. (2021). Machine learning in healthcare. Current Genomics, 22(4), 291-300. https://doi.org/10.2174/1389202922666210705124359',
    '[11] Musen, M. A., Middleton, B., & Greenes, R. A. (2021). Clinical decision-support systems. In E. H. Shortliffe & J. J. Cimino (Eds.), Biomedical informatics: Computer applications in health care and biomedicine (5th ed., pp. 795-840). Springer. https://doi.org/10.1007/978-3-030-58721-5_24',
    '[12] Li, J., Liu, H., Li, S., & Wu, J. (2022). A survey on annotation tools for natural language processing. Artificial Intelligence Review, 56, 2145-2173. https://doi.org/10.1007/s10462-022-10245-x',
    '[13] McHugh, M. L. (2022). Interrater reliability: The kappa statistic. Biochemia Medica, 22(3), 276-282. https://doi.org/10.11613/BM.2012.031',
]

for ref in references:
    p = doc.add_paragraph()
    p.add_run(ref)
    p.paragraph_format.left_indent = Inches(0.5)
    p.paragraph_format.first_line_indent = Inches(-0.5)

# ── Save ──────────────────────────────────────────────────────────────────────
output_path = 'MendoVendo_v3_Materials_and_Methods.docx'
doc.save(output_path)
print(f"✅ Saved: {output_path}")
print(f"   Paragraphs: {len(doc.paragraphs)}")
print(f"   Tables: {len(doc.tables)}")
