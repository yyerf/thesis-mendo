# Iteration 1 Results and Discussion Review

Review date: 13 October 2026, Asia/Manila. Source thesis: `thesis-13.docx`.

The pharmacist-guided scope and medicine revisions belong to Iteration 1 because they refine the baseline before the planned field validation. Results and Discussion should report the problem, expert feedback, design decision, implemented behavior, evaluation evidence, and remaining limitations. Methods must also describe the system that was actually evaluated. The original thesis has been preserved; this document is an implementation review and writing guide, not a replacement for measured research findings.

## Where changes belong

Use the three iterations already defined in Methods: Iteration 1 is design, development, and internal evaluation; Iteration 2 is consented real-user validation with independent pharmacist review; Iteration 3 is refinement and re-evaluation using those findings. Multiple changes within Iteration 1 can be revisions of the same iteration. A code change does not automatically create a new research iteration.

Organize the Iteration 1 discussion around findings and design decisions. Do not turn it into a list of commits. Group related changes into symptom scope, medicine knowledge and inventory, consultation and safety workflow, evaluation, and hardware integration. For each group, explain what was observed, what changed, why it changed, how it was tested, and what remains unproven.

| Document location | What to include |
|---|---|
| Introduction and scope | Current coverage and study objectives; distinguish broad symptom groups from internal labels |
| Methods | Final implemented pipeline, supported vocabulary, catalog policy, annotation process, evaluation procedures, and deviations from the original plan |
| Results and Discussion | Iteration findings, pharmacist feedback, resulting revisions, measured outcomes, interpretation, tradeoffs, and limitations |
| Appendix | Detailed change register, pharmacist review record, product verification sheets, test cases, forms, screenshots, and reproducibility manifest |
| Conclusion | Only conclusions supported by completed iterations and measured evidence |

## Verified implementation changes

Before this revision, the committed catalog already contained Buscopan in slot 1, while the README and catalog tests still expected Advil there. Neozep, Tuseran, and Erceflora remained in the production catalog. Toothache remained a dictionary label, fuzzy anchor, and proximity rescue. Therefore the requested changes had not been consistently implemented.

| Requested change | Revised behavior | Research implication |
|---|---|---|
| Remove toothache | Removed from the supported dictionary and fuzzy labels. Dental context is retained as an exclusion guard. Dental-only inputs return no medicine and a dentist/pharmacist message. Mixed complaints retain independently stated supported symptoms. | A scope change, not a demonstrated improvement in toothache recognition |
| Neozep to Buscopan | Buscopan occupies slot 8 and routes to cramping/spasm context. Neozep is retired from the production allowlist. | Reallocation of catalog coverage from cold treatment to abdominal cramps |
| Tuseran to Sinecod | Sinecod uses the existing Sinecod Forte butamirate source record. Dry cough routes to Sinecod; productive cough routes to Solmux. | Updated active ingredient, contraindications, and formulation-specific age handling |
| Ibuprofen to Kremil-S | Kremil-S occupies slot 1. Acidity context routes to the antacid, not to an analgesic. Advil is outside the production allowlist. | Removal of an analgesic option and addition of an acidity-specific treatment option |
| Erceflora to generic Lactobacillus acidophilus | Erceflora is retired. An inactive inventory placeholder reserves the intended slot 10; exact product, CFU, form, age, indications, and price remain unverified. It cannot be recommended or purchased. | Proposed replacement is incomplete and must not be reported as clinically validated |

These are catalog substitutions, not claims of therapeutic equivalence. Buscopan does not treat Neozep's cold indications, and Kremil-S does not replace ibuprofen for fever, headache, or body pain. The recommendation rules must change with the catalog.

After the revision, the dictionary contains **13 labels and 541 phrase entries**. The supported labels are HEADACHE, FEVER, COUGH_GENERAL, COUGH_DRY, COUGH_PRODUCTIVE, SORE_THROAT, STOMACH_ACHE, BODY_ACHES, DIARRHEA, NASAL_CONGESTION, RUNNY_NOSE, RASHES, and ALLERGIC_RHINITIS. Count these separately from broader clinical groupings. Phrase entries are a code count, not independent clinical examples or proof that every phrase has been validated.

## Current hardware catalog

| Slot | Runtime product | Form | Minimum age recorded in runtime |
|---|---|---|---|
| 1 | Kremil-S | Chewable tablet | 12 |
| 2 | Bioflu | Tablet | 12 |
| 3 | Biogesic | Tablet | 12 |
| 4 | Cetirizine | Tablet | 6 |
| 5 | Solmux | Capsule | 12 |
| 6 | Sinecod | Tablet | 13 |
| 7 | Symdex | Tablet | 6 |
| 8 | Buscopan | Tablet | 6 |
| 9 | Loperamide | Tablet | 6 |
| 10 | Lactobacillus acidophilus placeholder | Unverified | Unverified |

This means nine enabled catalog entries and one reserved, disabled placeholder, not ten approved medicines. Except for the Sinecod correction, minimum ages above reflect the existing source records and still need exact-product pharmacist verification before use with participants. The Sinecod 50 mg tablet listing specifies adolescents over 12, which is represented as 13 for the application's integer-age input. Do not apply syrup age limits to that tablet. [Watsons Sinecod product listing](https://www.watsons.com.ph/sinecod-sinecod-sinecod-butamirate-citrate-50mg-sold-per-piece/p/BP_10002745).

Buscopan's manufacturer describes relief of abdominal cramps; Kremil-S's manufacturer describes antacid and antiflatulent ingredients. The revised routes use those distinct contexts. General or severe abdominal pain still needs the existing clarification and triage workflow rather than an unconditional medicine match. [Buscopan Philippines](https://www.buscopan.com/en-ph/products/buscopan), [Unilab Kremil-S](https://www.unilab.com.ph/products/kremil-s?sku=299).

The [FDA active ingredient classification list](https://www.fda.gov.ph/wp-content/uploads/2025/10/Annex-A.pdf) lists medicinal Lactobacillus acidophilus as Rx and butamirate as pharmacist-only non-prescription. An [FDA probiotic food supplement registration](https://verification.fda.gov.ph/FoodProduct_Highriskview.php?ACCOUNTCODE=FR-4000008001252&export=pdf) also includes acidophilus in a combination supplement with no approved therapeutic claims. These categories do not identify the intended Watsons product or authorize autonomous OTC vending. Have the consulting pharmacist verify the specific registration, label, permitted use, and supervised dispensing arrangement.

Research located [Watsons Nutrabliss gut-health products](https://www.watsons.com.ph/c/shop-nutrabliss-by-watsons-gut-health), but did not establish that the intended product is a generic single-ingredient acidophilus medicine. An [FDA Nutrabliss registration](https://verification.fda.gov.ph/food_products_2view.php?ACCOUNTCODE=4000010697135&export=pdf) describes Bacillus coagulans plus lactulose, illustrating why selecting a product by the word “probiotic” is insufficient. Do not infer a brand or use a different organism without pharmacist confirmation.

## Thesis inconsistencies to correct first

1. **Three versus four iterations.** Methods describes three iterations, while the Results and Discussion opening says four. Align these with the actual study plan. If the older baseline is a preliminary evaluation, label it separately and explain its relationship to Iteration 1.
2. **Meaning of baseline.** Methods calls the implemented Iteration 1 artifact the baseline; Results calls its baseline an initial system before a community-based Iteration 1. Identify the version, date, dataset, and engine evaluated in every baseline table. Do not assume it is Mendo v2 unless the original evidence establishes that.
3. **Fine-tuned classifier claim.** The Iteration 1 implementation paragraph mentions a fine-tuned 13-label head. The default production pipeline uses a pretrained MiniLM embedding component and deterministic expert rules; a trained classifier head is not shown in that production path. Correct the description and distinguish any separate experimental models from the deployed system.
4. **Dictionary and anchor counts.** The thesis uses 587 phrases and 14 labels. The revised implementation has 541 phrase entries and 13 supported labels; the current semantic anchor dictionary contains 277 entries rather than the stated 145. Explain the differences and update the tables. Keep historical counts only where they describe a clearly identified older version.
5. **Medicine dataset versus dispensable catalog.** The JSON retains 24 formulation-level reference records. Production now selects nine approved items, with a disabled placeholder separately stored in inventory. Do not present every reference medicine, including syrups and ORS, as physically stocked or selectable in the kiosk.
6. **Semantic execution versus influence.** The report-producing hybrid path attempts semantic analysis even when dictionary results exist, and may mark it observational. The thesis says semantics is skipped completely on a dictionary hit. Document actual execution and which outputs influence the final decision; do not conflate an observation with a decision-making fallback.
7. **Conflicting performance values.** The thesis contains 283/288 guided and differing raw figures in prose/tables; the August 14 evidence file records 288/288 guided, while the August 15 current manifest records 266/288 guided. Each number needs its original version, source, date, hash, and evaluation mode. They cannot all describe one frozen system.
8. **319 versus 288.** Explain whether 319 means 288 detection cases plus 31 separate duration cases. Do not silently use 319 as the denominator for a detection metric measured on 288.
9. **Benchmark pass definition.** Methods says every applicable component must match. The existing benchmark primarily evaluates symptom sets; its recommendation-success counter checks that recommendations exist and is not a comparison against expert-approved medicines. Either implement the stated end-to-end rubric or accurately narrow the current metric description.
10. **Precision versus clinical safety.** A symptom-detection precision of 78.08% does not establish that one fifth of medicines are clinically inappropriate. Clinical appropriateness needs its own expert judgments and denominator. Likewise perfect negation precision on a test set does not prove a safe system.
11. **Field results versus plans.** Iterations 2 and 3 are described as planned. Do not report community validation, independent accuracy, or final deployment as complete without participant records and pharmacist review.
12. **Hardware and checkout language.** The thesis includes cashless checkout and hardware-disabled descriptions; current firmware and guides describe payment-only D2/D3 cash integration with medicine motors disabled. Update screenshots and distinguish software/simulator tests, measured payment behavior, and unmeasured dispensing.
13. **Figure and table references.** Several screen captions and their explanatory paragraphs use different figure numbers; the Methods duration matrix references also drift. Renumber after the chapter structure is settled.
14. **Public dataset objective.** Provide the repository URL/DOI and documentation only after an appropriately consented, reviewed, de-identified corpus is actually released. Raw clinical text is not automatically anonymous because names were omitted.

## What to assemble for Iteration 1

### Freeze a reproducible artifact

Record a commit identifier, engine ID (`mendo-expert-minilm-v3.3`), catalog version (`mendo-hardware-catalog-v2-2026-10-13`), supported labels, reference dataset hash, benchmark hashes, Python/package versions, semantic backend/model and cache status, thresholds, device specifications, and run date. Capture a controlled set of current screenshots. Use that same version throughout the Iteration 1 results.

Do not combine metrics from runs produced before and after scope changes. Keep a versioned pre-revision record and a post-revision record. If an experiment changes the dictionary, model, prompt, threshold, or vocabulary, it is a different evaluated artifact.

### Record pharmacist consultation evidence

Create a consultation record with the actual consultation date, professional role and credentials where appropriate, questions asked, original product list, recommended revisions, rationale actually supplied, unresolved issues, and confirmation of the final list. Use the user's account of the consultation as reported feedback until documentary confirmation exists. Do not invent a signed approval, quotation, consultation date, or clinical rationale.

For each enabled product, collect exact brand/generic, strength, dosage form, registration, package insert, indications, minimum age for that formulation, contraindications, warnings, interactions, duration limits, storage, expiry, packaging requirements, unit price, and hardware slot. The placeholder must stay disabled until those fields can be completed and the exact product is confirmed.

### Evaluate symptoms and scope fairly

Run normal, negated, mixed, misspelled, code-switched, ambiguous, and unsupported inputs. Report support per symptom and language, exact set match, micro precision/recall/F1, macro F1, and errors. Specify how empty sets are scored. Include cases with no symptoms, fully negated symptoms, unsupported complaints, and mixed supported/unsupported complaints.

Historical toothache cases should be retained as exclusion tests with their original annotations preserved. The workbook evaluator now explicitly records the original expected label and a dental-out-of-scope override. A successful exclusion is not successful clinical detection of toothache. For comparisons, report the full historical scope separately from a common-scope subset, with case counts and reasons for exclusions. Removing difficult labels can improve scores mechanically; do not attribute that improvement to a better language model.

Report raw-input detection separately from guided clarification. Guided results depend on the recorded or simulated answer and cannot be presented as an unaided classifier's performance. Label researcher/LLM-created benchmarks as synthetic technical evidence.

### Evaluate recommendations and safety as separate outcomes

Prepare independently reviewed expected medicine sets, acceptable alternatives, and expected actions. Allow a correct outcome to be clarification, non-drug advice, referral, or no recommendation. Brand exact match alone can unfairly reject a valid equivalent; a match on drug class alone can hide an unsuitable strength or formulation. Have the pharmacist define the rubric.

Test acid versus cramping stomach context; dry versus productive cough; isolated fever/headache/body pain; allergy versus viral nasal symptoms; non-infectious versus suspected infectious diarrhea; minimum-age boundaries; contraindications; duplicate paracetamol exposure; opposing cough mechanisms; and multi-symptom interactions. Include attempted stale-client submissions and unavailable inventory.

The revised catalog has a real coverage gap: plain congestion is not eligible for Bioflu's multi-symptom gate or Symdex's cough-plus-nasal gate. The current safe outcome is no recommendation. Suspected food-poisoning diarrhea also has no approved stocked medicine while the probiotic remains pending; guidance still emphasizes oral rehydration and excludes loperamide. Document these gaps instead of relaxing indication gates just to increase recommendation counts.

Distinguish symptom persistence thresholds from product-specific maximum use. For example, the Sinecod source record carries a seven-day maximum while cough referral screening uses a fourteen-day threshold. Ensure future evaluation checks that patients are not implicitly told to use the product for fourteen days.

### Evaluate the full consultation and platform

Exercise patient versus proxy purchase, intended-patient age, each clarification branch, severity, duration, red flags, inventory display, cart confirmation, payment, receipt, and stock movement. Test missing or invalid age because the backend currently applies minimum-age filtering when an age is supplied. A user-interface requirement alone does not prove the API cannot bypass that gate.

Verify that declining research consent still permits consultation, consented records carry model/version and decision traces, reviewer permissions hold, adjudication is recorded, and exports include only eligible records. Review raw-text terminal/file logging separately: the consultation route's flow tracing defaults on, so consent-aware research logging does not itself prove that raw clinical text never reaches operational logs. Resolve this before participant collection.

Measure latency on the actual Raspberry Pi under cold start and warmed use, including semantic audit execution on dictionary hits. Test offline after the model is cached. Record failures, timeouts, resource usage, and recovery. A local development machine result is not Raspberry Pi performance evidence.

Usability can use a defined instrument such as SUS if adopted in Methods, plus task-completion, errors, assistance needed, clarification comprehension, and language-specific feedback. Do not introduce survey scores in Results without a described protocol, sample, and collected responses.

### Evaluate hardware with measured evidence

Report payment trials by denomination and attempt, accepted/rejected events, duplicate or lost credit, receipt/stock consistency, disconnect and restart behavior, and simulator status. Existing source code and passing simulator tests support software behavior, not measured physical reliability.

Keep dispensing claims separate. Motors remain disabled in the integrated firmware. To claim physical dispensing, first gather supervised loaded-container trials, jams, single/double/no-release counts, confirmation sensors, product-slot identity, and failure recovery. Document expiry, packaging, and storage conditions for the selected products. Physical labels and calibration must match the revised catalog before dispensing is enabled.

## Proposed Results and Discussion sequence

1. **Evaluation context and preliminary baseline:** explain which earlier artifact and test set produced the existing normal/negation tables.
2. **Iteration 1 requirements and final artifact:** summarize the implemented consultation pipeline and actual coverage with a version identifier.
3. **Pharmacist-guided scope and catalog revisions:** present the change table, evidence of consultation, clinical distinctions, and incomplete probiotic verification.
4. **Internal symptom evaluation:** raw and guided results, per-language/per-label support, negation and unsupported-input outcomes, and representative errors.
5. **Recommendation and safety evaluation:** expert rubric, correct referrals and clarification, inappropriate suggestions, contraindication/age results, and coverage gaps.
6. **Platform and hardware results:** consultation, logging/consent, inventory, measured payment, and the remaining dispensing limitation.
7. **Iteration 1 interpretation and limitations:** what improved, what changed in scope, what remains unreliable, and what the evidence can establish.
8. **Readiness for Iteration 2:** unresolved issues, product verification, consent/review workflow, and the defined field protocol.

Do not add completed Iteration 2 or 3 result sections yet. When those phases are completed, use the same finding → change → evidence → interpretation structure with actual participant data and revised versions.

## Tables and records to prepare

| Evidence item | Essential fields |
|---|---|
| Scope and catalog revision register | Previous behavior, change, expert rationale, version, verification, status |
| Frozen artifact manifest | Commit, engine/catalog IDs, hashes, packages, device, thresholds, run date |
| Detection outcomes | Language, label, support, TP/FP/FN, precision, recall, F1, exact match |
| Negation and exclusion outcomes | Present and absent labels, false additions, missed presence, unsupported input routing |
| Recommendation appropriateness | Eligible reviewed consultations, appropriate/inappropriate/indeterminate, criteria, reviewer |
| Safety outcomes | Expected action, observed action, dangerous misses, unnecessary referral, age/condition blocks |
| Error analysis | De-identified case ID, expected/observed output, explanation, impact, remedy, retest |
| Hardware and platform trials | Mode, device, trial count, failures, recovery, receipt/stock/physical outcome |
| Field review reliability | Shared reviewed cases, reviewer labels, adjudication, disagreement, agreement measure |

Report numerators, denominators, missing/indeterminate data, and uncertainty. Cohen's kappa needs independently reviewed overlapping cases from at least two reviewers; one pharmacist's approval alone cannot produce inter-rater reliability. Avoid treating multiple sessions from the same person as independent participants without describing the sampling unit.

## Suggested Iteration 1 wording

“During Iteration 1, the researchers revised the symptom scope and medicine catalog following consultation with a pharmacy professional. Toothache was excluded from the supported recommendation scope, while dental expressions were retained as exclusion cues to prevent routing to unrelated OTC treatments. The revised catalog included Buscopan for cramping abdominal symptoms, Sinecod for dry cough, and Kremil-S for hyperacidity-related discomfort. These revisions changed symptom-to-medicine routing and required corresponding updates to formulation metadata, inventory, and regression expectations. The proposed Lactobacillus acidophilus product remained an inactive placeholder pending confirmation of its exact formulation and regulatory status.”

Follow that paragraph with measured verification results and coverage limitations. Do not add “improved accuracy,” “safer clinically,” or “validated by pharmacists” unless the corresponding comparisons and independent judgments are actually available.

## Completion checklist

- [ ] Confirm the intended three-iteration structure with the adviser and reconcile the preliminary baseline.
- [ ] Preserve original results and identify the version and dataset behind each existing table.
- [ ] Obtain a dated pharmacist consultation and exact-product verification record.
- [ ] Confirm the probiotic SKU before enabling slot 10.
- [ ] Verify all stocked strengths, formulation ages, prices, storage, expiry, and physical slot labels.
- [ ] Restart the app to apply the new catalog; inspect retired inventory and replacement stock independently.
- [ ] Resolve the existing regression and Windows-specific test limitations before declaring the artifact ready.
- [ ] Add expert gold recommendation/action annotations and an end-to-end pass rubric.
- [ ] Audit missing-age handling and raw health-text operational logging before participant use.
- [ ] Freeze and rerun a versioned technical evaluation; report raw/guided and historical/common scope separately.
- [ ] Update Methods, scope tables, screenshots, captions, and Results from the same frozen version.
- [ ] Prepare consent, sampling, independent review, adjudication, and de-identification for Iteration 2.
- [ ] Gather physical payment and dispensing evidence separately; do not infer dispensing from payment success.
- [ ] Publish the dataset only when release permissions and privacy review are complete.

## Verification record for this revision

The focused scope and catalog tests exercise dental-only and mixed complaints, class-specific stomach routing, Sinecod's tablet age metadata and API filtering, opposing cough warnings, legacy dental submissions, disabled pending inventory, first-run seeding, and idempotent inventory migration preserving retired product history.

A comparison against an isolated copy of the committed HEAD ran 200 tests and produced 25 failure reports and two errors. After the initial six scope tests were added and the revision corrected, the full run executed 206 tests with 20 failure reports and two errors. All remaining failed test identities were also present in the committed baseline; failed subtests can make failure-report totals differ from failed method counts. Windows Unix-domain-socket tests produced the two errors. Existing failures include fuzzy matching, a weather phrase incorrectly detected as cough, nasal bleeding interpretation, and semantic trace expectations. These remain work to do; the full suite is not green.

The Sinecod API boundary test was subsequently added, bringing the final full run to **207 tests, 20 failure reports, and two errors**. The failed identities still match the committed baseline. Final focused verification and separately versioned synthetic benchmark outputs are recorded alongside this review. Historical benchmark manifests have not been overwritten. Benchmark scores are technical findings, not clinical validation or evidence of physical dispensing.

The final focused run passed **14 of 14 tests**. Machine-readable evidence, including failed test identities and source hashes, is in [verification.json](evidence/iteration1-2026-10-13/verification.json).

| Revised technical evaluation | Cases | Exact set match | Micro F1 |
|---|---|---|---|
| Synthetic benchmark raw input | 288 | 211/288, 73.26% | 82.07% |
| Synthetic benchmark with simulated cough clarification | 288 | 266/288, 92.36% | 96.75% |
| Workbook with explicitly revised dental scope | 520 | 449/520, 86.35% | Not calculated by this runner |

The raw and guided metrics are saved in [synthetic-288.json](evidence/iteration1-2026-10-13/synthetic-288.json). The workbook outcomes are saved in [workbook-520.json](evidence/iteration1-2026-10-13/workbook-520.json), retaining each original expected label and scope override. The 288-case detection metrics equal the August 15 manifest values; these catalog changes do not demonstrate an improvement on that detection benchmark.

Of the forty workbook cases originally annotated as toothache, thirty-nine now produce the expected empty supported-label set. The remaining case, “Sakit ng isa kong ko since last night,” contains no explicit dental word and produces a cough false positive. It needs independent annotation review and language-error investigation; it has not been silently excluded or counted as a pass. Dental-context guards are conservative and can also miss an indirectly expressed secondary symptom in mixed complaints, so that tradeoff belongs in the error discussion.

New product prices in the catalog are provisional seed values, not verified pharmacy prices. Products already present under the same name retain their own inventory state; newly introduced medicines never inherit a different product's stock. Restart and inspect the inventory, price, and physical labels before loading the revised machine.
