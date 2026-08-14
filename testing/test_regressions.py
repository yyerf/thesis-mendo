import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mendo_core.step3_hybrid import detect_red_flags, extract_symptoms_hybrid_report
from mendo_core.step4_recommend import (
    DATASET_DEFAULT,
    DURATION_THRESHOLDS,
    check_duration_safety,
    get_duration_question,
    load_mendo_dataset,
    parse_duration_days,
    recommend_from_dataset,
)
from mendo_core.step1 import extract_conditions
from web.app import app
import mendo_core.interaction_logger as _ilog


class RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _ilog._disabled = True          # don't pollute production log during tests
        cls.rows = load_mendo_dataset(DATASET_DEFAULT)
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        _ilog._disabled = False

    def test_diarrhea_plain_input_asks_for_context(self):
        report = extract_symptoms_hybrid_report(
            "gi kalibangga ko",
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=3,
            enable_semantic_fallback=True,
        )
        symptoms = report.get("final", {}).get("symptoms", [])
        self.assertIn("DIARRHEA", symptoms)

        rec = recommend_from_dataset(symptoms, self.rows, user_input="gi kalibangga ko")
        self.assertEqual(rec.get("action"), "ask_clarify")
        self.assertEqual(rec.get("clarify_type"), "DIARRHEA_CONTEXT")

    def test_diarrhea_non_infectious_clarify_returns_recommendation(self):
        response = self.client.post(
            "/consult/api/context-clarify",
            json={
                "original_symptoms": ["DIARRHEA"],
                "clarify_type": "DIARRHEA_CONTEXT",
                "clarification": "DIARRHEA_NON_INFECTIOUS",
                "age": 21,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        recommendation = data["recommendation"]
        self.assertEqual(recommendation.get("action"), "recommend")
        brands = [row["brand"] for row in recommendation.get("recommendations", [])]
        self.assertIn("Loperamide", brands)

    def test_diarrhea_food_poisoning_excludes_loperamide(self):
        response = self.client.post(
            "/consult/api/context-clarify",
            json={
                "original_symptoms": ["DIARRHEA"],
                "clarify_type": "DIARRHEA_CONTEXT",
                "clarification": "DIARRHEA_FOOD_POISONING",
                "age": 21,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        recommendation = data["recommendation"]
        self.assertEqual(recommendation.get("action"), "recommend")
        brands = [row["brand"] for row in recommendation.get("recommendations", [])]
        self.assertIn("Erceflora", brands)
        self.assertNotIn("Loperamide", brands)

    def test_difficulty_breathing_red_flag(self):
        flags = detect_red_flags("lisod muginhawa kaayo")
        self.assertTrue(any(flag["flag"] == "difficulty_breathing" for flag in flags))

    def test_blood_in_stool_red_flag_variants(self):
        for text in [
            "nag dugo akong tae",
            "may dugo ang aking tae",
            "may blood ang tae",
            "may dugo ang aking bawas",
        ]:
            with self.subTest(text=text):
                flags = detect_red_flags(text)
                self.assertTrue(any(flag["flag"] == "blood_in_stool" for flag in flags))

    def test_high_fever_red_flag_variants(self):
        for text in [
            "fever ko 40 ang temp",
            "lagnat na 41 degrees",
            "temperature 42 with fever",
            "init ang lawas, temp 40",
        ]:
            with self.subTest(text=text):
                flags = detect_red_flags(text)
                self.assertTrue(any(flag["flag"] == "high_fever_prolonged" for flag in flags))

    def test_hyperthermia_ignores_age_weight_numbers(self):
        for text in [
            "may fever siya, 40 years old na",
            "lagnat tapos 41 kg timbang",
            "temp ko 42 years old",  # malformed but should be ignored by lexical exclusion
        ]:
            with self.subTest(text=text):
                flags = detect_red_flags(text)
                self.assertFalse(any(flag["flag"] == "high_fever_prolonged" for flag in flags), flags)

    def test_chest_pain_exclusion_for_cough_context(self):
        text = "masakit dibdib ko kakaubo at may plema"
        flags = detect_red_flags(text)
        self.assertFalse(any(flag["flag"] == "chest_pain" for flag in flags), flags)

    def test_respiratory_emergency_detected_by_cooccurrence(self):
        for text in [
            "hirap huminga ako ngayon",
            "lisod muginhawa kaayo",
            "nahihirapan ako sa paghinga",
        ]:
            with self.subTest(text=text):
                flags = detect_red_flags(text)
                self.assertTrue(any(flag["flag"] == "difficulty_breathing" for flag in flags), flags)

    def test_dengue_warning_fever_with_rashes(self):
        flags = detect_red_flags("may lagnat ako at may pantal at red spots")
        self.assertTrue(any(flag["flag"] == "dengue_warning" for flag in flags), flags)

    def test_dengue_warning_exclusion_bite_allergy_context(self):
        for text in [
            "may lagnat at pantal dahil sa kagat ng insekto",
            "fever and rashes from allergy",
            "pantal at lagnat dahil sa bite",
        ]:
            with self.subTest(text=text):
                flags = detect_red_flags(text)
                self.assertFalse(any(flag["flag"] == "dengue_warning" for flag in flags), flags)

    def test_stroke_warning_numb_face_half_side(self):
        for text in [
            "manhid kalahati ng mukha ko",
            "numb yung half face ko",
            "pamamanhid sa one side ng mukha",
        ]:
            with self.subTest(text=text):
                flags = detect_red_flags(text)
                self.assertTrue(any(flag["flag"] == "stroke_warning" for flag in flags), flags)

    def test_stroke_warning_exclusion_tooth_context(self):
        for text in [
            "manhid ngipin ko",
            "numb tooth after bunot",
        ]:
            with self.subTest(text=text):
                flags = detect_red_flags(text)
                self.assertFalse(any(flag["flag"] == "stroke_warning" for flag in flags), flags)

    def test_severe_dehydration_diarrhea_no_urine(self):
        for text in [
            "nagtatae ako tapos walang ihi",
            "diarrhea with no urine since morning",
            "kalibang pero walay ihi",
        ]:
            with self.subTest(text=text):
                flags = detect_red_flags(text)
                self.assertTrue(any(flag["flag"] == "severe_dehydration" for flag in flags), flags)

    def test_pregnancy_contraindication_with_proxy_exclusions(self):
        flags = detect_red_flags("buntis ako at may lagnat")
        self.assertTrue(any(flag["flag"] == "pregnancy_contraindication" for flag in flags), flags)

        for text in [
            "buntis yung asawa ko, bibili lang ako",
            "pregnant sister ko ang iinuman",
            "misis ko buntis, para sa kanya ito",
        ]:
            with self.subTest(text=text):
                proxy_flags = detect_red_flags(text)
                self.assertFalse(any(flag["flag"] == "pregnancy_contraindication" for flag in proxy_flags), proxy_flags)

    def test_direct_emergency_terms(self):
        for text, expected in [
            ("nag seizure siya kanina", "seizure"),
            ("nahimatay ako", "loss_of_consciousness"),
        ]:
            with self.subTest(text=text):
                flags = detect_red_flags(text)
                self.assertTrue(any(flag["flag"] == expected for flag in flags), flags)

    def test_head_bleeding_detects_gadugo_variant(self):
        flags = detect_red_flags("gadugo akong ulo")
        self.assertTrue(any(flag["flag"] == "head_bleeding" for flag in flags), flags)

    def test_gadugo_ulo_pipeline_triages_not_headache(self):
        text = "gadugo akong ulo"
        report = extract_symptoms_hybrid_report(
            text,
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=2,
            enable_semantic_fallback=True,
        )
        red_flags = report.get("red_flags", [])
        self.assertTrue(any(f["flag"] == "head_bleeding" for f in red_flags), red_flags)

        symptoms = report.get("final", {}).get("symptoms", [])
        rec = recommend_from_dataset(symptoms, self.rows, red_flags=red_flags, user_input=text)
        self.assertEqual(rec.get("action"), "triage")

    def test_headache_detects_gasakit_ulo_variant(self):
        report = extract_symptoms_hybrid_report(
            "murag gasakit akong ulo",
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=2,
            enable_semantic_fallback=False,
        )
        symptoms = report.get("final", {}).get("symptoms", [])
        self.assertIn("HEADACHE", symptoms)

    def test_ever_never_do_not_fire_fever_fuzzy_rescue(self):
        # "ever"/"never" are edit-distance-1 from "fever"; must not trigger FEVER.
        for text in [
            "worst headache ever",
            "i never get headaches",
        ]:
            with self.subTest(text=text):
                report = extract_symptoms_hybrid_report(
                    text,
                    semantic_threshold=0.65,
                    semantic_top_margin=0.08,
                    semantic_max_symptoms=2,
                    enable_semantic_fallback=False,
                )
                symptoms = report.get("final", {}).get("symptoms", [])
                self.assertNotIn("FEVER", symptoms, text)

    def test_fever_typo_rescue_still_works(self):
        report = extract_symptoms_hybrid_report(
            "my lgnat is gone",
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=2,
            enable_semantic_fallback=False,
        )
        symptoms = report.get("final", {}).get("symptoms", [])
        self.assertIn("FEVER", symptoms)

    def test_hypertension_primary_complaint_is_red_flag(self):
        for text in [
            "naa koy high blood",
            "mataas blood pressure ko",
            "hypertension ako",
        ]:
            with self.subTest(text=text):
                flags = detect_red_flags(text)
                self.assertTrue(any(flag["flag"] == "hypertension_risk" for flag in flags), flags)

    def test_hypertension_incidental_after_contrastive_not_triaged(self):
        text = "May sipon at ubo ako, pero may high blood ako"
        flags = detect_red_flags(text)
        self.assertFalse(any(flag["flag"] == "hypertension_risk" for flag in flags), flags)

    def test_hemoptysis_does_not_trigger_on_high_blood_context(self):
        text = "May sipon at ubo ako, pero may high blood ako"
        flags = detect_red_flags(text)
        self.assertFalse(any(flag["flag"] == "hemoptysis" for flag in flags), flags)

    def test_hemoptysis_does_not_trigger_when_blood_is_negated(self):
        for text in [
            "naa koy ubo pero walay dugo",
            "may ubo ako pero walang dugo",
            "I have cough but no blood",
        ]:
            with self.subTest(text=text):
                flags = detect_red_flags(text)
                self.assertFalse(any(flag["flag"] == "hemoptysis" for flag in flags), flags)

    def test_nonproductive_cough_maps_to_dry(self):
        report = extract_symptoms_hybrid_report(
            "nonproductive cough, no difficulty of breathing, no fever",
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=3,
            enable_semantic_fallback=False,
        )
        symptoms = report.get("final", {}).get("symptoms", [])
        self.assertIn("COUGH_DRY", symptoms)
        self.assertNotIn("COUGH_PRODUCTIVE", symptoms)

    def test_gakurot_phrase_includes_headache(self):
        report = extract_symptoms_hybrid_report(
            "gakurot akong ulo tpos naay sipon ug ubo",
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=3,
            enable_semantic_fallback=False,
        )
        symptoms = report.get("final", {}).get("symptoms", [])
        self.assertIn("HEADACHE", symptoms)
        self.assertIn("RUNNY_NOSE", symptoms)
        self.assertIn("COUGH_GENERAL", symptoms)

    def test_nose_bleeding_does_not_become_congestion(self):
        report = extract_symptoms_hybrid_report(
            "blood on my nose",
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=3,
            enable_semantic_fallback=True,
        )
        symptoms = report.get("final", {}).get("symptoms", [])
        self.assertNotIn("NASAL_CONGESTION", symptoms)
        self.assertNotIn("RUNNY_NOSE", symptoms)
        self.assertEqual(symptoms, [])

    def test_blocked_nose_never_double_detects_runny(self):
        """'blocked/stuffy nose' must detect congestion only — a blocked nose
        has a congestion cue, not a dripping cue, so RUNNY_NOSE must not leak in
        from the semantic layer even when it clears the cosine threshold."""
        for text in [
            "my nose has been blocked since morning",
            "nakabara ang ilong ko",
            "barado ang ilong ko",
            "I have stuffy nose and its difficult to breathe through it",
        ]:
            with self.subTest(text=text):
                report = extract_symptoms_hybrid_report(
                    text,
                    semantic_threshold=0.65,
                    semantic_top_margin=0.08,
                    semantic_max_symptoms=3,
                    enable_semantic_fallback=True,
                )
                symptoms = report.get("final", {}).get("symptoms", [])
                self.assertIn("NASAL_CONGESTION", symptoms, text)
                self.assertNotIn("RUNNY_NOSE", symptoms, text)

    def test_blocked_nose_recommends_decongestant_not_runny_clarify(self):
        """Pure congestion (no dripping cue) must go straight to a decongestant
        recommendation, never the runny-nose SIPON_CONTEXT clarification."""
        for text in [
            "my nose has been blocked since morning",
            "I have stuffy nose and its difficult to breathe through it",
            "barado ang ilong ko",
        ]:
            with self.subTest(text=text):
                report = extract_symptoms_hybrid_report(
                    text,
                    semantic_threshold=0.65,
                    semantic_top_margin=0.08,
                    semantic_max_symptoms=3,
                    enable_semantic_fallback=True,
                )
                symptoms = report.get("final", {}).get("symptoms", [])
                rec = recommend_from_dataset(symptoms, self.rows, user_input=text)
                self.assertEqual(rec.get("action"), "recommend", text)
                self.assertNotEqual(rec.get("clarify_type"), "SIPON_CONTEXT", text)
                brands = [row["brand"] for row in rec.get("recommendations", [])]
                self.assertIn("Neozep", brands, text)

    def test_plain_headache_does_not_pull_cold_meds(self):
        rec = recommend_from_dataset(["HEADACHE"], self.rows, user_input="sakit akong ulo")
        self.assertEqual(rec.get("action"), "recommend")
        brands = [row["brand"] for row in rec.get("recommendations", [])]
        self.assertIn("Biogesic", brands)
        self.assertIn("Advil", brands)
        self.assertFalse(any(brand in {"Bioflu", "Neozep", "Symdex"} for brand in brands))

    def test_hypertension_filters_decongestant_cold_combos(self):
        text = "May sipon at tuyong ubo ako, pero may high blood ako"
        rec = recommend_from_dataset(
            ["RUNNY_NOSE", "COUGH_DRY"],
            self.rows,
            user_input=text,
            detected_conditions=["HYPERTENSION"],
        )
        self.assertEqual(rec.get("action"), "recommend")

        brands = [row["brand"] for row in rec.get("recommendations", [])]
        blocked_brands = [row.get("brand", "") for row in rec.get("blocked_recommendations", [])]
        joined_blocked = " ".join(blocked_brands).lower()

        self.assertNotIn("Bioflu", brands)
        self.assertFalse(any("Neozep" in b for b in brands))
        self.assertIn("neozep", joined_blocked)
        self.assertTrue(
            any(name in joined_blocked for name in ("tuseran", "symdex", "neozep"))
        )

        # Ensure no decongestant ingredient survives recommendation list.
        rec_ingredients = " ".join(
            (row.get("active_ingredients") or "")
            for row in rec.get("recommendations", [])
        ).lower()
        self.assertNotIn("phenylephrine", rec_ingredients)
        self.assertNotIn("pseudoephedrine", rec_ingredients)

    def test_hypertension_runny_nose_prefers_plain_antihistamine(self):
        rec = recommend_from_dataset(
            ["RUNNY_NOSE"],
            self.rows,
            user_input="may sipon ako at may high blood",
            context_override="SIPON_ALLERGY",
            detected_conditions=["HYPERTENSION"],
        )
        self.assertEqual(rec.get("action"), "recommend")

        brands = [row["brand"] for row in rec.get("recommendations", [])]
        self.assertIn("Cetirizine", brands)

        # Explicitly ensure common decongestant cold combos are filtered out.
        self.assertNotIn("Bioflu", brands)
        self.assertFalse(any("Neozep" in b for b in brands))

    def test_empty_symptom_list_returns_no_match(self):
        rec = recommend_from_dataset([], self.rows, user_input="asdasd")
        self.assertEqual(rec.get("action"), "no_match")
        self.assertEqual(rec.get("recommendations"), [])

    # ── New regression tests for latest fixes ──────────────────────────────

    def test_naay_dugo_gamay_bisaya_red_flag(self):
        """Bisaya blood-in-stool with filler words must trigger red flag."""
        for text in [
            "naay dugo gamay sa akong tae",
            "naay dugo sa akong tae",
            "naay dugo akong bawas",
        ]:
            with self.subTest(text=text):
                flags = detect_red_flags(text)
                self.assertTrue(
                    any(f["flag"] == "blood_in_stool" for f in flags),
                    f"Expected blood_in_stool for '{text}', got {flags}",
                )

    def test_diarrhea_typo_semantic_fallback(self):
        """Common misspelling 'diarreha' should still extract DIARRHEA."""
        report = extract_symptoms_hybrid_report(
            "diarreha",
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=3,
            enable_semantic_fallback=True,
        )
        symptoms = report.get("final", {}).get("symptoms", [])
        self.assertIn("DIARRHEA", symptoms)

    def test_blood_in_stool_bisaya_triggers_triage(self):
        """Full pipeline: 'naay dugo gamay sa akong tae' → triage (not recommend)."""
        report = extract_symptoms_hybrid_report(
            "naay dugo gamay sa akong tae",
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=3,
            enable_semantic_fallback=True,
        )
        red_flags = report.get("red_flags", [])
        self.assertTrue(any(f["flag"] == "blood_in_stool" for f in red_flags))

        symptoms = report.get("final", {}).get("symptoms", [])
        rec = recommend_from_dataset(symptoms, self.rows, red_flags=red_flags, user_input="naay dugo gamay sa akong tae")
        self.assertEqual(rec.get("action"), "triage")

    def test_logger_new_fields_present(self):
        """Consented SQLite audit rows include type, context, and trace steps."""
        import tempfile
        from mendo_core.interaction_logger import get_interaction_logs, log_interaction
        import mendo_core.interaction_logger as _ilog2

        old_path = _ilog2._DB_PATH
        temp_dir = tempfile.TemporaryDirectory()
        _ilog2._DB_PATH = str(Path(temp_dir.name) / "audit.sqlite")
        _ilog2._disabled = False
        try:
            log_interaction(
                user_input="unit test input",
                extracted_symptoms=["HEADACHE"],
                extraction_source="dictionary",
                pipeline_stages=[
                    {"stage": "dictionary", "used": True, "detected": ["HEADACHE"], "details": []},
                    {"stage": "semantic", "used": True, "available": True, "detected_raw": [], "detected_selected": []},
                ],
                recommendation={"action": "recommend", "recommendations": [{"brand": "Biogesic", "active_ingredients": "Paracetamol"}]},
                red_flags=[],
                interaction_type="initial_analysis",
                context_override=None,
                severity=5,
                age=25,
                session_id="unit_test",
                research_consent=True,
            )
            last = get_interaction_logs(limit=1)[0]

            self.assertEqual(last["interaction_type"], "initial_analysis")
            self.assertIsNone(last["context_override"])
            self.assertEqual(last["session_id"], "unit_test")
            self.assertEqual(last["pipeline_stages"][0]["step"], 1)
            self.assertEqual(last["pipeline_stages"][1]["step"], 2)
            self.assertEqual(last["severity"], 5)
        finally:
            _ilog2._DB_PATH = old_path
            _ilog2._disabled = True
            temp_dir.cleanup()

    def test_stomach_ache_detects_bisaya_gasakit_variant(self):
        report = extract_symptoms_hybrid_report(
            "murag gasakit akong tiyan",
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=2,
            enable_semantic_fallback=False,
        )
        symptoms = report.get("final", {}).get("symptoms", [])
        self.assertIn("STOMACH_ACHE", symptoms)

    def test_context_clarify_returns_specific_display_symptom_for_stomach(self):
        response = self.client.post(
            "/consult/api/context-clarify",
            json={
                "original_symptoms": ["STOMACH_ACHE"],
                "clarify_type": "STOMACH_CONTEXT",
                "clarification": "STOMACH_ACIDIC",
                "age": 21,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data.get("symptoms"), ["STOMACH_ACHE"])
        self.assertEqual(data.get("symptoms_display"), ["STOMACH_ACHE_ACIDIC"])

    # ── Ten-slot diarrhea + Sipon OLDCARTS regression tests ────────────────

    def test_diarrhea_recommends_stocked_treatment_and_adjunct(self):
        """Non-infectious diarrhea uses only the two stocked diarrhea products."""
        rec = recommend_from_dataset(
            ["DIARRHEA"], self.rows,
            user_input="diarrhea no spoiled food no fever",
            context_override="DIARRHEA_NON_INFECTIOUS",
        )
        self.assertEqual(rec.get("action"), "recommend")
        brands = [r["brand"] for r in rec.get("recommendations", [])]
        self.assertEqual(brands, ["Loperamide", "Erceflora"])

    def test_diarrhea_food_poisoning_uses_adjunct_and_hydration_warning(self):
        """Food poisoning excludes loperamide and does not overstate probiotics."""
        rec = recommend_from_dataset(
            ["DIARRHEA"], self.rows,
            user_input="diarrhea food poisoning spoiled",
            context_override="DIARRHEA_FOOD_POISONING",
        )
        self.assertEqual(rec.get("action"), "recommend")
        brands = [r["brand"] for r in rec.get("recommendations", [])]
        self.assertEqual(brands, ["Erceflora"])
        warnings = " ".join(rec.get("safety_warnings", [])).lower()
        self.assertIn("only an adjunct", warnings)
        self.assertIn("oral rehydration", warnings)

    def test_sipon_alone_asks_context(self):
        """RUNNY_NOSE as sole symptom should trigger SIPON_CONTEXT clarification."""
        rec = recommend_from_dataset(
            ["RUNNY_NOSE"], self.rows,
            user_input="may sipon ako",
        )
        self.assertEqual(rec.get("action"), "ask_clarify")
        self.assertEqual(rec.get("clarify_type"), "SIPON_CONTEXT")
        options = [o["value"] for o in rec.get("options", [])]
        self.assertIn("SIPON_VIRAL_COLD", options)
        self.assertIn("SIPON_ALLERGY", options)
        self.assertIn("SIPON_COLD_WEATHER", options)

    def test_sipon_cold_weather_no_medicine(self):
        """Cold-weather sipon should return rest advice, no medicine."""
        rec = recommend_from_dataset(
            ["RUNNY_NOSE"], self.rows,
            user_input="sipon cold weather malamig",
            context_override="SIPON_COLD_WEATHER",
        )
        self.assertEqual(rec.get("action"), "recommend")
        self.assertEqual(rec.get("recommendations"), [])
        self.assertIn("malamig na panahon", rec.get("message", ""))

    def test_sipon_with_fever_skips_clarification(self):
        """RUNNY_NOSE + FEVER should go straight to recommendation, no clarification."""
        rec = recommend_from_dataset(
            ["RUNNY_NOSE", "FEVER"], self.rows,
            user_input="may sipon ako at lagnat",
        )
        self.assertNotEqual(rec.get("action"), "ask_clarify")
        self.assertEqual(rec.get("action"), "recommend")

    def test_cough_general_with_other_symptoms_still_asks_clarify(self):
        """COUGH_GENERAL should always request dry/wet clarification for consistency."""
        rec = recommend_from_dataset(
            ["COUGH_GENERAL", "RUNNY_NOSE"], self.rows,
            user_input="naa koy ubo ug sipon",
        )
        self.assertEqual(rec.get("action"), "ask_clarify")
        self.assertIn("dry", (rec.get("question") or "").lower())

    def test_extract_conditions_high_blood_and_pregnancy(self):
        self.assertIn("HYPERTENSION", extract_conditions("naa koy high blood"))
        self.assertIn("PREGNANCY", extract_conditions("buntis ko"))

    def test_mixed_input_keeps_symptom_and_condition(self):
        report = extract_symptoms_hybrid_report(
            "May sipon pero may high blood",
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=2,
            enable_semantic_fallback=True,
        )
        self.assertIn("RUNNY_NOSE", report.get("final", {}).get("symptoms", []))
        self.assertIn("HYPERTENSION", report.get("final", {}).get("conditions", []))

    def test_hypertension_contraindication_blocks_cold_combo(self):
        rec = recommend_from_dataset(
            ["RUNNY_NOSE"],
            self.rows,
            user_input="may sipon pero may high blood",
            detected_conditions=["HYPERTENSION"],
        )
        self.assertEqual(rec.get("action"), "recommend")
        recommended_brands = [r["brand"] for r in rec.get("recommendations", [])]
        blocked_brands = [r["brand"] for r in rec.get("blocked_recommendations", [])]
        self.assertNotIn("Neozep", recommended_brands)
        self.assertIn("Neozep", blocked_brands)


# ===================================================================
# DURATION SAFEGUARD MATRIX — REGRESSION TESTS
# ===================================================================

class DurationSafeguardTests(unittest.TestCase):
    """Tests for the OLDCARTS Duration Safeguard Matrix."""

    @classmethod
    def setUpClass(cls):
        cls.rows = load_mendo_dataset(DATASET_DEFAULT)
        cls.client = app.test_client()

    # -- parse_duration_days --

    def test_parse_duration_single(self):
        self.assertEqual(parse_duration_days("3"), 3)

    def test_parse_duration_range(self):
        self.assertEqual(parse_duration_days("1-3"), 2)

    def test_parse_duration_plus(self):
        self.assertEqual(parse_duration_days("4+"), 4)

    def test_parse_duration_plus_high(self):
        self.assertEqual(parse_duration_days("15+"), 15)

    # -- get_duration_question --

    def test_duration_question_exists_for_all_thresholds(self):
        for symptom in DURATION_THRESHOLDS:
            q = get_duration_question(symptom)
            self.assertIsNotNone(q, f"No question for {symptom}")
            self.assertEqual(q["action"], "ask_duration")
            self.assertEqual(q["symptom"], symptom)
            self.assertTrue(len(q["options"]) >= 2, f"<2 options for {symptom}")

    # -- check_duration_safety: SAFE cases --

    def test_fever_2_days_safe(self):
        result = check_duration_safety("FEVER", 2)
        self.assertTrue(result["safe"])

    def test_diarrhea_1_day_safe(self):
        result = check_duration_safety("DIARRHEA", 1)
        self.assertTrue(result["safe"])

    def test_cough_7_days_safe(self):
        result = check_duration_safety("COUGH_DRY", 7)
        self.assertTrue(result["safe"])

    def test_headache_3_days_safe(self):
        result = check_duration_safety("HEADACHE", 3)
        self.assertTrue(result["safe"])

    def test_runny_nose_5_days_safe(self):
        result = check_duration_safety("RUNNY_NOSE", 5)
        self.assertTrue(result["safe"])

    # -- check_duration_safety: BLOCKED (exceeds threshold) --

    def test_fever_4_days_blocked(self):
        result = check_duration_safety("FEVER", 4)
        self.assertFalse(result["safe"])
        self.assertIn("referral", result)
        self.assertEqual(result["referral"]["action"], "duration_referral")

    def test_diarrhea_3_days_blocked(self):
        result = check_duration_safety("DIARRHEA", 3)
        self.assertFalse(result["safe"])
        self.assertIn("referral", result)

    def test_sore_throat_6_days_blocked(self):
        result = check_duration_safety("SORE_THROAT", 6)
        self.assertFalse(result["safe"])
        self.assertEqual(result["referral"]["action"], "duration_referral")

    def test_stomach_8_days_blocked(self):
        result = check_duration_safety("STOMACH_ACHE", 8)
        self.assertFalse(result["safe"])
        self.assertEqual(result["referral"]["action"], "duration_referral")

    def test_headache_8_days_blocked(self):
        result = check_duration_safety("HEADACHE", 8)
        self.assertFalse(result["safe"])
        self.assertEqual(result["referral"]["action"], "duration_referral")

    def test_body_aches_8_days_blocked(self):
        result = check_duration_safety("BODY_ACHES", 8)
        self.assertFalse(result["safe"])

    def test_rashes_8_days_blocked(self):
        result = check_duration_safety("RASHES", 8)
        self.assertFalse(result["safe"])

    def test_nasal_congestion_11_days_blocked(self):
        result = check_duration_safety("NASAL_CONGESTION", 11)
        self.assertFalse(result["safe"])
        self.assertEqual(result["referral"]["action"], "duration_referral")

    def test_runny_nose_11_days_blocked(self):
        result = check_duration_safety("RUNNY_NOSE", 11)
        self.assertFalse(result["safe"])

    def test_cough_15_days_blocked(self):
        result = check_duration_safety("COUGH_GENERAL", 15)
        self.assertFalse(result["safe"])
        self.assertEqual(result["referral"]["action"], "duration_referral")

    def test_cough_dry_15_days_blocked(self):
        result = check_duration_safety("COUGH_DRY", 15)
        self.assertFalse(result["safe"])

    def test_cough_productive_15_days_blocked(self):
        result = check_duration_safety("COUGH_PRODUCTIVE", 15)
        self.assertFalse(result["safe"])

    # -- Edge cases: exactly at threshold (should be SAFE) --

    def test_fever_exactly_3_days_safe(self):
        result = check_duration_safety("FEVER", 3)
        self.assertTrue(result["safe"])

    def test_diarrhea_exactly_2_days_safe(self):
        result = check_duration_safety("DIARRHEA", 2)
        self.assertTrue(result["safe"])

    def test_cough_exactly_14_days_safe(self):
        result = check_duration_safety("COUGH_GENERAL", 14)
        self.assertTrue(result["safe"])

    def test_runny_nose_exactly_7_days_safe(self):
        result = check_duration_safety("RUNNY_NOSE", 7)
        self.assertTrue(result["safe"])

    def test_runny_nose_exactly_10_days_blocks(self):
        result = check_duration_safety("RUNNY_NOSE", 10)
        self.assertFalse(result["safe"])

    # -- API endpoint tests --

    def test_duration_check_api_safe(self):
        response = self.client.post(
            "/consult/api/duration-check",
            json={
                "symptom": "FEVER",
                "duration_value": "1-2",
                "original_symptoms": ["FEVER"],
                "original_conditions": [],
                "pending_durations": [],
                "age": 25,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["safe"])
        self.assertTrue(data["proceed"])
        self.assertIn("recommendation", data)

    def test_duration_check_api_blocked(self):
        response = self.client.post(
            "/consult/api/duration-check",
            json={
                "symptom": "FEVER",
                "duration_value": "4+",
                "original_symptoms": ["FEVER"],
                "original_conditions": [],
                "pending_durations": [],
                "age": 25,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertFalse(data["safe"])
        self.assertIn("referral", data)

    def test_duration_check_api_chains_to_next_symptom(self):
        response = self.client.post(
            "/consult/api/duration-check",
            json={
                "symptom": "FEVER",
                "duration_value": "1-2",
                "original_symptoms": ["FEVER", "HEADACHE"],
                "original_conditions": [],
                "pending_durations": ["HEADACHE"],
                "age": 25,
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["safe"])
        self.assertFalse(data["proceed"])
        self.assertIn("next_duration", data)
        self.assertEqual(data["next_duration"]["symptom"], "HEADACHE")

    def test_duration_check_api_missing_params(self):
        response = self.client.post(
            "/consult/api/duration-check",
            json={"symptom": "FEVER"},
        )
        self.assertEqual(response.status_code, 400)

    def test_duration_thresholds_count(self):
        """Verify all 9 symptom categories are covered (some with multiple labels)."""
        # At minimum: FEVER, DIARRHEA, SORE_THROAT, STOMACH_ACHE, HEADACHE,
        # BODY_ACHES, RASHES, ALLERGIC_RHINITIS, NASAL_CONGESTION,
        # RUNNY_NOSE, COUGH_GENERAL, COUGH_DRY, COUGH_PRODUCTIVE
        self.assertGreaterEqual(len(DURATION_THRESHOLDS), 13)


# ===================================================================
# SCOPED (ACCUMULATED) NEGATION — REGRESSION TESTS
# ===================================================================
# A negation word covers its whole clause: "wala koy gibati na sakit akong
# tiyan ug sakit sa ulo" negates both, while "pero gi ubo ko" is positive.

class ScopedNegationTests(unittest.TestCase):
    def _run(self, text):
        report = extract_symptoms_hybrid_report(
            text,
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=3,
            enable_semantic_fallback=True,
        )
        return sorted(report.get("final", {}).get("symptoms", []))

    def test_coordinate_list_fully_negated(self):
        cases = [
            ("wala akong ubo at sipon", []),
            ("wala koy ubo ug sipon", []),
            ("wala akong lagnat at ubo", []),
            ("no fever or cough", []),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(self._run(text), expected)

    def test_accumulated_negation_then_contrast_clause(self):
        cases = [
            (
                "wala koy gibati na sakit akong tiyan kay okay ra ug sakit sa ulo, pero gi ubo ko",
                ["COUGH_GENERAL"],
            ),
            ("wala koy sakit akong tiyan ug sakit sa ulo pero gi ubo ko", ["COUGH_GENERAL"]),
            ("wala akong lagnat at ubo pero masakit ulo ko", ["HEADACHE"]),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(self._run(text), expected)

    def test_negation_does_not_cross_contrast_or_assertion(self):
        cases = [
            ("hindi ako nilalagnat pero may ubo ako", ["COUGH_GENERAL"]),
            ("walang ubo pero may sipon", ["RUNNY_NOSE"]),
            ("wala koy ubo, naa koy sipon", ["RUNNY_NOSE"]),
            ("wala akong ubo may sipon ako", ["RUNNY_NOSE"]),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(self._run(text), expected)

    def test_consumed_negation_preserved(self):
        cases = [
            ("hindi pala ubo sipon", ["RUNNY_NOSE"]),
            ("wala koy ubo sipon", ["RUNNY_NOSE"]),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(self._run(text), expected)

    def test_trap_verbs_leave_symptom_positive(self):
        cases = [
            ("hindi na ako makagalaw dahil sa sakit ng katawan", ["BODY_ACHES"]),
            ("hindi ako makahinga dahil sa barado ilong", ["NASAL_CONGESTION"]),
            ("dili mawala akong ubo", ["COUGH_GENERAL"]),
            ("hindi na ako makatulog dahil sa sobrang ubo", ["COUGH_GENERAL"]),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(self._run(text), expected)


class FuzzyRescueTests(unittest.TestCase):
    """Generic typo rescue: any misspelled symptom word maps to its label."""

    def _run(self, text):
        report = extract_symptoms_hybrid_report(
            text,
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=3,
            enable_semantic_fallback=False,
        )
        return sorted(report.get("final", {}).get("symptoms", []))

    def test_misspelled_english_words_detected(self):
        cases = [
            ("hedache", ["HEADACHE"]),
            ("headeche", ["HEADACHE"]),
            ("headach", ["HEADACHE"]),
            ("grabeng hedache nako", ["HEADACHE"]),
            ("totache", ["TOOTHACHE"]),
            ("toothach", ["TOOTHACHE"]),
            ("stomachake", ["STOMACH_ACHE"]),
            ("stomak pain", ["STOMACH_ACHE"]),
            ("my tummi hurts", ["STOMACH_ACHE"]),
            ("couhg", ["COUGH_GENERAL"]),
            ("diahrea", ["DIARRHEA"]),
            ("noze barado", ["RUNNY_NOSE"]),
            ("itchy skin rsh", ["RASHES"]),
            ("trout hurts", ["SORE_THROAT"]),
            ("sore troat", ["SORE_THROAT"]),
            ("may sorethroat ako", ["SORE_THROAT"]),
            ("alerdyi sa pollen", ["ALLERGIC_RHINITIS"]),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(self._run(text), expected)

    def test_misspelled_words_respect_negation(self):
        cases = [
            ("wala koy hedache", []),
            ("wala akong trhot problem", []),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(self._run(text), expected)

    def test_accumulated_negation_then_contrast_still_works_with_typos(self):
        self.assertEqual(
            self._run("wala koy hedache ug totache pero gi ubo ko"),
            ["COUGH_GENERAL"],
        )

    def test_near_miss_words_do_not_fire(self):
        # 1-2 edit words that are NOT symptom typos must never fire.
        cases = [
            "worst headache ever",
            "i never get headaches",
            "boses ko",
            "isang ngipin ko",
            "masakit ang ulo ko simula kahapon",
            "tuloy tuloy ang sipon ko",
            "naa koy iring sa balay",
            "my nose keeps leaking even though i feel okay",
            "there is a pain that won't go away",
        ]
        for text in cases:
            with self.subTest(text=text):
                symptoms = self._run(text)
                self.assertTrue(set(symptoms) <= {"HEADACHE", "RUNNY_NOSE"})
                self.assertNotIn("FEVER", symptoms)
                self.assertNotIn("COUGH_GENERAL", symptoms)
                self.assertNotIn("SORE_THROAT", symptoms)
                self.assertNotIn("STOMACH_ACHE", symptoms)


if __name__ == "__main__":
    unittest.main()
