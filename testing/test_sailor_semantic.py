"""Tests for the Sailor2 (Ollama) semantic backend.

All HTTP traffic is mocked — these tests never touch the network, so they
run on any machine (no Ollama install required).

Coverage:
- closed-vocabulary constrained decode (request contract)
- fail-closed parsing (garbage → raise, not silent noise)
- honest binary emission scoring (1.0 emitted / 0.0 else)
- LRU cache behavior
- precision-first gating: LLM backend skipped when dictionary hits
- factory dispatch behind MENDO_SEMANTIC_BACKEND
"""

import json
import unittest
from unittest import mock

from mendo_core import step3_hybrid
from mendo_core.prediction_pipeline import predict_symptoms
from mendo_core.sailor_semantic import LLMSymptomExtractor, SYMPTOM_LABELS
from mendo_core.step2 import SemanticMatch
from mendo_core.step3_hybrid import extract_symptoms_hybrid_report, extract_symptoms_hybrid


class _FakeHTTPResponse:
    """Context-manager urllib response double with a status attribute."""
    def __init__(self, content: str):
        self.status = 200
        self._payload = json.dumps({"message": {"content": content}}).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, *args, **kwargs):
        return self._payload


class LLMExtractorUnitTests(unittest.TestCase):
    def _extractor(self):
        return LLMSymptomExtractor(base_url="http://127.0.0.1:11434", model="sailor2:1b")

    def test_emitted_labels_score_1_others_0(self):
        with mock.patch(
            "mendo_core.sailor_semantic.urllib.request.urlopen",
            return_value=_FakeHTTPResponse('["HEADACHE", "FEVER"]'),
        ) as uo:
            labels, diag = self._extractor().analyze("sakit ulo tapos nilagnat")
        self.assertEqual(labels, ["HEADACHE", "FEVER"])
        self.assertEqual(len(diag), len(SYMPTOM_LABELS))
        by_symptom = {m.symptom: m.score for m in diag}
        self.assertEqual(by_symptom["HEADACHE"], 1.0)
        self.assertEqual(by_symptom["FEVER"], 1.0)
        self.assertEqual(by_symptom["RUNNY_NOSE"], 0.0)
        uo.assert_called_once()

    def test_empty_detection_is_valid(self):
        with mock.patch(
            "mendo_core.sailor_semantic.urllib.request.urlopen",
            return_value=_FakeHTTPResponse("[]"),
        ):
            labels, diag = self._extractor().analyze("pahabol lang to")
        self.assertEqual(labels, [])
        self.assertTrue(all(m.score == 0.0 for m in diag))

    def test_request_contract_is_closed_vocabulary_and_deterministic(self):
        with mock.patch(
            "mendo_core.sailor_semantic.urllib.request.urlopen",
            return_value=_FakeHTTPResponse("[]"),
        ) as uo:
            self._extractor().analyze("gihilanat ko")

        req = uo.call_args.args[0]
        self.assertIn("/api/chat", req.full_url)
        body = json.loads(req.data.decode("utf-8"))
        # The format is a GBNF JSON-schema whose array items are restricted to
        # the 13-label enum — closed vocabulary is enforced by the grammar,
        # not by prompt trust.
        fmt = body["format"]
        self.assertIsInstance(fmt, dict)
        self.assertEqual(fmt["type"], "object")
        items = fmt["properties"]["symptoms"]["items"]
        self.assertEqual(set(items["enum"]), set(SYMPTOM_LABELS))
        self.assertIn("symptoms", fmt["required"])
        self.assertEqual(body["options"]["temperature"], 0)
        self.assertEqual(body["options"]["num_predict"], 120)
        self.assertEqual(body["model"], "sailor2:1b")
        self.assertEqual(body["messages"][-1]["content"], "gihilanat ko")
        # Closed vocabulary must appear verbatim in the system prompt.
        system = body["messages"][0]["content"]
        for label in SYMPTOM_LABELS:
            self.assertIn(label, system)

    def test_garbage_reply_raises_fail_closed(self):
        for garbage in ['{"not": "a list"}', '"hello"', "cough medicine is good", "```\n[{broken\n```"]:
            with self.subTest(reply=garbage), mock.patch(
                "mendo_core.sailor_semantic.urllib.request.urlopen",
                return_value=_FakeHTTPResponse(garbage),
            ):
                with self.assertRaises(ValueError):
                    self._extractor().analyze("masakit ulo")

    def test_unknown_labels_are_dropped_not_trusted(self):
        with mock.patch(
            "mendo_core.sailor_semantic.urllib.request.urlopen",
            return_value=_FakeHTTPResponse('["HEADACHE", "COVID-19", "wala"]'),
        ):
            labels, _diag = self._extractor().analyze("sakit ulo")
        self.assertEqual(labels, ["HEADACHE"])

    def test_dict_of_label_bools_is_accepted(self):
        """Real model output seen in production: {"HEADACHE": true, ...}."""
        with mock.patch(
            "mendo_core.sailor_semantic.urllib.request.urlopen",
            return_value=_FakeHTTPResponse('{"HEADACHE": true, "RUNNY_NOSE": false}'),
        ):
            labels, _ = self._extractor().analyze("masakit ulo ko")
        self.assertEqual(labels, ["HEADACHE"])

    def test_wrapped_object_and_markdown_fences_are_accepted(self):
        with mock.patch(
            "mendo_core.sailor_semantic.urllib.request.urlopen",
            return_value=_FakeHTTPResponse('{"symptoms": ["FEVER", "COUGH_GENERAL"]}'),
        ):
            labels, _ = self._extractor().analyze("lagnat tapos ubo")
        self.assertEqual(labels, ["FEVER", "COUGH_GENERAL"])

        with mock.patch(
            "mendo_core.sailor_semantic.urllib.request.urlopen",
            return_value=_FakeHTTPResponse("```json\n[\"DIARRHEA\"]\n```"),
        ):
            labels, _ = self._extractor().analyze("nagkalibang ko")
        self.assertEqual(labels, ["DIARRHEA"])

    def test_http_failure_raises(self):
        with mock.patch(
            "mendo_core.sailor_semantic.urllib.request.urlopen",
            side_effect=OSError("connection refused"),
        ):
            with self.assertRaises(RuntimeError):
                self._extractor().analyze("masakit ulo")

    def test_cache_avoids_repeated_generations(self):
        with mock.patch(
            "mendo_core.sailor_semantic.urllib.request.urlopen",
            return_value=_FakeHTTPResponse('["HEADACHE"]'),
        ) as uo:
            ex = self._extractor()
            ex.analyze("masakit ulo")
            ex.analyze("masakit ulo")
        uo.assert_called_once()

    def test_dedupe_preserves_order(self):
        with mock.patch(
            "mendo_core.sailor_semantic.urllib.request.urlopen",
            return_value=_FakeHTTPResponse('["FEVER", "FEVER", "HEADACHE"]'),
        ):
            labels, _ = self._extractor().analyze("nilagnat tapos masakit ulo")
        self.assertEqual(labels, ["FEVER", "HEADACHE"])


class PrecisionFirstGatingTests(unittest.TestCase):
    """The LLM backend must run ONLY when the dictionary finds nothing."""

    def setUp(self):
        step3_hybrid._SEMANTIC_EXTRACTOR = None
        self._llm = mock.Mock()
        self._llm.fallback_only = True
        # analyze() must return diag rows too — the report selects candidates
        # from the per-symptom diagnostics, not from the label list alone.
        self._llm.analyze.return_value = (
            ["FEVER"],
            [SemanticMatch(symptom="FEVER", score=1.0, best_anchor="llm_constrained_decode: [...]")],
        )

    def tearDown(self):
        step3_hybrid._SEMANTIC_EXTRACTOR = None

    def _report(self, text, **kw):
        return extract_symptoms_hybrid_report(
            text,
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=2,
            enable_semantic_fallback=True,
            **kw,
        )

    def test_dictionary_hit_skips_llm(self):
        with mock.patch("mendo_core.step3_hybrid._get_semantic_extractor", return_value=self._llm):
            report = self._report("masakit ulo ko")
        self.assertEqual(report["final"]["symptoms"], ["HEADACHE"])
        self.assertEqual(report["final"]["source"], "dictionary")
        semantic = [s for s in report["stages"] if s["stage"] == "semantic"]
        self.assertEqual(semantic[0]["used"], False)
        self.assertEqual(semantic[0]["skipped_reason"], "dictionary_hit_precision_first")
        self._llm.analyze.assert_not_called()

    def test_dictionary_miss_uses_llm(self):
        with mock.patch("mendo_core.step3_hybrid._get_semantic_extractor", return_value=self._llm):
            report = self._report("nasusunog ako sa init ng panahon")
        self.assertEqual(report["final"]["symptoms"], ["FEVER"])
        semantic = [s for s in report["stages"] if s["stage"] == "semantic"]
        self.assertEqual(semantic[0]["used"], True)
        self._llm.analyze.assert_called_once()

    def test_hybrid_entry_point_also_gates_on_llm(self):
        """extract_symptoms_hybrid is the original fallback-only path; the
        LLM backend must simply not add noise to dictionary hits there."""
        with mock.patch("mendo_core.step3_hybrid._get_semantic_extractor", return_value=self._llm):
            result = extract_symptoms_hybrid("sipon ako", semantic_threshold=0.65)
        self.assertEqual(result, ["RUNNY_NOSE"])
        self._llm.analyze.assert_not_called()

    def test_embedding_backend_is_precision_first(self):
        """MiniLM (deployed default) is fallback-only like every backend:
        it must never add noise to a dictionary hit."""
        emb = mock.Mock()
        emb.fallback_only = True
        emb.analyze.return_value = (
            ["FEVER"],
            [SemanticMatch(symptom="FEVER", score=0.81, best_anchor="nilalagnat ako")],
        )
        with mock.patch("mendo_core.step3_hybrid._get_semantic_extractor", return_value=emb):
            report = self._report("masakit ulo ko")
        self.assertEqual(report["final"]["symptoms"], ["HEADACHE"])
        semantic = [s for s in report["stages"] if s["stage"] == "semantic"]
        self.assertEqual(semantic[0]["used"], False)
        self.assertEqual(semantic[0]["skipped_reason"], "dictionary_hit_precision_first")
        emb.analyze.assert_not_called()

        with mock.patch("mendo_core.step3_hybrid._get_semantic_extractor", return_value=emb):
            report = self._report("nasusunog ako sa init ng panahon")
        self.assertEqual(report["final"]["symptoms"], ["FEVER"])
        semantic = [s for s in report["stages"] if s["stage"] == "semantic"]
        self.assertEqual(semantic[0]["used"], True)

    def test_unavailable_backend_fails_closed_to_dictionary(self):
        with mock.patch(
            "mendo_core.step3_hybrid._get_semantic_extractor",
            side_effect=RuntimeError("ollama not running"),
        ):
            report = self._report("masakit ulo ko")
        semantic = [s for s in report["stages"] if s["stage"] == "semantic"]
        self.assertEqual(semantic[0]["available"], False)
        self.assertEqual(report["final"]["symptoms"], ["HEADACHE"])


def _getenv_for_backend(backend_value):
    """os.getenv double that only overrides the backend selector."""
    def getenv(key, default=None):
        if key == "MENDO_SEMANTIC_BACKEND":
            return backend_value
        return default
    return getenv


class FactoryDispatchTests(unittest.TestCase):
    def setUp(self):
        step3_hybrid._SEMANTIC_EXTRACTOR = None

    def tearDown(self):
        step3_hybrid._SEMANTIC_EXTRACTOR = None

    def test_default_backend_is_minilm(self):
        # Deployed default is the MiniLM cosine-anchor extractor (no env var).
        def unset_env(key, default=None):
            return default
        with mock.patch("mendo_core.step2.EmbeddingSymptomExtractor") as emb_cls, mock.patch(
            "os.getenv", side_effect=unset_env
        ):
            step3_hybrid._get_semantic_extractor()
        emb_cls.assert_called_once()

    def test_sailor_backend_selector(self):
        with mock.patch("os.getenv", side_effect=_getenv_for_backend("sailor")):
            ext = step3_hybrid._get_semantic_extractor()
        self.assertIsInstance(ext, LLMSymptomExtractor)

    def test_minilm_backend_selector(self):
        # The factory imports EmbeddingSymptomExtractor from .step2 at call
        # time, so the patch must target mendo_core.step2, not step3_hybrid.
        with mock.patch("mendo_core.step2.EmbeddingSymptomExtractor") as emb_cls, mock.patch(
            "os.getenv", side_effect=_getenv_for_backend("minilm")
        ):
            step3_hybrid._get_semantic_extractor()
        emb_cls.assert_called_once()

    def test_unknown_backend_falls_back_to_sailor(self):
        with mock.patch("os.getenv", side_effect=_getenv_for_backend("gpt4-api")):
            ext = step3_hybrid._get_semantic_extractor()
        self.assertIsInstance(ext, LLMSymptomExtractor)


class TraceSummaryHonestyTests(unittest.TestCase):
    """The audit trace must honestly record whether the semantic stage ran."""

    def setUp(self):
        step3_hybrid._SEMANTIC_EXTRACTOR = None

    def tearDown(self):
        step3_hybrid._SEMANTIC_EXTRACTOR = None

    def _llm_stub(self, labels):
        ex = mock.Mock()
        ex.fallback_only = True
        ex.analyze.return_value = (
            labels,
            [SemanticMatch(symptom=l, score=1.0, best_anchor="llm_constrained_decode") for l in labels],
        )
        return ex

    def test_dict_hit_skipped_stage_records_not_used(self):
        with mock.patch("mendo_core.step3_hybrid._get_semantic_extractor", return_value=self._llm_stub(["FEVER"])):
            trace = predict_symptoms("masakit ulo ko")
        self.assertEqual(
            trace["semantic"],
            {"used": False, "reason": "dictionary_hit_precision_first"},
        )

    def test_llm_run_records_emission_score_type(self):
        with mock.patch(
            "os.getenv", side_effect=_getenv_for_backend("sailor")
        ), mock.patch(
            "mendo_core.step3_hybrid._get_semantic_extractor", return_value=self._llm_stub(["FEVER"])
        ):
            trace = predict_symptoms("nasusunog ako sa init ng panahon")
        sem = trace["semantic"]
        self.assertTrue(sem["used"])
        self.assertEqual(sem["score_type"], "constrained_decode_emission")
        self.assertIn("FEVER", [s["symptom"] for s in sem["selected"]])

    def test_minilm_run_records_cosine_score_type(self):
        emb = mock.Mock()
        emb.fallback_only = True
        emb.analyze.return_value = (
            ["FEVER"],
            [SemanticMatch(symptom="FEVER", score=0.81, best_anchor="nilalagnat ako")],
        )
        with mock.patch("os.getenv", side_effect=_getenv_for_backend("minilm")), mock.patch(
            "mendo_core.step3_hybrid._get_semantic_extractor", return_value=emb
        ):
            trace = predict_symptoms("nasusunog ako sa init ng panahon")
        sem = trace["semantic"]
        self.assertTrue(sem["used"])
        self.assertEqual(sem["score_type"], "cosine_similarity")

    def test_unavailable_backend_records_reason(self):
        with mock.patch(
            "mendo_core.step3_hybrid._get_semantic_extractor",
            side_effect=RuntimeError("ollama down"),
        ):
            trace = predict_symptoms("nasusunog ako sa init ng panahon")
        self.assertEqual(trace["semantic"], {"used": False, "reason": "backend_unavailable"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
