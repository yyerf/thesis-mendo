"""Regression tests for the semantic audit-row partition.

On the Raspberry Pi, MiniLM produces noisy-but-close raw cosine scores for
short multilingual phrases (DIARRHEA's best anchor can score 0.7275 on a
fever sentence while FEVER's scores 0.7264). The selection pipeline was
already lexically guarded, but the *audit trace* still ranked vetoed symptoms
like DIARRHEA above the real candidates, which looked like the system was
"doing diarrhea" on a fever input.

These tests fake the extractor's output (mirroring real MiniLM behaviour) and
assert that:
  - vetoed symptoms land in lexical_guard_vetoed, not near_miss_rejected
  - candidate rows sort before vetoed rows in the stage trace
  - the final symptom set is unaffected
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mendo_core.step3_hybrid import extract_symptoms_hybrid_report
from mendo_core.prediction_pipeline import predict_symptoms


# Simulates what paraphrase-multilingual-MiniLM-L12-v2 actually returns for a
# Cebuano fever sentence: noisy scores where DIARRHEA's best anchor beats
# FEVER's, plus a handful of above-threshold false positives.
_SEMANTIC_DIAG = [
    SimpleNamespace(symptom="DIARRHEA", score=0.7275, best_anchor="nagkalibang ko"),
    SimpleNamespace(symptom="FEVER", score=0.7264, best_anchor="init ang noo ko"),
    SimpleNamespace(symptom="STOMACH_ACHE", score=0.7251, best_anchor="nagsusuka ako"),
    SimpleNamespace(symptom="BODY_ACHES", score=0.7218, best_anchor="bug at kaayo akong lawas"),
    SimpleNamespace(symptom="HEADACHE", score=0.7025, best_anchor="masakit ang ulo ko"),
    SimpleNamespace(symptom="SORE_THROAT", score=0.6855, best_anchor="garas ang tilaok pag mutulon ko"),
    SimpleNamespace(symptom="RASHES", score=0.6736, best_anchor="nagpula akong panit unya katol siya"),
    SimpleNamespace(symptom="NASAL_CONGESTION", score=0.6600, best_anchor="weird ang ilong ko"),
    SimpleNamespace(symptom="RUNNY_NOSE", score=0.5900, best_anchor="sipon"),
    SimpleNamespace(symptom="ALLERGIC_RHINITIS", score=0.5800, best_anchor="makati ilong"),
    SimpleNamespace(symptom="COUGH_GENERAL", score=0.5700, best_anchor="inuubo ako"),
    SimpleNamespace(symptom="COUGH_DRY", score=0.5600, best_anchor="tuyong ubo"),
    SimpleNamespace(symptom="COUGH_PRODUCTIVE", score=0.5500, best_anchor="may plema"),
]

# DIARRHEA's raw score is the single highest cosine we supply.
_FAKE_EXTRACTOR = SimpleNamespace(
    analyze=lambda _input, threshold=0.65: (
        [d.symptom for d in _SEMANTIC_DIAG if d.score >= threshold],
        list(_SEMANTIC_DIAG),
    )
)


def _run(text: str = "wala koy ubo pero naa koy fever"):
    with patch("mendo_core.step3_hybrid._get_semantic_extractor", return_value=_FAKE_EXTRACTOR):
        return extract_symptoms_hybrid_report(
            text,
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=2,
            enable_semantic_fallback=True,
        )


def test_diarrhea_not_final_on_fever_sentence():
    report = _run()
    assert report["final"]["symptoms"] == ["FEVER"]


def test_vetoed_rows_kept_out_of_near_miss():
    with patch("mendo_core.step3_hybrid._get_semantic_extractor", return_value=_FAKE_EXTRACTOR):
        trace = predict_symptoms("wala koy ubo pero naa koy fever")
    semantic = trace["semantic"]
    near_miss = {r["symptom"] for r in semantic.get("near_miss_rejected", [])}
    vetoed = {r["symptom"] for r in semantic.get("lexical_guard_vetoed", [])}
    assert "DIARRHEA" in vetoed
    assert "DIARRHEA" not in near_miss
    assert "FEVER" not in vetoed


def test_candidate_rows_precede_vetoed_rows_in_stage():
    report = _run()
    sem = next(s for s in report["stages"] if s["stage"] == "semantic")
    scores = sem["scores"]
    first_vetoed = next(i for i, r in enumerate(scores) if r.get("vetoed"))
    non_vetoed_relevant = [i for i, r in enumerate(scores) if not r.get("vetoed")]
    assert non_vetoed_relevant
    assert all(i < first_vetoed for i in non_vetoed_relevant)


def test_vetoed_rows_carry_reason():
    report = _run()
    sem = next(s for s in report["stages"] if s["stage"] == "semantic")
    diarrhea = next(r for r in sem["scores"] if r["symptom"] == "DIARRHEA")
    assert diarrhea["vetoed"] is True
    assert diarrhea["veto_reason"] == "rejected_by_lexical_guard_or_safety_filter"


def test_semantic_guid_does_not_hijack_legit_symptom():
    # Same raw scores, but a genuine diarrhea sentence: DIARRHEA survives the
    # lexical guard so it IS a candidate and gets a real decision.
    text = "grabe na gyud ang nagkalibang ko ug sakit tiyan"
    with patch("mendo_core.step3_hybrid._get_semantic_extractor", return_value=_FAKE_EXTRACTOR):
        report = extract_symptoms_hybrid_report(
            text,
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=2,
            enable_semantic_fallback=True,
        )
    sem = next(s for s in report["stages"] if s["stage"] == "semantic")
    diarrhea_row = next(r for r in sem["scores"] if r["symptom"] == "DIARRHEA")
    assert not diarrhea_row.get("vetoed")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
        except AssertionError as exc:
            print(f"FAIL  {fn.__name__}: {exc}")
        else:
            passed += 1
            print(f"ok    {fn.__name__}")
    print(f"\n{passed}/{len(fns)} passed")
    sys.exit(0 if passed == len(fns) else 1)