# Annotation Workspace

Domain expert annotation files for creating the gold-standard evaluation dataset.

---

## Files

| File | Purpose |
|---|---|
| `userInquiry.txt` | 1,039 real-user style symptom inquiries (Bisaya/Tagalog/English/code-switched) for annotation |
| `annotator_prompt.md` | System prompt for the annotator tool — 5 rules, drug reference table, dosage guide, worked examples |
| `domain_expert_annotations.template.json` | JSON schema template for structured expert annotations |
| `domain_expert_pairs.template.csv` | CSV template for sentence-pair extraction from annotations |

---

## Annotation Workflow

1. Annotator reads `annotator_prompt.md` for full instructions
2. For each entry in `userInquiry.txt`, annotator fills in:
   - `language` — one of: `tagalog`, `bisaya`, `english`, `code-switched` (never null)
   - `symptom_labels[]` — one or more of the 15 canonical labels
   - `suggested_otc.selected[]` — generic drug names from the 26-drug list
   - `min_age`, `has_age_restrictions`, dosage guide per drug
3. Output follows `domain_expert_annotations.template.json` schema

## Required vs Optional Fields

| Field | Required? |
|---|---|
| `entry_id`, `user_inquiry`, `language` | ✅ Always |
| `symptom_labels[]` | ✅ Always (minimum `["UNKNOWN"]`) |
| `suggested_otc.selected[]` | ✅ Always (empty `[]` only if `requires_medical_referral: true`) |
| `min_age`, `has_age_restrictions`, `confidence` | ✅ Always |
| `known_contraindications_details` | ⚠️ Only if `has_known_contraindications: true` |
| `otc_dosage_guide` | ⚠️ Required per drug in `selected[]` |
| `user_age`, `symptom_labels_other` | ❌ Optional |
