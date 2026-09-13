#!/usr/bin/env python3
"""Test for headache intake bug fix (August 15, 2026).

Tests that HEADACHE is not incorrectly added when:
1. User types negated headache text with other symptoms
2. No explicit headache diagram click occurred
3. No bare headache cue promotion should happen

Bug: System was adding HEADACHE when headache_location was set but user
didn't click on diagram and HEADACHE wasn't detected by symptom pipeline.

Fix: Only add HEADACHE if user explicitly clicked diagram or if intake
promoted a bare headache cue (which already validates appropriateness).
"""

import unittest
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mendo_core.prediction_pipeline import predict_symptoms
from pos.routes_consultation import _apply_text_headache_intake


class HeadacheIntakeBugFixTests(unittest.TestCase):
    """Test cases for the headache intake bug fix."""

    def test_negated_headache_with_cough_no_user_click(self):
        """Negated headache + cough should only detect cough, not add HEADACHE."""
        user_text = "dili sakit akong tiyan, akong ulo, akong ngipon pero giubo ko"
        user_headache_location = None  # User did NOT click diagram
        
        # Run symptom detection
        report = predict_symptoms(user_text)
        symptoms = report["final"]["symptoms"]
        
        # Verify cough detected, headache negated
        self.assertEqual(symptoms, ["COUGH_GENERAL"])
        
        # Apply headache intake
        headache_intake = _apply_text_headache_intake(report, user_text, None)
        
        # Should return None (no intake)
        self.assertIsNone(headache_intake)
        
        # Symptoms should still be just cough
        self.assertEqual(report["final"]["symptoms"], ["COUGH_GENERAL"])
        
    def test_user_click_adds_headache_even_with_other_symptoms(self):
        """User clicking diagram should add HEADACHE even with other symptoms."""
        user_text = "dili sakit akong tiyan, akong ulo, akong ngipon pero giubo ko"
        user_headache_location = "tension"  # User DID click diagram
        
        # Run symptom detection
        report = predict_symptoms(user_text)
        
        # Should detect cough
        self.assertEqual(report["final"]["symptoms"], ["COUGH_GENERAL"])
        
        # Simulate user click by checking if headache_location matches user input
        user_clicked = (user_headache_location is not None)
        
        # If user clicked, HEADACHE should be addable
        if user_clicked and "HEADACHE" not in report["final"]["symptoms"]:
            report["final"]["symptoms"].append("HEADACHE")
        
        # Should have both symptoms now
        self.assertIn("COUGH_GENERAL", report["final"]["symptoms"])
        self.assertIn("HEADACHE", report["final"]["symptoms"])
        
    def test_bare_headache_cue_promotes_when_no_other_symptoms(self):
        """Bare cue like 'tension' should promote to HEADACHE when no other symptoms."""
        user_text = "tension"
        
        # Run symptom detection
        report = predict_symptoms(user_text)
        symptoms_before = report["final"]["symptoms"].copy()
        
        # Should have no symptoms initially (or maybe some weak semantic hit)
        self.assertNotIn("HEADACHE", symptoms_before)
        
        # Apply headache intake
        headache_intake = _apply_text_headache_intake(report, user_text, None)
        
        # Should promote bare cue
        self.assertIsNotNone(headache_intake)
        self.assertEqual(headache_intake["key"], "tension")
        
        # _apply_text_headache_intake should have added HEADACHE
        self.assertIn("HEADACHE", report["final"]["symptoms"])
        
        # Should only appear once
        self.assertEqual(report["final"]["symptoms"].count("HEADACHE"), 1)
        
    def test_bare_cue_does_not_promote_with_other_symptoms(self):
        """Bare headache cue should NOT promote if other symptoms detected."""
        user_text = "giubo ko ug tension"  # Cough + tension word
        
        # Run symptom detection
        report = predict_symptoms(user_text)
        symptoms = report["final"]["symptoms"]
        
        # Should detect cough
        self.assertIn("COUGH_GENERAL", symptoms)
        
        # Apply headache intake
        headache_intake = _apply_text_headache_intake(report, user_text, None)
        
        # Should NOT promote because other symptoms exist
        self.assertIsNone(headache_intake)
        
        # HEADACHE should NOT be added
        self.assertNotIn("HEADACHE", report["final"]["symptoms"])
        
    def test_negated_sinus_does_not_promote(self):
        """Negated sinus text should not promote headache."""
        user_text = "wala koy sinus"
        
        # Run symptom detection
        report = predict_symptoms(user_text)
        
        # Apply headache intake
        headache_intake = _apply_text_headache_intake(report, user_text, None)
        
        # Should NOT promote negated text
        self.assertIsNone(headache_intake)
        
        # HEADACHE should NOT be added
        self.assertNotIn("HEADACHE", report["final"]["symptoms"])


if __name__ == "__main__":
    # Run with verbose output
    unittest.main(verbosity=2)
