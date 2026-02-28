# 20260221 — Annotator Strategy for `userInquiry.txt`

> **Core questions answered here:**
> 1. Will annotator answers actually help, given we already have 522 phrases in `mendo_core`?
> 2. Should all 1,039 entries be annotated, or is there too much redundancy?
> 3. Which entries are the highest priority?

---

## 1. Will Annotator Answers Actually Help?

**Yes — and they fill a gap that the 522 phrases in `step1.py` cannot fill.**

### What `step1.py`'s 522 phrases already do (working)

`step1.py` is a **symptom detection** layer. It answers:
> *"Does this text contain a HEADACHE signal?"*

It maps raw tokens → symptom label presence/absence. It is good at this.

### What the annotator provides (currently missing)

The annotator creates **end-to-end recommendation ground truth**. It answers:
> *"Given this exact complaint, what is the clinically correct drug, dosage, and safety flag?"*

This is a completely different layer. Specifically, annotators validate:

| Layer | What it covers | Currently validated? |
|-------|---------------|---------------------|
| `step1.py` symptom detection | Does "sakit ulo" = HEADACHE? | ✅ Yes, via `symptom_eval.whole.jsonl` |
| `step2.py` semantic similarity | Does "gatuyok" embed near DIZZINESS? | ✅ Partially, via `st_pairs.sample.jsonl` |
| `step4_recommend.py` drug scoring | Is Paracetamol the RIGHT pick for this complaint? | ❌ **Never externally validated** |
| Safety referral logic | Should `refer_to_doctor: true` for "ubo may dugo"? | ❌ **Never validated** |
| Multi-symptom drug priority | For fever + sore throat combo, which drug wins? | ❌ **Not tested** |

**The annotator fills all three gaps in the bottom rows.**

### Concrete example of why this matters

> Input: `"Labad kaayo akong tutunlan"`

- `step1.py` — will fire on `"labad"` (HEADACHE keyword) AND `"tutunlan"` (SORE_THROAT keyword) → **two labels detected**
- But `"labad sa tutunlan"` = *throat pain*, not head pain → the correct label is **SORE_THROAT only**
- `step4` may then recommend **Paracetamol** (for HEADACHE) when the correct drug is **Strepsils or Betadine gargle**
- Only a pharmacist annotator catches this

> Input: `"Sakit akong ulo sukad ganina pa"`

- The word `"sukad"` contains the substring `"suka"` (nausea keyword)
- `step1` might false-positive on NAUSEA → wrong drug recommendation
- Annotator confirms: HEADACHE only, `refer_to_doctor: false`, drug = Paracetamol

**Summary: the annotator produces the gold standard against which `step4_recommend.py` is evaluated for the first time.**

---

## 2. Dataset Profile — What Are the 1,039 Entries?

Automated analysis of `data/datasets/annotation/userInquiry.txt`:

### Symptom Distribution

| Symptom Label | Entries |
|---------------|---------|
| HEADACHE | 206 |
| FEVER | 166 |
| COUGH | 145 |
| RHINITIS | 137 |
| STOMACH_PAIN | 89 |
| SORE_THROAT | 78 |
| NAUSEA | 69 |
| LBM / DIARRHEA | 49 |
| DYSPNEA | 37 |
| FATIGUE | 36 |
| CHEST_PAIN | 34 |
| DIZZINESS | 33 |
| BODY_PAIN | 31 |

> Note: counts sum to more than 1,039 because many entries contain multiple symptom signals.

### Linguistic Complexity

| Type | Count | % of total |
|------|-------|------------|
| Multi-symptom (2+ detected labels) | ~175 | 17% |
| Negation entries (`wala`, `dili`, `hindi`) | 151 | 15% |
| Uncertain / hedged (`siguro`, `murag`, `parang`) | 105 | 10% |
| Tagalog-primary | 253 | 24% |
| English-primary | 24 | 2% |
| Short / possible noise (≤12 chars) | 81 | 8% |
| Typo / heavy abbreviation | 35 | 3% |

---

## 3. Are There Duplicates? Yes — Significant Redundancy

A large portion of the 1,039 entries are **semantic duplicates**: same symptom, same expected output, different surface phrasing.

### Example duplicate cluster (all → HEADACHE → Paracetamol/Ibuprofen, `refer_to_doctor: false`)

```
Sakit kaayo akong ulo karon
Labad kaayo akong ulo
Kasakit sa akong ulo oy
Sakit akong ulo sukad ganina pa
Dili nako makaya sakit sa akong ulo
sakit ulo ko
Ulo lang sakit wala nay lain
ahhh sakit kaayo akong ulo
Yawa sakit ulo ko mars
Sakit ulo ko eh
```

All ten produce the same annotation. Asking a pharmacist to fill 10 identical JSON records is wasted time.

### Why the duplicates exist (and why they are still useful — just not for annotation)

The duplicates are valuable for a **different purpose**: testing that `step1.py + step2.py` handles all phrasing variants correctly (robustness testing). But that does NOT require a full pharmacist annotation — it just requires running the pipeline and checking the label output.

---

## 4. Recommended Tiered Annotation Strategy

**Recommended total: ~350 full expert annotations** (from 1,039).

This is not a shortcut — it is the professionally correct approach. Annotating 1,039 near-identical entries produces 650 redundant data points while the pharmacist misses the clinically important ones.

---

### TIER A — Must Annotate (~200 entries)
> **Reason: Genuinely different expected outputs. Pipeline likely to fail.**

| Category | Count | Why it matters |
|----------|-------|----------------|
| Multi-symptom combinations | ~120 | Drug selection changes when symptoms combine (e.g., fever + chest pain = refer) |
| Negation entries | 151 | System MUST NOT recommend cough medicine for "wala koy ubo" |
| Safety-critical singles | ~15 | "ubo may dugo", "sakit dughan sa tuo", "sakit tiyan sa wala" → `refer_to_doctor: true` |
| Uncertainty/hedged statements | ~50 | "murag hilanat" — should this trigger a recommendation or a clarification? |

**Specific safety-critical entries to annotate immediately:**

```
Ubo may dugo                        → refer_to_doctor: true (blood in cough)
Sipon nahimong yellow na            → refer_to_doctor: true (purulent rhinitis)
Sakit na dughan sa tuo              → refer_to_doctor: true (right chest = not cardiac but serious)
Sakit tiyan sa wala                 → refer_to_doctor: true (possible appendicitis region)
Tingali dengue ni hilanat unya sakit lawas  → refer_to_doctor: true
Lisod moginhawa parang kulang hangin → refer_to_doctor: true (severe dyspnea)
Parang may sagka sa ilong dili ko makaginhawa  → escalate if persistent
```

---

### TIER B — Should Annotate (~100 entries)
> **Reason: Linguistic diversity. Pipeline may handle incorrectly.**

| Category | Count | Why it matters |
|----------|-------|----------------|
| All English-primary entries | 24 | Real user diversity, step1 phrase coverage likely lowest here |
| All typo/heavy abbreviation entries | 35 | Tests robustness ("hlnat", "skit ulo", "gtk") |
| All 50 LBM/DIARRHEA entries | 50 | Newly added class, needs drug ground truth (ORS/Hydrite, Diatabs) |
| All 50 SORE_THROAT entries | 50 | Newly added class, needs drug ground truth (Strepsils, gargle) |
| Code-switched entries not in Tier A | ~30 | Filipino-English mixing, harder for step1 |

> Note: Some of these overlap with Tier A (e.g., LBM with "watery tai" safety cases). Count ~100 unique non-Tier-A.

---

### TIER C — Sample Only (~50 entries)
> **Reason: Baseline sanity check. Confirm the pipeline handles clean, simple cases.**

Pick **5–10 entries per symptom class** of the simplest, cleanest, unambiguous single-symptom entries:

```
# HEADACHE baseline
Sakit kaayo akong ulo karon
sakit ulo ko
Headache napud today

# FEVER baseline
Gihilantan ko karon
Hilanat ko oy
Fever mode karon

# COUGH baseline
Ubo-ubo lang ko wala laing sakit
Padayon akong ubo dili mahunong
Dry cough lang ni

# (etc. for all 13 symptom classes)
```

These confirm the happy path works. One representative per language variant (Bisaya, Tagalog, English) is enough.

---

### TIER D — Skip (remaining ~650 entries)
> **Reason: Semantic duplicates of Tier C. No new annotation value.**

These are entries like:
```
Sakit akong ulo grabe
Nakasakit kaayo akong ulo karon
Parang mobuto akong ulo sa kasakit
Kasakit sa akong ulo oy
Dili nako makaya sakit sa akong ulo
Kanunay nalang sakit akong ulo karon
...  (15+ variants all = HEADACHE → Paracetamol)
```

The pipeline either handles all of them or none of them. Annotating all 15 does not improve evaluation quality over annotating 2.

**What to do with Tier D:** After annotation is complete, run the pipeline on all 650 and auto-label them with the pipeline's own output. Flag any where confidence < threshold for spot-check. This is a legitimate methodological approach (self-annotation with human spot-check).

---

## 5. Annotation Load Estimate

| Tier | Entries | Time @ 8 min/entry | Time @ 5 min/entry |
|------|---------|-------------------|-------------------|
| A — Complex/safety | ~200 | ~27 hours | ~17 hours |
| B — Linguistic diversity | ~100 | ~13 hours | ~8 hours |
| C — Baseline samples | ~50 | ~7 hours | ~4 hours |
| **Total recommended** | **~350** | **~47 hours** | **~29 hours** |

For a thesis timeline, ~30–50 hours of pharmacist annotation time is realistic. Annotating all 1,039 would require ~86–143 hours — too much for a single annotator on a thesis schedule.

---

## 6. Output File Structure

Save annotated outputs to:

```
data/datasets/annotation/
├── userInquiry.txt                          ← source (1,039 entries)
├── annotator_prompt.md                      ← instructions for pharmacist
├── domain_expert_annotations.template.json ← schema
│
├── annotations_tier_A.jsonl                ← complex + safety (annotate first)
├── annotations_tier_B.jsonl                ← linguistic diversity
├── annotations_tier_C.jsonl                ← baseline samples
└── annotations_combined.jsonl              ← merged after all tiers done
```

This structure lets you report annotation progress in stages:
> *"Tier A (200 high-complexity entries) completed as of [date]; Tier B in progress."*

Which is a stronger thesis claim than *"1,039 entries prepared but only X annotated."*

---

## 7. Thesis Claim Accuracy Check

| Claim | Status |
|-------|--------|
| "1,039 realistic patient utterances prepared for expert annotation" | ✅ Accurate |
| "Annotated by a licensed pharmacist" | ✅ Accurate once Tier A+B+C done |
| "Gold-standard evaluation covering all 13 symptom classes" | ✅ Accurate after ~350 annotations |
| "All 1,039 entries annotated" | ❌ Not needed, overshoots, wastes time |
| "350 strategically selected entries annotated, prioritizing multi-symptom, negation, and safety-critical cases" | ✅ More defensible than raw volume |

---

## 8. Action Order for Annotator

1. **Start with Tier A safety-critical entries** (blood in cough, chest pain, left stomach pain, dengue suspicion) — these are highest clinical impact and take priority in any defense Q&A
2. **Complete all Tier A negation entries** — this is the hardest edge case for the pipeline
3. **Complete all Tier A multi-symptom entries**
4. **Complete Tier B** (all 50 LBM + all 50 SORE_THROAT entries first, since these are the newest additions)
5. **Complete Tier C** (one session, fastest since these are unambiguous)
6. After ~350 done: run pipeline on remaining 650, auto-label, spot-check low-confidence outputs

---

*Generated: 2026-02-21 | Dataset: data/datasets/annotation/userInquiry.txt (1,039 entries)*
