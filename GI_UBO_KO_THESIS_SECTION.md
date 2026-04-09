# "gi ubo ko" — Copy-Paste Thesis Section

> Copy the section below directly into your thesis paper.
> It follows the same style as the existing diarrhea ("nagtatae ako") scenario in the OLDCARTS Sample Implementation section.
> You can place this **after** the diarrhea scenario paragraph, or **replace** the brief cough mention in the existing text with this expanded version.

---

## OPTION A — Full Cough Scenario (add after the diarrhea paragraph)

To further illustrate the pipeline's multilingual capability and multi-step OLDCARTS flow, consider a second scenario. A Cebuano-speaking user approaches the kiosk and types: "gi ubo ko" (I'm coughing).

The hybrid extraction pipeline processes this Bisaya input through three stages. The dictionary scanner matches "ubo" against the Cebuano cough entries, producing the symptom label COUGH_GENERAL. Because cough is the sole detected symptom and no contextual clues about cough type (dry or productive) are present in the input, the system triggers a Character clarification question:

> "Please specify: Is your cough dry (walay/walang plema) or with phlegm (naay/may plema)?"

The user selects "Dry cough." This maps to the OLDCARTS Character component — identifying the quality of the symptom. The system now reclassifies the symptom as COUGH_DRY, which changes the recommendation strategy: it selects cough suppressants such as Tuseran Forte (Dextromethorphan + Paracetamol + Phenylephrine + Chlorphenamine) and Sinecod Forte (Butamirate citrate), while excluding expectorants like Solmux (Carbocisteine), because administering an expectorant for a dry, non-productive cough serves no therapeutic purpose and can cause unnecessary side effects.

Before displaying these recommendations, the system applies the Duration component — the Timing element of OLDCARTS. The user is presented with four bilingual multiple-choice buttons tailored to the cough threshold:

> "Gaano na katagal ang iyong tuyong ubo (dry cough)? / How long have you had this dry cough?"
>
> • Less than a day
> • 1–7 days
> • 8–14 days
> • More than 2 weeks

If the user selects "More than 2 weeks," the system blocks the OTC recommendation and displays a referral notice: cough persisting beyond 14 days may indicate chronic bronchitis, undiagnosed asthma, or tuberculosis, conditions requiring professional medical evaluation. If the user selects any of the other three options (less than a day, 1–7 days, or 8–14 days), the duration falls within the safe threshold and the system proceeds to display the medicine recommendations normally.

Had the user instead selected "With phlegm" during the Character clarification, the system would have classified the symptom as COUGH_PRODUCTIVE and recommended expectorants — Ascof Forte (Lagundi leaf extract), Solmux (Carbocisteine), and Robitussin (Guaifenesin) — while excluding suppressants. The same 14-day duration check would still apply.

This cough scenario demonstrates three key system capabilities working in sequence: (1) multilingual symptom extraction from Cebuano input, (2) OLDCARTS Character clarification to distinguish clinically different cough subtypes, and (3) OLDCARTS Timing enforcement through the Duration Safeguard to prevent OTC self-medication for chronic symptoms.

---

## OPTION B — Shorter version (replace the existing brief cough mention)

If you prefer to keep it shorter, you can replace the existing sentence about cough in the "This pattern repeats across three other symptom domains" paragraph with this expanded version:

For cough, the system asks whether the cough is dry or with phlegm — mapping to the Character component — because dry cough requires a suppressant (e.g., Sinecod Forte with Butamirate citrate) while productive cough requires an expectorant (e.g., Solmux with Carbocisteine), and giving the wrong type can be harmful. This flow is demonstrated when a Cebuano-speaking user types "gi ubo ko" (I'm coughing): the hybrid pipeline detects COUGH_GENERAL from the Bisaya input, triggers the Character clarification, and upon the user selecting "dry cough," reclassifies the symptom as COUGH_DRY before applying the 14-day Duration threshold. If the user reports coughing for more than two weeks, the OTC recommendation is blocked and a professional referral is displayed.

---

## OPTION C — Pipeline trace table (for methodology/technical sections)

| Stage | Component | Input | Output |
|-------|-----------|-------|--------|
| 1. Symptom Extraction | Dictionary + Semantic | "gi ubo ko" (Cebuano) | COUGH_GENERAL |
| 2. Clarification | OLDCARTS Character | User selects "Dry cough" | COUGH_DRY |
| 3. Duration Check | OLDCARTS Timing | User selects duration button | Safe (≤14 days) or Blocked (>14 days) |
| 4a. Recommendation (safe) | Medicine Matching | COUGH_DRY, safe duration | Tuseran Forte, Sinecod Forte |
| 4b. Referral (blocked) | Duration Safeguard | COUGH_DRY, >14 days | Doctor referral displayed |

**Duration Safety Matrix for Cough:**

| Button Label | Value | Parsed Days | Threshold (14d) | Result |
|-------------|-------|-------------|-----------------|--------|
| Less than a day | 0 | 0 | ≤ 14 | SAFE — proceed to recommendation |
| 1–7 days | 1-7 | 4 | ≤ 14 | SAFE — proceed to recommendation |
| 8–14 days | 8-14 | 11 | ≤ 14 | SAFE — proceed to recommendation |
| More than 2 weeks | 15+ | 15 | > 14 | BLOCKED — doctor referral |
