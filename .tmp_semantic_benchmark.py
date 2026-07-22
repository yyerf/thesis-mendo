from mendo_core.step3_hybrid import extract_symptoms_hybrid_report

cases = [
    {
        'case_id': 'SEM_001',
        'scenario': 'Metaphorical Body Aches',
        'input': 'Mura kog gilat-an sa hilanat, tibuok lawas nako bug-at kaayo.',
        'expected': ['BODY_ACHES', 'FEVER'],
    },
    {
        'case_id': 'SEM_002',
        'scenario': 'High-Context Stomach Issues',
        'input': "I've been running to the loo every 10 mins, purely liquid na talaga.",
        'expected': ['DIARRHEA'],
    },
    {
        'case_id': 'SEM_003',
        'scenario': 'Descriptive Nasal Blockage',
        'input': 'Locked na locked yung nose ko, cannot breathe through my nostrils anymore.',
        'expected': ['NASAL_CONGESTION'],
    },
    {
        'case_id': 'SEM_004',
        'scenario': 'Phlegm Description (Productive)',
        'input': "My chest feels like there's a lot of glue and I'm bringing up yellow stuff.",
        'expected': ['COUGH_PRODUCTIVE'],
    },
    {
        'case_id': 'SEM_005',
        'scenario': 'Trilingual Throat Irritation',
        'input': "Naay garas akong tilaok pag mutulon ko, it's so itchy inside my neck area.",
        'expected': ['SORE_THROAT'],
    },
    {
        'case_id': 'SEM_006',
        'scenario': 'Idiomatic Headache',
        'input': 'I feel like my brain is trying to explode from the inside, pulsing non-stop.',
        'expected': ['HEADACHE'],
    },
    {
        'case_id': 'SEM_007',
        'scenario': 'Allergy-Induced Skin Issues',
        'input': 'I touched some dust and now my skin is on fire and covered in red bumps.',
        'expected': ['ALLERGIC_RHINITIS', 'RASHES'],
    },
    {
        'case_id': 'SEM_008',
        'scenario': 'Negation with Semantic Distraction',
        'input': 'Ubod ng sakit ang ulo ko pero wala namang init ang katawan ko.',
        'expected': ['HEADACHE'],
    },
    {
        'case_id': 'VAGUE_001',
        'scenario': 'Vague Patient',
        'input': 'Doc, parang pinupukpok ang bumbunan ko tapos pag humihinga ako may parang kumakalansing sa dibdib ko.',
        'expected': ['HEADACHE', 'COUGH_PRODUCTIVE'],
    },
]

exact = partial = failed = 0
for case in cases:
    report = extract_symptoms_hybrid_report(
        case['input'],
        semantic_threshold=0.65,
        semantic_top_margin=0.08,
        semantic_max_symptoms=3,
        enable_semantic_fallback=True,
    )
    final = sorted(report.get('final', {}).get('symptoms', []))
    source = report.get('final', {}).get('source')
    dict_stage = next((s for s in report.get('stages', []) if s.get('stage') == 'dictionary'), {})
    sem_stage = next((s for s in report.get('stages', []) if s.get('stage') == 'semantic'), {})
    detected_dict = dict_stage.get('detected', [])
    sem_selected = sem_stage.get('detected_selected', []) if sem_stage else []
    expected = sorted(case['expected'])
    status = 'EXACT' if set(final) == set(expected) else ('PARTIAL' if set(final) & set(expected) else 'FAILED')
    if status == 'EXACT':
        exact += 1
    elif status == 'PARTIAL':
        partial += 1
    else:
        failed += 1
    print('=' * 80)
    print(f"{case['case_id']} | {case['scenario']} | {status}")
    print('input    :', case['input'])
    print('expected :', expected)
    print('final    :', final)
    print('source   :', source)
    print('dict     :', detected_dict)
    print('semantic :', sem_selected)
    if sem_stage.get('scores'):
        top3 = sem_stage['scores'][:3]
        simplified = [(row['symptom'], round(row['score'], 3)) for row in top3]
        print('top3     :', simplified)
print('=' * 80)
print(f'SUMMARY total={len(cases)} exact={exact} partial={partial} failed={failed}')
