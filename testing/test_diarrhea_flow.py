"""Diarrhea context must survive duration screening without enabling unsafe meds."""
import unittest
from unittest.mock import patch

from flask import Flask
from pos.routes_consultation import consultation_bp


class DiarrheaFlowTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.secret_key = 'diarrhea-flow-test'
        app.register_blueprint(consultation_bp)
        self.client = app.test_client()
        with self.client.session_transaction() as state:
            state['consult_age'] = 25
        for target in ('pos.routes_consultation.log_interaction', 'pos.db.get_inventory_by_brand'):
            mock = patch(target, return_value=None)
            mock.start()
            self.addCleanup(mock.stop)

    def clarify(self, answer):
        response = self.client.post('/consult/api/context-clarify', json={
            'original_symptoms': ['DIARRHEA'], 'clarify_type': 'DIARRHEA_CONTEXT',
            'clarification': answer, 'age': 25,
        })
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def duration(self, answer, value='1'):
        response = self.client.post('/consult/api/duration-check', json={
            'symptom': 'DIARRHEA', 'duration_value': value,
            'original_symptoms': ['DIARRHEA'], 'pending_durations': [],
            'context_override': answer, 'clarification_data': {'clarification': answer},
            'age': 25, 'severity': 3, 'severity_map': {'DIARRHEA': 3},
        })
        self.assertEqual(response.status_code, 200)
        return response.get_json()

    def screen(self, overrides=None):
        answers = {'stool': 'watery', 'blood': 'no', 'fever': 'no', 'hydration': 'normal', 'pain': 'mild', 'antibiotics': 'no', 'risk': 'no', 'trigger': 'no', 'frequency': 'three_five', 'comfort': 'both'}
        answers.update(overrides or {})
        result = self.clarify('DIARRHEA_NON_INFECTIOUS')
        while result['recommendation']['action'] == 'ask_clarify' and result['recommendation']['clarify_type'] == 'DIARRHEA_SCREEN':
            key = result['recommendation']['question_key']
            response = self.client.post('/consult/api/context-clarify', json={
                'original_symptoms': ['DIARRHEA'], 'clarify_type': 'DIARRHEA_SCREEN',
                'clarification': f'DS_{key}_{answers[key]}', 'age': 25,
            })
            self.assertEqual(response.status_code, 200)
            result = response.get_json()
        return result

    def test_noninfectious_answer_proceeds_after_safe_duration(self):
        answer = 'DIARRHEA_NON_INFECTIOUS'
        self.assertEqual(self.screen()['recommendation']['action'], 'recommend')
        result = self.duration(answer)
        self.assertTrue(result['safe'])
        self.assertTrue(result['proceed'])
        self.assertEqual(result['symptoms_display'], ['DIARRHEA_NON_INFECTIOUS_CONTEXT'])
        self.assertEqual([r['brand'] for r in result['recommendation']['recommendations']], ['Loperamide'])

    def test_food_poisoning_keeps_advice_and_excludes_loperamide(self):
        for result in (self.screen({'trigger': 'yes'}),
                       self.duration('DIARRHEA_FOOD_POISONING')):
            recommendation = result['recommendation']
            self.assertEqual(recommendation['action'], 'no_match')
            self.assertEqual(recommendation['recommendations'], [])
            self.assertTrue(any('oral rehydration' in w for w in recommendation['safety_warnings']))

    def test_old_answer_cannot_bypass_full_screen(self):
        result = self.clarify('DIARRHEA_NON_INFECTIOUS')
        self.assertEqual(result['recommendation']['question_key'], 'stool')
        self.assertEqual(result['recommendation']['recommendations'] if 'recommendations' in result['recommendation'] else [], [])

    def test_danger_and_antibiotics_block_medicine(self):
        for facts, action in (({'blood': 'yes'}, 'triage'), ({'hydration': 'cannot'}, 'triage'), ({'pain': 'severe'}, 'triage'), ({'antibiotics': 'yes'}, 'no_match'), ({'fever': 'yes'}, 'no_match')):
            with self.subTest(facts=facts):
                with self.client.session_transaction() as state:
                    state['diarrhea_answers'] = {}
                result = self.screen(facts)['recommendation']
                self.assertEqual(result['action'], action)
                self.assertEqual(result['recommendations'], [])

    def test_out_of_order_answer_is_rejected(self):
        response = self.client.post('/consult/api/context-clarify', json={'original_symptoms':['DIARRHEA'], 'clarify_type':'DIARRHEA_SCREEN', 'clarification':'DS_blood_no', 'age':25})
        self.assertEqual(response.status_code, 400)

    def test_prolonged_diarrhea_still_refers(self):
        result = self.duration('DIARRHEA_NON_INFECTIOUS', '3+')
        self.assertFalse(result['safe'])
        self.assertFalse(result.get('proceed', False))
        self.assertIn('referral', result)


if __name__ == '__main__':
    unittest.main()
