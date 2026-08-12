"""Headache free-text intake tests (deterministic, no model required).

Runnable two ways:
    python testing/test_headache_intake.py        # simple runner
    pytest testing/test_headache_intake.py        # pytest mode
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mendo_core.headache_intake import (
    classify_headache_text,
    promote_bare_headache_cue,
)


def _key(text):
    return classify_headache_text(text).get("key")


def _resolution(text):
    return classify_headache_text(text).get("resolution")


# ── Bare-cue promotion (e.g. "sinus" typed alone) ──────────────────────────

def test_promote_bare_sinus():
    out = promote_bare_headache_cue("sinus")
    assert out is not None
    assert out["key"] == "sinus"


def test_promote_bare_sinusitis():
    out = promote_bare_headache_cue("sinusitis")
    assert out is not None
    assert out["key"] == "sinus"


def test_promote_bare_high_blood():
    out = promote_bare_headache_cue("high blood")
    assert out is not None
    assert out["key"] == "hypertension"
    assert out["danger"] == "red_flag"


def test_promote_bare_tension():
    assert promote_bare_headache_cue("tension")["key"] == "tension"


def test_promote_bare_migraine():
    assert promote_bare_headache_cue("migraine")["key"] == "migraine"


def test_promote_bare_regla():
    assert promote_bare_headache_cue("regla")["key"] == "hormone"


def test_no_promote_weak_only_stress():
    assert promote_bare_headache_cue("stress") is None


def test_no_promote_negated_sinus():
    assert promote_bare_headache_cue("wala koy sinus") is None


def test_no_promote_generic_pain():
    assert promote_bare_headache_cue("sakit kaayo") is None


# ── Direct keyword / tag routing ───────────────────────────────────────────

def test_sinus_single_word():
    assert _key("sinus") == "sinus"


def test_sinusitis():
    assert _key("sinusitis") == "sinus"


def test_sinus_full_description():
    assert _key(
        "deep constant pressure and throbbing behind cheeks and forehead "
        "due to sinus congestion"
    ) == "sinus"


def test_sinus_bisaya_pressure():
    assert _key("presyon sa akong aping ug agtang tungod sa sinus") == "sinus"


def test_tension_description():
    assert _key(
        "squeezing dull ache around the head caused by stress or muscle tension"
    ) == "tension"


def test_tension_stress_headache():
    assert _key("stress headache") == "tension"


def test_migraine_word():
    assert _key("migraine") == "migraine"


def test_migraine_aura():
    assert _key("migraine with aura, sensitive to light") == "migraine"


def test_hormone_regla():
    assert _key("sakit ulo ko kada regla") == "hormone"


def test_hormone_before_period():
    assert _key("headache before my period") == "hormone"


def test_cluster_around_eye():
    assert _key("piercing pain around one eye in bursts") == "cluster"


def test_caffeine_no_coffee():
    assert _key("headache because i skipped my coffee this morning") == "caffeine"


def test_caffeine_walay_kape():
    assert _key("labad ulo kay walay kape sa buntag") == "caffeine"


def test_rebound_painkiller_overuse():
    assert _key("every day headache from too much painkiller") == "rebound"


def test_rebound_medicine_overuse():
    assert _key("palaging umiinom ng gamot kaya sakit ulo") == "rebound"


def test_ice_pick_stabbing():
    assert _key("brief stabbing pain that lasts seconds") == "ice_pick"


def test_ice_pick_sharp_headache():
    assert _key("sharp headache") == "ice_pick"


def test_ice_pick_sharp_pain():
    assert _key("sharp pain sa akong ulo") == "ice_pick"


def test_ice_pick_tusok_tusok():
    assert _key("tusok tusok sa ulo") == "ice_pick"


def test_ice_pick_tusok_tusok_bare():
    assert _key("tusok tusok") == "ice_pick"


def test_ice_pick_nagtusok():
    assert _key("nagtusok ang ulo ko") == "ice_pick"


def test_ice_pick_tinutusok():
    assert _key("parang tinutusok ang ulo ko") == "ice_pick"


def test_ice_pick_promotes_bare_cue():
    out = promote_bare_headache_cue("tusok tusok sa ulo")
    assert out is not None
    assert out["key"] == "ice_pick"


def test_ice_pick_negated_not_promoted():
    assert promote_bare_headache_cue("wala naman akong tusok tusok") is None


def test_hemicrania_never_stops():
    assert _key("continuous one sided headache that never stops") == "hemicrania"


# ── Red-zone auto-refer (danger must be red_flag) ───────────────────────────

def test_thunderclap_auto_refer():
    out = classify_headache_text("worst headache ever, peak in seconds")
    assert out["key"] == "thunderclap"
    assert out["danger"] == "red_flag"
    assert out["resolution"] == "red_zone"


def test_hypertension_auto_refer():
    out = classify_headache_text("high blood pressure ang sakit sa ulo")
    assert out["key"] == "hypertension"
    assert out["danger"] == "red_flag"
    assert out["resolution"] == "red_zone"


def test_post_traumatic_auto_refer():
    out = classify_headache_text("sakit ulo human sa bangga, na concussion ko")
    assert out["key"] == "post_traumatic"
    assert out["danger"] == "red_flag"


def test_spinal_auto_refer():
    out = classify_headache_text("worse when standing, better lying down")
    assert out["key"] == "spinal"
    assert out["danger"] == "red_flag"


def test_exertion_after_gym():
    assert _key("headache right after lifting weights") == "exertion"


def test_red_zone_beats_green_candidate():
    out = classify_headache_text("high blood pressure and migraine")
    assert out["key"] == "hypertension"
    assert out["resolution"] == "red_zone"


# ── No false positives / ambiguity guards ───────────────────────────────────

def test_generic_headache_stays_untyped():
    assert _key("sakit kaayo akong ulo") is None


def test_fever_input_untouched():
    assert _key("wala koy ubo pero naa koy fever") is None


def test_multiword_border_does_not_half_match():
    # "presyon" appears inside "altapresyon"; standalone "presyon" is not a tag.
    assert _key("altapresyon") == "hypertension"


def test_sinus_presyon_phrase_does_not_leak_hypertension():
    # "presyon sa aping" (cheek pressure) must stay sinus, not hypertension.
    out = classify_headache_text("presyon sa aping ug agtang")
    assert out["key"] == "sinus"


def test_ambiguous_weak_only_returns_none():
    out = classify_headache_text("throbbing and stress lang ang ulo ko")
    # weak words shared by two types (migraine + tension) -> no confident type
    assert out["resolution"] == "ambiguous"
    assert out["key"] is None


def test_empty_input():
    assert _key("") is None


def test_no_collision_tension_vs_hormone_stress():
    # "stress" alone is a weak tension tag; must not fire without a headache cue
    assert _key("stress headache") == "tension"


# ── Run mode ────────────────────────────────────────────────────────────────

def _run_all():
    import types

    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and isinstance(v, types.FunctionType)]
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
    return passed == len(fns)


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
