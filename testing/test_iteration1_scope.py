"""Pharmacist scope revision: clinical routing, dental exclusion, and pending SKU."""
import unittest
from unittest.mock import patch
from flask import Flask

from mendo_core.step1 import SYMPTOM_DICTIONARY, extract_symptoms
from mendo_core.step3_hybrid import extract_symptoms_hybrid_report
from mendo_core.step4_recommend import DATASET_DEFAULT, load_mendo_dataset, recommend_from_dataset


class IterationOneScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_mendo_dataset(DATASET_DEFAULT)

    def test_dental_inputs_cannot_trigger_semantic_drug_routing(self):
        self.assertNotIn('TOOTHACHE', SYMPTOM_DICTIONARY)
        self.assertEqual(len(SYMPTOM_DICTIONARY), 13)
        for text in ('toothache', 'tootache', 'totache', 'masakit ang ngipin ko',
                     'sakit akong ngipon', 'pain in one of my teeth',
                     'I woke up with a painful tooth this morning.',
                     'Masakit ang ngipin ko kapag umiinom ako ng malamig.',
                     'Grabe ang kasakit sa usa sa akong mga ngipon.'):
            with self.subTest(text=text), patch('mendo_core.step3_hybrid._get_semantic_extractor') as semantic:
                self.assertEqual(extract_symptoms(text), [])
                report = extract_symptoms_hybrid_report(
                    text, semantic_threshold=.65, semantic_top_margin=.08,
                    semantic_max_symptoms=2, enable_semantic_fallback=True)
                self.assertEqual(report['final']['symptoms'], [])
                semantic.assert_not_called()
                rec = recommend_from_dataset([], self.rows, user_input=text)
                self.assertEqual(rec['recommendations'], [])
                self.assertIn('dentist', rec['message'])

    def test_mixed_dental_complaints_keep_independent_supported_symptoms(self):
        self.assertEqual(extract_symptoms('toothache and fever'), ['FEVER'])
        self.assertEqual(extract_symptoms('sakit akong ngipon ug sipon'), ['RUNNY_NOSE'])
        self.assertNotIn('TOOTHACHE', extract_symptoms('masakit ngipin at ulo'))

    def test_stomach_character_selects_the_matching_drug_class(self):
        for context, expected in (('STOMACH_ACIDIC', ['Kremil-S']),
                                  ('STOMACH_CRAMPING', ['Buscopan'])):
            with self.subTest(context=context):
                rec = recommend_from_dataset(['STOMACH_ACHE'], self.rows,
                    user_input='stomach pain', context_override=context)
                self.assertEqual([r['brand'] for r in rec['recommendations']], expected)

    def test_antacid_never_replaces_an_analgesic_indication(self):
        for symptoms in (['FEVER'], ['HEADACHE'], ['BODY_ACHES']):
            rec = recommend_from_dataset(symptoms, self.rows, user_input='scope regression')
            self.assertNotIn('Kremil-S', [r['brand'] for r in rec['recommendations']])

    def test_sinecod_uses_the_tablet_age_and_opposing_mechanism_warning(self):
        sinecod = next(r for r in self.rows if r.brand == 'Sinecod')
        self.assertEqual(sinecod.min_age, '13')
        self.assertIn('butamirate', sinecod.generic_main_use.lower())
        rec = recommend_from_dataset(['COUGH_DRY', 'COUGH_PRODUCTIVE'], self.rows,
                                     user_input='dry cough and cough with phlegm')
        self.assertTrue(any('opposing mechanisms' in s for s in rec['safety_warnings']))

    def test_retired_dental_label_cannot_be_recommended_by_legacy_client(self):
        rec = recommend_from_dataset(['TOOTHACHE'], self.rows, user_input='toothache')
        self.assertEqual(rec['recommendations'], [])
        self.assertEqual(rec['action'], 'no_match')

    def test_consultation_api_enforces_sinecod_tablet_age(self):
        from pos.routes_consultation import consultation_bp
        app = Flask(__name__)
        app.secret_key = 'test-scope'
        app.register_blueprint(consultation_bp)
        with app.test_client() as client, \
             patch('pos.routes_consultation.log_interaction', return_value=None), \
             patch('pos.db.get_inventory_by_brand', return_value=None):
            for age in (12, 13):
                with self.subTest(age=age):
                    response = client.post('/consult/api/analyze', json={
                        'text': 'dry cough', 'age': age,
                    })
                    self.assertEqual(response.status_code, 200)
                    brands = [r['brand'] for r in response.get_json()['recommendation'].get('recommendations', [])]
                    self.assertEqual('Sinecod' in brands, age == 13)


if __name__ == '__main__':
    unittest.main()
