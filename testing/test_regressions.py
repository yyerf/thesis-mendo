import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mendo_core.step3_hybrid import detect_red_flags, extract_symptoms_hybrid_report
from mendo_core.step4_recommend import DATASET_DEFAULT, load_mendo_dataset, recommend_from_dataset
from web.app import app


class RegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_mendo_dataset(DATASET_DEFAULT)
        cls.client = app.test_client()

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
        self.assertIn("Loperamide (Diatabs)", brands)

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
        self.assertNotIn("Loperamide (Diatabs)", brands)

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
            "fever ko is like 50 ang temp",
            "fever ko is like 50 degree ang temp",
            "fever ko is 45",
            "lagnat na 44 degrees",
        ]:
            with self.subTest(text=text):
                flags = detect_red_flags(text)
                self.assertTrue(any(flag["flag"] == "high_fever_prolonged" for flag in flags))

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

    def test_plain_headache_does_not_pull_cold_meds(self):
        rec = recommend_from_dataset(["HEADACHE"], self.rows, user_input="sakit akong ulo")
        self.assertEqual(rec.get("action"), "recommend")
        brands = [row["brand"] for row in rec.get("recommendations", [])]
        self.assertIn("Biogesic", brands)
        self.assertIn("Advil", brands)
        self.assertNotIn("Decolgen", brands)
        self.assertNotIn("Decolgen Forte", brands)

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
        """Logger output must include interaction_type, context_override, step numbers."""
        import json
        from mendo_core.interaction_logger import log_interaction

        iid = log_interaction(
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
        )
        # Read back last line
        with open("logs/interactions.jsonl") as f:
            last = json.loads(f.readlines()[-1])

        self.assertEqual(last["interaction_type"], "initial_analysis")
        self.assertIsNone(last["context_override"])
        self.assertEqual(last["session_id"], "unit_test")
        self.assertEqual(last["pipeline_stages"][0]["step"], 1)
        self.assertEqual(last["pipeline_stages"][1]["step"], 2)
        self.assertEqual(last["severity"], 5)

        # Cleanup: remove test entry
        with open("logs/interactions.jsonl") as f:
            lines = f.readlines()
        with open("logs/interactions.jsonl", "w") as f:
            f.writelines(lines[:-1])

    # ── ORS + Sipon OLDCARTS regression tests ──────────────────────────────

    def test_diarrhea_recommends_ors(self):
        """Non-infectious diarrhea should include ORS (Hydrite) in recommendations."""
        rec = recommend_from_dataset(
            ["DIARRHEA"], self.rows,
            user_input="diarrhea no spoiled food no fever",
            context_override="DIARRHEA_NON_INFECTIOUS",
        )
        self.assertEqual(rec.get("action"), "recommend")
        brands = [r["brand"] for r in rec.get("recommendations", [])]
        self.assertIn("Hydrite (ORS)", brands)
        self.assertIn("Loperamide (Diatabs)", brands)

    def test_diarrhea_food_poisoning_recommends_ors_first(self):
        """Food poisoning diarrhea: ORS should rank highest, loperamide excluded."""
        rec = recommend_from_dataset(
            ["DIARRHEA"], self.rows,
            user_input="diarrhea food poisoning spoiled",
            context_override="DIARRHEA_FOOD_POISONING",
        )
        self.assertEqual(rec.get("action"), "recommend")
        brands = [r["brand"] for r in rec.get("recommendations", [])]
        self.assertIn("Hydrite (ORS)", brands)
        self.assertIn("Erceflora", brands)
        self.assertNotIn("Loperamide (Diatabs)", brands)
        # ORS should be first (highest score)
        self.assertEqual(brands[0], "Hydrite (ORS)")

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


if __name__ == "__main__":
    unittest.main()
