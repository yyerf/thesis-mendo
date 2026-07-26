"""Regression tests for consent, annotation, exports, and evaluation metrics."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

from mendo_core import interaction_logger
from mendo_core.evaluation import (
    aggregate_metrics,
    case_metrics,
    clinical_appropriateness_rate,
    cohen_kappa,
    multilabel_reviewer_kappa,
)
from mendo_core.prediction_pipeline import predict_symptoms
from pos import db as pos_db
from pos.routes_admin import admin_bp
from pos.routes_consultation import consultation_bp


def _trace(symptoms: list[str] | None = None) -> dict:
    symptoms = symptoms or ["HEADACHE"]
    return {
        "trace_version": 2,
        "engine": {
            "engine_id": "mendo-expert-minilm-v3.1",
            "semantic_model_id": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
        },
        "stages": [
            {
                "stage": "dictionary",
                "detected": symptoms,
                "details": [
                    {
                        "symptom": symptoms[0],
                        "matched_phrases": ["headache"],
                        "decision": "selected",
                    }
                ],
            },
            {
                "stage": "semantic",
                "available": True,
                "threshold": 0.65,
                "scores": [
                    {
                        "symptom": symptoms[0],
                        "score": 0.81,
                        "best_anchor": "my head hurts",
                    }
                ],
            },
        ],
        "red_flags": [],
        "final": {
            "symptoms": symptoms,
            "conditions": [],
            "source": "hybrid_merged",
        },
    }


class MetricTests(unittest.TestCase):
    def test_case_and_aggregate_multilabel_metrics(self):
        row = case_metrics(["A", "B"], ["B", "C"])
        self.assertEqual(row["true_positive"], 1)
        self.assertAlmostEqual(row["precision"], 0.5)
        self.assertAlmostEqual(row["recall"], 0.5)
        self.assertAlmostEqual(row["f1"], 0.5)
        self.assertFalse(row["exact_match"])

        aggregate = aggregate_metrics(
            [
                {"predicted": ["A"], "expected": ["A"]},
                {"predicted": ["A"], "expected": ["B"]},
            ]
        )
        self.assertEqual(aggregate["case_count"], 2)
        self.assertAlmostEqual(aggregate["micro_precision"], 0.5)
        self.assertAlmostEqual(aggregate["micro_recall"], 0.5)
        self.assertAlmostEqual(aggregate["micro_f1"], 0.5)
        self.assertAlmostEqual(aggregate["exact_match_rate"], 0.5)
        self.assertAlmostEqual(aggregate["macro_f1"], 1 / 3)

    def test_clinical_appropriateness_and_kappa(self):
        result = clinical_appropriateness_rate(
            ["appropriate", "inappropriate", "not_applicable"]
        )
        self.assertEqual(result["judged_case_count"], 2)
        self.assertAlmostEqual(result["rate"], 0.5)
        self.assertEqual(cohen_kappa(["yes", "no"], ["yes", "no"]), 1.0)

        insufficient = multilabel_reviewer_kappa(
            [
                {
                    "reviewer_id": 1,
                    "interaction_id": "one",
                    "expected_symptoms": ["A"],
                }
            ]
        )
        self.assertEqual(insufficient["status"], "insufficient_reviewers")

        perfect = multilabel_reviewer_kappa(
            [
                {
                    "reviewer_id": reviewer,
                    "interaction_id": case,
                    "expected_symptoms": labels,
                }
                for reviewer in (1, 2)
                for case, labels in (("one", ["A"]), ("two", []))
            ]
        )
        self.assertEqual(perfect["status"], "available")
        self.assertAlmostEqual(perfect["kappa"], 1.0)


class PredictionTraceTests(unittest.TestCase):
    def test_known_false_positives_and_nasal_separation(self):
        expected = {
            "hindi masakit ang katawan ko": [],
            "ang ubod ng init ngayon": [],
            "walang sore throat": [],
            "barado ang ilong ko": ["NASAL_CONGESTION"],
            "sipon ako": ["RUNNY_NOSE"],
        }
        for text, labels in expected.items():
            with self.subTest(text=text):
                report = predict_symptoms(text)
                self.assertEqual(report["final"]["symptoms"], labels)

    def test_trace_identifies_model_scores_and_decisions(self):
        report = predict_symptoms("masakit ang ulo ko")
        self.assertEqual(report["trace_version"], 2)
        self.assertEqual(
            report["engine"]["semantic_score_type"], "cosine_similarity"
        )
        dictionary = next(
            stage for stage in report["stages"] if stage["stage"] == "dictionary"
        )
        self.assertTrue(dictionary["details"])
        self.assertIn("decision", dictionary["details"][0])
        semantic = next(
            stage for stage in report["stages"] if stage["stage"] == "semantic"
        )
        if semantic.get("available"):
            self.assertTrue(semantic["scores"])
            self.assertEqual(
                semantic["scores"][0]["score_type"], "cosine_similarity"
            )


class AuditStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "audit.sqlite")
        self.original_path = interaction_logger._DB_PATH
        interaction_logger._DB_PATH = self.db_path

    def tearDown(self):
        interaction_logger._DB_PATH = self.original_path
        self.tmp.cleanup()

    def _log(self, *, consent: bool, text: str = "Masakit ulo ko 09171234567") -> str:
        return interaction_logger.log_interaction(
            user_input=text,
            extracted_symptoms=["HEADACHE"],
            extraction_source="hybrid_merged",
            pipeline_stages=_trace()["stages"],
            recommendation={"action": "no_match", "recommendations": []},
            session_id="session-a",
            research_consent=consent,
            language="tl",
            input_mode="text",
            trace=_trace(),
        )

    def test_declined_consent_never_persists_raw_text(self):
        self.assertEqual(self._log(consent=False), "not_persisted")
        self.assertEqual(interaction_logger.count_interaction_logs(), 0)
        summary = interaction_logger.get_operational_summary()
        self.assertEqual(summary["anonymous_nonpersistent_events"], 1)

    def test_deidentification_removes_identifiers_but_keeps_symptoms(self):
        text = interaction_logger.deidentify_text(
            "My name is Juan Dela Cruz, I am coughing. "
            "Email juan@example.com phone 09171234567."
        )
        self.assertNotIn("Juan Dela Cruz", text)
        self.assertNotIn("juan@example.com", text)
        self.assertNotIn("09171234567", text)
        self.assertIn("I am coughing", text)

    def test_legacy_exclusion_review_and_adjudicated_export(self):
        consented_id = self._log(consent=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO interaction_logs
                    (interaction_id,timestamp,session_id,interaction_type,user_input,research_consent)
                VALUES ('legacy','2026-01-01','old','analysis','legacy raw text',0)
                """
            )
            conn.commit()

        with self.assertRaisesRegex(ValueError, "not review-eligible"):
            interaction_logger.submit_review(
                "legacy",
                8,
                {
                    "expected_action": "no_match",
                    "recommendation_appropriateness": "not_applicable",
                    "reviewer_confidence": 3,
                },
            )

        review = interaction_logger.submit_review(
            consented_id,
            8,
            {
                "correct_symptoms": ["HEADACHE"],
                "missed_symptoms": [],
                "expected_red_flags": [],
                "expected_action": "no_match",
                "recommendation_appropriateness": "not_applicable",
                "expected_medicines": [],
                "reviewer_confidence": 4,
                "notes": "Appropriate extraction.",
            },
        )
        self.assertEqual(review["reviewer_id"], 8)
        self.assertEqual(review["correct_symptoms"], ["HEADACHE"])
        self.assertEqual(review["expected_symptoms"], ["HEADACHE"])
        interaction_logger.submit_review(
            consented_id,
            9,
            {
                "expected_symptoms": ["HEADACHE"],
                "missed_symptoms": [],
                "expected_red_flags": [],
                "expected_action": "no_match",
                "recommendation_appropriateness": "not_applicable",
                "expected_medicines": [],
                "reviewer_confidence": 5,
                "notes": "Independent agreement.",
            },
        )
        self.assertEqual(interaction_logger.export_research_jsonl(), "")

        interaction_logger.adjudicate(
            consented_id,
            1,
            {
                "final_symptoms": ["HEADACHE"],
                "final_red_flags": [],
                "final_action": "no_match",
                "recommendation_appropriateness": "not_applicable",
                "expected_medicines": [],
                "notes": "Gold.",
            },
        )
        exported = interaction_logger.export_research_jsonl()
        self.assertNotIn("09171234567", exported)
        self.assertIn("[PHONE]", exported)
        self.assertNotIn("legacy raw text", exported)
        manifest = interaction_logger.research_manifest()
        self.assertEqual(manifest["record_count"], 1)
        metrics = interaction_logger.get_aggregate_metrics()
        self.assertEqual(metrics["aggregate"]["case_count"], 1)
        self.assertEqual(metrics["aggregate"]["micro_f1"], 1.0)
        self.assertEqual(
            metrics["inter_reviewer_agreement"]["status"], "available"
        )


class ConsultationConsentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "web.sqlite")
        self.old_logger_path = interaction_logger._DB_PATH
        self.old_pos_path = pos_db.DB_PATH
        interaction_logger._DB_PATH = self.db_path
        pos_db.DB_PATH = self.db_path

        self.app = Flask(__name__, template_folder="../web/templates")
        self.app.secret_key = "testing"
        self.app.config.update(TESTING=True)
        self.app.teardown_appcontext(pos_db.close_db)
        with self.app.app_context():
            pos_db.init_db()
        self.app.register_blueprint(consultation_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        interaction_logger._DB_PATH = self.old_logger_path
        pos_db.DB_PATH = self.old_pos_path
        self.tmp.cleanup()

    @patch("pos.routes_consultation._get_med_rows", return_value=[])
    @patch("pos.routes_consultation.predict_symptoms", side_effect=lambda _text: _trace())
    def test_decline_then_grant_consent_and_validate_headache(
        self, _predict, _meds
    ):
        declined = self.client.post(
            "/consult/api/research-consent", json={"consent": False}
        )
        self.assertEqual(declined.status_code, 200)
        analysis = self.client.post(
            "/consult/api/analyze",
            json={
                "text": "Masakit ulo ko",
                "age": 22,
                "language": "tl",
                "input_mode": "text",
            },
        )
        self.assertEqual(analysis.status_code, 200)
        self.assertEqual(analysis.get_json()["interaction_id"], "not_persisted")
        self.assertEqual(interaction_logger.count_interaction_logs(), 0)

        self.client.post("/consult/api/research-consent", json={"consent": True})
        invalid = self.client.post(
            "/consult/api/analyze",
            json={"text": "Masakit ulo ko", "age": 22, "headache_location": "fake"},
        )
        self.assertEqual(invalid.status_code, 400)

        consented = self.client.post(
            "/consult/api/analyze",
            json={
                "text": "Masakit ulo ko",
                "age": 22,
                "headache_location": "sinus",
                "headache_danger": "red_flag",
                "language": "tl",
                "input_mode": "voice",
            },
        )
        body = consented.get_json()
        self.assertEqual(consented.status_code, 200)
        self.assertNotEqual(body["interaction_id"], "not_persisted")
        self.assertIn("NASAL_CONGESTION", body["symptoms"])
        self.assertEqual(
            body["headache_location"]["source"], "user_selected_illustration"
        )
        self.assertNotEqual(body["headache_location"]["danger"], "red_flag")
        self.assertEqual(body["engine"]["engine_id"], "mendo-expert-minilm-v3.1")
        self.assertEqual(interaction_logger.count_interaction_logs(), 1)


class ReviewerAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp.name) / "roles.sqlite")
        self.old_logger_path = interaction_logger._DB_PATH
        self.old_pos_path = pos_db.DB_PATH
        interaction_logger._DB_PATH = self.db_path
        pos_db.DB_PATH = self.db_path

        project_root = Path(__file__).resolve().parents[1]
        self.app = Flask(
            __name__,
            template_folder=str(project_root / "web" / "templates"),
            static_folder=str(project_root / "web" / "static"),
        )
        self.app.secret_key = "testing"
        self.app.config.update(TESTING=True)
        self.app.teardown_appcontext(pos_db.close_db)
        with self.app.app_context():
            pos_db.init_db()
            pos_db.create_user(
                "reviewer-one", "review-pass", "Domain Expert One", "reviewer"
            )
        self.app.register_blueprint(admin_bp)
        self.app.register_blueprint(consultation_bp)
        self.client = self.app.test_client()

    def tearDown(self):
        interaction_logger._DB_PATH = self.old_logger_path
        pos_db.DB_PATH = self.old_pos_path
        self.tmp.cleanup()

    def test_reviewer_is_restricted_and_adjudication_is_admin_only(self):
        login = self.client.post(
            "/admin/login",
            data={"username": "reviewer-one", "password": "review-pass"},
        )
        self.assertEqual(login.status_code, 302)
        self.assertTrue(login.headers["Location"].endswith("/admin/logs"))

        logs = self.client.get("/admin/logs")
        self.assertEqual(logs.status_code, 200)
        self.assertIn(b"Consultation Audit", logs.data)

        inventory = self.client.get("/admin/inventory")
        self.assertEqual(inventory.status_code, 302)
        self.assertTrue(inventory.headers["Location"].endswith("/admin/logs"))

        adjudication = self.client.post(
            "/admin/api/audit/interactions/not-found/adjudication",
            json={
                "final_action": "no_match",
                "recommendation_appropriateness": "not_applicable",
            },
        )
        self.assertEqual(adjudication.status_code, 302)


if __name__ == "__main__":
    unittest.main()
