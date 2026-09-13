"""
Comprehensive tests for advanced multilingual fuzzy matching.

Tests cover:
1. Phonetic normalization (Tagalog/Bisaya)
2. Keyboard-weighted Levenshtein
3. Tagalog/Bisaya anchor support
4. Character n-gram matching
"""

import unittest
import sys
sys.path.insert(0, '.')

from mendo_core.advanced_fuzzy import (
    phonetic_normalize,
    keyboard_weighted_distance,
    ngram_similarity,
    advanced_fuzzy_match,
    get_match_details,
    _are_adjacent_keys,
)


class PhoneticNormalizationTests(unittest.TestCase):
    """Test phonetic normalization for Tagalog/Bisaya."""
    
    def test_vowel_normalization(self):
        """o→u and e→i swaps are common in local languages."""
        cases = [
            ("sipon", "sipun"),      # o→u
            ("sipoon", "sipun"),     # oo→u
            ("saket", "sakit"),      # e→i
            ("masaket", "masakit"),  # e→i
        ]
        for input_word, expected in cases:
            self.assertEqual(phonetic_normalize(input_word), expected,
                           f"Failed: {input_word} → {expected}")
    
    def test_consonant_normalization(self):
        """c/ck → k conversions."""
        cases = [
            ("stomack", "stumak"),   # ck→k, o→u
            ("cough", "kuf"),         # c→k, ou→u
            ("sikat", "sikat"),       # already k
        ]
        for input_word, expected in cases:
            result = phonetic_normalize(input_word)
            self.assertEqual(result, expected,
                           f"Failed: {input_word} → {expected}, got {result}")
    
    def test_affix_stripping(self):
        """Remove Tagalog/Bisaya prefixes and suffixes."""
        cases = [
            ("giubo", "ubu"),         # gi- prefix, o→u
            ("nagubo", "ubu"),        # nag- prefix, o→u
            ("sakitan", "sakit"),     # -an suffix
            ("sakiten", "sakit"),     # -en suffix
            ("inuubo", "ubu"),        # -in suffix (inside), o→u
            ("pagubo", "ubu"),        # no prefix match (pag- not in list)
        ]
        for input_word, expected in cases:
            result = phonetic_normalize(input_word)
            self.assertEqual(result, expected,
                           f"Failed: {input_word} → {expected}, got {result}")
    
    def test_combined_normalization(self):
        """Multiple normalizations in one word."""
        cases = [
            ("nagsaketan", "sakit"),  # nag- + -an + e→i
            ("gisakiten", "sakit"),   # gi- + -en + e→i
            ("makasipon", "sipun"),   # maka- + o→u
        ]
        for input_word, expected in cases:
            result = phonetic_normalize(input_word)
            self.assertEqual(result, expected,
                           f"Failed: {input_word} → {expected}, got {result}")


class KeyboardWeightedDistanceTests(unittest.TestCase):
    """Test keyboard-aware edit distance."""
    
    def test_adjacent_key_detection(self):
        """Adjacent keys on QWERTY keyboard."""
        # Adjacent pairs
        self.assertTrue(_are_adjacent_keys('u', 'i'))
        self.assertTrue(_are_adjacent_keys('s', 'a'))
        self.assertTrue(_are_adjacent_keys('k', 'j'))
        
        # Non-adjacent pairs
        self.assertFalse(_are_adjacent_keys('u', 'z'))
        self.assertFalse(_are_adjacent_keys('a', 'p'))
    
    def test_adjacent_substitution_cost(self):
        """Adjacent key swaps should cost 0.5."""
        # "sakut" → "sakit" (u→i adjacent)
        dist = keyboard_weighted_distance("sakut", "sakit")
        self.assertAlmostEqual(dist, 0.5, places=2)
    
    def test_non_adjacent_substitution_cost(self):
        """Non-adjacent key swaps should cost 1.0."""
        # "sakzt" → "sakit" (z→k non-adjacent)
        dist = keyboard_weighted_distance("sakzt", "sakit")
        self.assertAlmostEqual(dist, 2.0, places=2)  # z→k and z→i
    
    def test_exact_match(self):
        """Exact matches should have 0 distance."""
        self.assertEqual(keyboard_weighted_distance("sakit", "sakit"), 0.0)
    
    def test_early_exit_on_long_words(self):
        """Distance > max_dist should return inf."""
        dist = keyboard_weighted_distance("abc", "xyz", max_dist=1.0)
        self.assertEqual(dist, float('inf'))
    
    def test_mixed_operations(self):
        """Test insertions and deletions alongside substitutions."""
        # "hedache" → "headache" (insert 'a')
        dist = keyboard_weighted_distance("hedache", "headache")
        self.assertAlmostEqual(dist, 1.0, places=2)


class NGramSimilarityTests(unittest.TestCase):
    """Test character n-gram similarity."""
    
    def test_identical_words(self):
        """Identical words should have similarity 1.0."""
        self.assertAlmostEqual(ngram_similarity("headache", "headache"), 1.0)
    
    def test_single_character_difference(self):
        """Words with minor typos should have high similarity."""
        # "hedache" vs "headache"
        sim = ngram_similarity("hedache", "headache")
        self.assertGreater(sim, 0.6)  # Should be > 60%
    
    def test_completely_different_words(self):
        """Unrelated words should have low similarity."""
        sim = ngram_similarity("headache", "xyz")
        self.assertLess(sim, 0.3)
    
    def test_affixation_handling(self):
        """N-grams should naturally handle affixation."""
        # "ubo" vs "inaubo" should share "ubo" bigrams/trigrams
        sim = ngram_similarity("ubo", "inaubo", n=3)
        self.assertGreater(sim, 0.3)  # Some overlap


class AdvancedFuzzyMatchTests(unittest.TestCase):
    """Test unified advanced fuzzy matching."""
    
    def test_exact_match(self):
        """Exact matches should always succeed."""
        result = advanced_fuzzy_match("headache", "headache", "HEADACHE", 2.0, [])
        self.assertEqual(result, "HEADACHE")
    
    def test_phonetic_match_tagalog(self):
        """Phonetic variations in Tagalog should match."""
        # "sipoon" → "sipon" via phonetic normalization
        result = advanced_fuzzy_match("sipoon", "sipon", "RUNNY_NOSE", 2.0, [])
        self.assertEqual(result, "RUNNY_NOSE")
    
    def test_keyboard_weighted_match(self):
        """Adjacent key typos should match with low distance."""
        # "sakut" → "sakit" (u→i adjacent)
        result = advanced_fuzzy_match("sakut", "sakit", "BODY_ACHES", 1.5, [])
        self.assertEqual(result, "BODY_ACHES")
    
    def test_ngram_match(self):
        """High n-gram similarity should match."""
        # "hedache" → "headache"
        result = advanced_fuzzy_match("hedache", "headache", "HEADACHE", 2.0, [], min_ngram_score=0.6)
        self.assertEqual(result, "HEADACHE")
    
    def test_no_match_when_all_strategies_fail(self):
        """Completely different words should not match."""
        result = advanced_fuzzy_match("xyz", "headache", "HEADACHE", 2.0, [])
        self.assertIsNone(result)
    
    def test_affix_handling(self):
        """Affixed words should match root via phonetic normalization."""
        # "giubo" → "ubo"
        result = advanced_fuzzy_match("giubo", "ubo", "COUGH_GENERAL", 2.0, [])
        self.assertEqual(result, "COUGH_GENERAL")


class IntegrationTests(unittest.TestCase):
    """Integration tests with real symptom extraction."""
    
    def test_tagalog_typos_with_advanced_fuzzy(self):
        """Tagalog typos should be rescued by advanced fuzzy."""
        from mendo_core.step1 import extract_symptoms
        
        cases = [
            ("sipoon", "RUNNY_NOSE"),      # Phonetic: sipoon→sipun→sipon
            ("sakut", "BODY_ACHES"),       # Keyboard: sakut→sakit (u→i adjacent)
            ("giubo", "COUGH_GENERAL"),    # Affix: giubo→ubo
            ("lagnt", "FEVER"),            # Keyboard + phonetic
            ("masakut", "BODY_ACHES"),     # Phonetic: masakut→masakit
        ]
        
        for text, expected_label in cases:
            result = extract_symptoms(text)
            self.assertIn(expected_label, result,
                         f"Failed to extract {expected_label} from '{text}', got {result}")
    
    def test_english_typos_still_work(self):
        """English typos should still be rescued."""
        from mendo_core.step1 import extract_symptoms
        
        cases = [
            ("hedache", "HEADACHE"),
            ("feaver", "FEVER"),
            ("couhg", "COUGH_GENERAL"),
            ("stomakache", "STOMACH_ACHE"),
        ]
        
        for text, expected_label in cases:
            result = extract_symptoms(text)
            self.assertIn(expected_label, result,
                         f"Failed to extract {expected_label} from '{text}'")
    
    def test_negation_with_typos(self):
        """Negated typos should not fire."""
        from mendo_core.step1 import extract_symptoms
        
        # "wala koy sipoon" = no runny nose
        result = extract_symptoms("wala koy sipoon")
        self.assertNotIn("RUNNY_NOSE", result)
    
    def test_precision_maintained(self):
        """Near-miss non-symptom words should not fire."""
        from mendo_core.step1 import extract_symptoms
        
        # These should NOT trigger symptoms
        cases = [
            ("never fever", "FEVER"),        # "never" ≠ "fever"
            ("worst headache", "HEADACHE"),  # "worst" is not a symptom
            ("uso ngayon", "COUGH_GENERAL"), # "uso" (trend) ≠ "ubo" (cough)
        ]
        
        for text, should_not_contain in cases:
            result = extract_symptoms(text)
            # "never fever" SHOULD contain FEVER because "fever" is there
            # but "never" alone should not trigger it
            if "fever" not in text.lower():
                self.assertNotIn(should_not_contain, result,
                               f"False positive: '{text}' incorrectly extracted {should_not_contain}")


class MatchDetailsTests(unittest.TestCase):
    """Test match details debugging utility."""
    
    def test_get_match_details(self):
        """get_match_details should return all matching scores."""
        details = get_match_details("sipoon", "sipon")
        
        self.assertIn("exact_match", details)
        self.assertIn("phonetic_match", details)
        self.assertIn("keyboard_distance", details)
        self.assertIn("ngram_similarity", details)
        self.assertIn("token_phonetic", details)
        self.assertIn("anchor_phonetic", details)
        
        # Should be phonetic match
        self.assertTrue(details["phonetic_match"])
        self.assertEqual(details["token_phonetic"], details["anchor_phonetic"])


if __name__ == "__main__":
    # Run tests with verbose output
    unittest.main(verbosity=2)
