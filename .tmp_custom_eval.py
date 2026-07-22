import json
from mendo_core.step3_hybrid import extract_symptoms_hybrid_report

cases = [
  { "id": 1, "input": "doc hlp... masakit ang tultunlan ko tpos prang d makahngan dhil sa barado ilong.", "labels": ["SORE_THROAT", "NASAL_CONGESTION"] },
  { "id": 2, "input": "Sige nko og CR since bfast... lbm yarn? Matubig ang dumi and kumukulo tyan ko.", "labels": ["DIARRHEA", "STOMACH_ACHE"] },
  { "id": 3, "input": "Grabe ang hperacidty ko... buhol buhol na tyan ko prang pinukpok din ang bdy ko.", "labels": ["STOMACH_ACHE", "BODY_ACHES"] },
  { "id": 4, "input": "Ang init ng katawan ko 39 degreesss... tmitibok din ulo ko and kumikislot.", "labels": ["FEVER", "HEADACHE"] },
  { "id": 5, "input": "Dghan kaayo og plema doc... ubo na productive kau. Mahapdi ang lalamunan.", "labels": ["COUGH_PRODUCTIVE", "SORE_THROAT"] },
  { "id": 6, "input": "Nag aalerdyi n nman me. Makati skin and namumula ang balat coz of food yta.", "labels": ["ALLERGIC_RHINITIS", "RASHES"] },
  { "id": 7, "input": "Ubo na tuyo (dry) and nanlalamig ako pro ang init ng ktawan ko. Ano ni?", "labels": ["COUGH_DRY", "BODY_ACHES", "FEVER"] },
  { "id": 8, "input": "Sakit akong alimpulo... mura migrena na tumitibok-tibok. d mdaala og smile.", "labels": ["HEADACHE"] },
  { "id": 9, "input": "i hve bad cough... may plema but d lumalabas. chest hurts also.", "labels": ["COUGH_PRODUCTIVE", "BODY_ACHES"] },
  { "id": 10, "input": "Barado ilong, d makahinga, tpos prang gripo ang runny nose. Huhu.", "labels": ["NASAL_CONGESTION", "RUNNY_NOSE"] },
  { "id": 11, "input": "Paos na ko sa sige ubo. My throat hurts tlga as in sumasakit lalamunan ko.", "labels": ["SORE_THROAT", "COUGH_GENERAL"] },
  { "id": 12, "input": "Sakit sa tyan, sige nako ug visit sa CR. Loose bowel movement is real.", "labels": ["STOMACH_ACHE", "DIARRHEA"] },
  { "id": 13, "input": "Body aches r everywhere... parang pinukpok ang likod ko. Nanlalamig pa.", "labels": ["BODY_ACHES"] },
  { "id": 14, "input": "Ang init ng katawan ko... 38.5. Giniginaw din nmn ako. Flu na ata.", "labels": ["FEVER", "BODY_ACHES"] },
  { "id": 15, "input": "Kumukulo tyan, hyperacidity galore. Masakit din ang likod sa sakit.", "labels": ["STOMACH_ACHE", "BODY_ACHES"] },
  { "id": 16, "input": "Makati balat, namumula everywhere. Allergy attack yata 'to.", "labels": ["RASHES", "ALLERGIC_RHINITIS"] },
  { "id": 17, "input": "Tuyo na ubo, dry cough for 3 days na. Di makatulog sa gabi.", "labels": ["COUGH_DRY"] },
  { "id": 18, "input": "Masakit ang tutunlan ko, paos pko. Sumasakit ang lalamunan pag lunok.", "labels": ["SORE_THROAT"] },
  { "id": 19, "input": "Kumikislot ang ulo, migraine malala. Tumitibok pa.", "labels": ["HEADACHE"] },
  { "id": 20, "input": "Nag-aalerdyi ako sa dust. Sipon and runny nose sige.", "labels": ["ALLERGIC_RHINITIS", "RUNNY_NOSE"] },
  { "id": 21, "input": "Mura'g nabun-og akong lawas. Masakit ang katawan, nanlalamig pko.", "labels": ["BODY_ACHES"] },
  { "id": 22, "input": "Hyperacidity is back. Buhol buhol ang tyan, sakit kaayo.", "labels": ["STOMACH_ACHE"] },
  { "id": 23, "input": "Sige cr... matubig ang dumi. Diko na kaya.", "labels": ["DIARRHEA"] },
  { "id": 24, "input": "Ubo with plema... productive cough feels heavy in the chest.", "labels": ["COUGH_PRODUCTIVE"] },
  { "id": 25, "input": "Barado ang ilong pero runny nose din. Weird but true.", "labels": ["NASAL_CONGESTION", "RUNNY_NOSE"] },
  { "id": 26, "input": "Init ng katawan, giniginaw... parang pinukpok ang joints ko.", "labels": ["FEVER", "BODY_ACHES"] },
  { "id": 27, "input": "Headache migraine tumitibok humahapdi ang ulo. Shocks.", "labels": ["HEADACHE"] },
  { "id": 28, "input": "Mahapdi ang lalamunan, masakit ang tutunlan ko. Paos nko.", "labels": ["SORE_THROAT"] },
  { "id": 29, "input": "Makati skin, rashes everywhere. Allergy na 'to.", "labels": ["RASHES", "ALLERGIC_RHINITIS"] },
  { "id": 30, "input": "Productive cough and ubo na general. Sige lang ubo.", "labels": ["COUGH_PRODUCTIVE", "COUGH_GENERAL"] },
  { "id": 31, "input": "Nanlalamig pero ang init ng katawan ko. Help po.", "labels": ["BODY_ACHES", "FEVER"] },
  { "id": 32, "input": "Loose bowel, sige cr, matubig ang dumi. So weak.", "labels": ["DIARRHEA"] },
  { "id": 33, "input": "Stomach ache buhol buhol, kumukulo tyan. Hyperacidity ata.", "labels": ["STOMACH_ACHE"] },
  { "id": 34, "input": "Dry cough dry cough dry cough. No phlegm at all.", "labels": ["COUGH_DRY"] },
  { "id": 35, "input": "Nasal congestion barado ilong d makahinga. Tired of this.", "labels": ["NASAL_CONGESTION"] },
  { "id": 36, "input": "Sumasakit ang lalamunan, my throat hurts, mahapdi tutunlan.", "labels": ["SORE_THROAT"] },
  { "id": 37, "input": "Migraine humahapdi ang ulo kumikislot tumitibok. Sakit.", "labels": ["HEADACHE"] },
  { "id": 38, "input": "Body aches masakit ang katawan parang pinukpok. Sakit body.", "labels": ["BODY_ACHES"] },
  { "id": 39, "input": "Ang init ng katawan, feverish feeling, giniginaw din.", "labels": ["FEVER", "BODY_ACHES"] },
  { "id": 40, "input": "Alerdyi sige sneeze runny nose and rashes.", "labels": ["ALLERGIC_RHINITIS", "RUNNY_NOSE", "RASHES"] },
  { "id": 41, "input": "D makalunok, mahapdi lalamunan ko. Throat is sore.", "labels": ["SORE_THROAT"] },
  { "id": 42, "input": "Ubo na may plema but d makalabas. Productive cough.", "labels": ["COUGH_PRODUCTIVE"] },
  { "id": 43, "input": "Hyperacidity, buhol buhol tyan, kumukulo. Sakit tyan.", "labels": ["STOMACH_ACHE"] },
  { "id": 44, "input": "Diarrhea loose bowel matubig dumi. Non-stop cr.", "labels": ["DIARRHEA"] },
  { "id": 45, "input": "Headache humahapdi ang ulo ko. Too much stress.", "labels": ["HEADACHE"] },
  { "id": 46, "input": "Dry cough no plema. Constant coughing only.", "labels": ["COUGH_DRY"] },
  { "id": 47, "input": "Nasal congestion barado ilong runny nose. Sipon.", "labels": ["NASAL_CONGESTION", "RUNNY_NOSE"] },
  { "id": 48, "input": "Masakit ang katawan, body aches parang pinukpok. Ouch.", "labels": ["BODY_ACHES"] },
  { "id": 49, "input": "Ang init ng katawan ko, feeling so hot. Feverish.", "labels": ["FEVER"] },
  { "id": 50, "input": "Alerdyi rashes makati skin namumula.", "labels": ["ALLERGIC_RHINITIS", "RASHES"] },
  { "id": 51, "input": "Paos and mahapdi ang lalamunan ko. Sore throat is bad.", "labels": ["SORE_THROAT"] },
  { "id": 52, "input": "Productive cough with lots of plema. Coughing deep.", "labels": ["COUGH_PRODUCTIVE"] },
  { "id": 53, "input": "Stomach cramps buhol buhol kumukulo ang tyan.", "labels": ["STOMACH_ACHE"] },
  { "id": 54, "input": "Sige cr matubig ang dumi. Diarrhea situation.", "labels": ["DIARRHEA"] },
  { "id": 55, "input": "Tumitibok ang ulo, humahapdi migraine feel.", "labels": ["HEADACHE"] },
  { "id": 56, "input": "Ubo general lang and nasal congestion. Cold and flu?", "labels": ["COUGH_GENERAL", "NASAL_CONGESTION"] },
  { "id": 57, "input": "Body aches all over, nanlalamig giniginaw pko.", "labels": ["BODY_ACHES"] },
  { "id": 58, "input": "Init ng katawan ko, ang init ko talaga. 39 degrees.", "labels": ["FEVER"] },
  { "id": 59, "input": "Alerdyi runny nose and sneezing non stop.", "labels": ["ALLERGIC_RHINITIS", "RUNNY_NOSE"] },
  { "id": 60, "input": "Masakit ang tutunlan pag lunok, paos pko.", "labels": ["SORE_THROAT"] },
  { "id": 61, "input": "Ubo na may plema productive ubo.", "labels": ["COUGH_PRODUCTIVE"] },
  { "id": 62, "input": "Hyperacidity stomach ache kumukulo tyan.", "labels": ["STOMACH_ACHE"] },
  { "id": 63, "input": "Lbm loose bowel sige cr matubig dumi.", "labels": ["DIARRHEA"] },
  { "id": 64, "input": "Migraine tumitibok humahapdi ulo ko. Pain.", "labels": ["HEADACHE"] },
  { "id": 65, "input": "Dry cough ubo na tuyo no mucus.", "labels": ["COUGH_DRY"] },
  { "id": 66, "input": "Nasal congestion barado ilong runny nose.", "labels": ["NASAL_CONGESTION", "RUNNY_NOSE"] },
  { "id": 67, "input": "Parang pinukpok ang likod body aches.", "labels": ["BODY_ACHES"] },
  { "id": 68, "input": "Giniginaw nanlalamig pro ang init ng katawan.", "labels": ["BODY_ACHES", "FEVER"] },
  { "id": 69, "input": "Makati skin namumula balat allergy.", "labels": ["RASHES", "ALLERGIC_RHINITIS"] },
  { "id": 70, "input": "Sore throat masakit ang lalamunan tutunlan.", "labels": ["SORE_THROAT"] },
  { "id": 71, "input": "Ubo plema productive general cough.", "labels": ["COUGH_PRODUCTIVE", "COUGH_GENERAL"] },
  { "id": 72, "input": "Buhol buhol tyan hyperacidity kumukulo.", "labels": ["STOMACH_ACHE"] },
  { "id": 73, "input": "Sige cr matubig dumi diarrhea loose bowel.", "labels": ["DIARRHEA"] },
  { "id": 74, "input": "Kumikislot ulo headache tumitibok migraine.", "labels": ["HEADACHE"] },
  { "id": 75, "input": "Ubo dry tuyo dry cough.", "labels": ["COUGH_DRY"] },
  { "id": 76, "input": "Barado ilong nasal congestion d makahinga.", "labels": ["NASAL_CONGESTION"] },
  { "id": 77, "input": "Nanlalamig body aches masakit katawan.", "labels": ["BODY_ACHES"] },
  { "id": 78, "input": "Ang init ng katawan ko talaga. Fever.", "labels": ["FEVER"] },
  { "id": 79, "input": "Nag aalerdyi makati balat rashes.", "labels": ["ALLERGIC_RHINITIS", "RASHES"] },
  { "id": 80, "input": "Throat hurts mahapdi lalamunan sumasakit tutunlan.", "labels": ["SORE_THROAT"] }
]

def norm(labels):
    return sorted(set(labels))

exact = partial = failed = 0
mismatches = []
for case in cases:
    report = extract_symptoms_hybrid_report(
        case['input'],
        semantic_threshold=0.65,
        semantic_top_margin=0.08,
        semantic_max_symptoms=3,
        enable_semantic_fallback=True,
    )
    got = norm(report.get('final', {}).get('symptoms', []))
    exp = norm(case['labels'])
    gs, es = set(got), set(exp)
    if gs == es:
        exact += 1
    elif gs & es:
        partial += 1
        mismatches.append({
            'id': case['id'], 'status': 'PARTIAL', 'expected': exp, 'got': got,
            'missing': sorted(es - gs), 'extra': sorted(gs - es), 'input': case['input']
        })
    else:
        failed += 1
        mismatches.append({
            'id': case['id'], 'status': 'FAILED', 'expected': exp, 'got': got,
            'missing': sorted(es - gs), 'extra': sorted(gs - es), 'input': case['input']
        })

print(f'SUMMARY {len(cases)} total | {exact} exact | {partial} partial | {failed} failed')
for row in mismatches:
    print(json.dumps(row, ensure_ascii=False))
