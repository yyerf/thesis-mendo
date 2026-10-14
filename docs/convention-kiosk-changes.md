# Kiosk changes for October 15, 2026

The main screen retains **Tap anywhere to begin**. After the opening dialog,
a separate first page offers neutral **Browse medicines** and **Describe symptoms**
selections. Both paths collect age once; catalog product dialogs contain only
product information, with no repeated age inputs. The
direct catalog uses the existing checkout cart and payment flow, with real POS
prices, available stock (excluding reserved units), product details and local
reference photos. Server checks enforce age limits at cart addition and order
creation; quantity limits and payment reservations remain. Nutrabliss is an
active retail supplement in slot 10 at PHP 35 per capsule. It follows the same
cart and stock-reservation flow, and remains separate from medicinal recommendations.

Auto language selection is available on the home screen and language dialog;
individual pages have no language dropdowns. Choosing Auto restores detection from typed or transcribed symptoms;
explicit English, Tagalog or Bisaya choices remain until Auto or a new session.
The catalog uses square-corner cards with direct Add to Cart buttons and a
separate info icon, a Search placeholder, and a View Cart button at the top.
The opening dialog uses compact text, a small blue checkbox, and a blue
Proceed button. Optional research consent remains unchecked: the participant
chooses whether to store health information. Development flow traces now also
require that consent. Consented decision records include diarrhea answers and
safety advice for later expert review.

The diarrhea screen asks about stool consistency, blood/black stools, fever,
hydration, abdominal pain, recent antibiotics, pregnancy/breastfeeding/immune
or bowel risk, suspected food exposure, stool frequency, and bloating/cramps.
It describes reported symptoms without diagnosing an infection. Blood, severe
pain/distension, fainting or inability to retain fluids trigger urgent referral.
Other concerning responses stop kiosk medicine recommendations and advise
professional assessment. Duration screening still blocks prolonged diarrhea.
ORS guidance appears explicitly because the machine does not stock it. Bloating
and mild cramps are recorded without automatically adding another medicine.

Unsupported complaint recognition covers dental discomfort, cuts/wounds,
burns, fungal skin complaints, acne, general skin care, bites, constipation,
mouth ulcers, hemorrhoids, scalp complaints, and ear/eye/urinary discomfort.
These are reported complaint labels, not diagnoses or promises that OTC care
will be sufficient. Serious wound, bite and vision cues retain medical referral.
Negated complaint phrases are excluded. This is a finite rule set; unmatched
text still gets the existing rephrase/professional-help fallback.

Stock was set to **99 for each active POS listing** on this Windows checkout,
after a verified database backup. Each change has a `stock_logs` entry with the
event reference. A separate kiosk/Pi installation must run its own stock setup:

```sh
python tools/set_event_stock.py --quantity 99 --event convention-2026-10-15
python tools/set_event_stock.py --quantity 99 --event convention-2026-10-15 --apply
```

Capture the final build or completed event without clearing any records:

```sh
python tools/snapshot_event.py --event convention-2026-10-15-end
```

This saves a verified SQLite backup, source code, medicine images, runtime logs
and checksums under `logs/archive/`. Stop the app first for an end-of-event copy
so the log files and database describe the same completed session.

This is a one-time adjustment, not a startup refill. Restarting preserves stock
deductions. Entries do not certify physical quantities loaded. Historical generic
probiotic rows are retired rather than renamed into Nutrabliss.

## Product and clinical sources

- [Unilab Diatabs](https://www.unilab.com.ph/products/diatabs?sku=153): 2 mg
  capsule and ages 12+. Runtime catalog corrected from tablet/age 6.
- [Watsons Philippines Nutrabliss Daily Defense](https://www.watsons.com.ph/nutrabliss-ws-nutrabliss-daily-defense-probiotic-capsule-sold-per-piece/p/BP_50030196):
  six Lactobacillus species plus prebiotics; digestive-health supplement.
  PHP 35 is the per-piece reference price used for its new POS listing.
  No diarrhea therapeutic indication or strain-specific efficacy is inferred.
- [Watsons Daily Defense usage](https://www.watsons.com.hk/en/daily-defense-probiotic-prebiotics/p/BP_812267):
  the brand's regional listing specifies ages 12 and above, used as the kiosk
  purchase age limit. The supplied local package directions take precedence.
- [NCCIH probiotics](https://www.nccih.nih.gov/health/probiotics-usefulness-and-safety):
  effects depend on product/strain and condition; supplements do not replace
  established care.
- [NHS loperamide suitability](https://www.nhs.uk/medicines/loperamide/who-can-and-cannot-take-loperamide/)
  and [diarrhea care](https://www.nhs.uk/symptoms/diarrhoea-and-vomiting/):
  rehydration and professional assessment for concerning symptoms.

Photos are references, not images of the actual stock. Packaging may differ;
the supplied label takes precedence. Local photos and source URLs are in
`web/static/images/medicines/sources.json`; original owners retain image rights.
`tools/fetch_catalog_images.py` records the sources for retrieval. Product images
were downloaded, not AI generated.

## Validation

Isolated database tests cover catalog fields/photos, stock reservations, age
gates, cart caps, supplement purchases/reservations and fresh consent sessions. Diarrhea route
tests cover sequential answers, rejection of bypass/out-of-order answers,
urgent/antibiotic referral and retained duration context. Complaint tests cover
English/Tagalog/Bisaya recognition, negation and urgent fallback. Browser checks
verify the welcome dialog, product grid, medicine details and cart handoff.
No paid order is created by those browser checks.
