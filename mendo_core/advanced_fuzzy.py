"""
Advanced multilingual fuzzy matching for Tagalog/Bisaya/English symptom detection.

This module implements four key improvements over standard Levenshtein:
1. Phonetic normalization for Tagalog/Bisaya vowel/consonant swaps
2. Keyboard-weighted edit distance (QWERTY-aware)
3. Expanded anchor set with Tagalog/Bisaya terms
4. Character n-gram similarity (FastText-style)
"""

import re
from typing import List, Tuple, Set, Optional


# ---------------------------------------------------------------------------
# 1. PHONETIC NORMALIZATION (Tagalog/Bisaya)
# ---------------------------------------------------------------------------

def phonetic_normalize(word: str) -> str:
    """
    Normalize common phonetic variations in Tagalog/Bisaya.
    
    Rules:
    - Vowel swaps: o↔u, e↔i (common in local languages)
    - Consonant normalization: c/ck→k
    - Affix stripping: remove nag-, gi-, -an, -en, -in, -hin (but NOT -on for words like sipon)
    
    Examples:
        "sipoon" → "sipuun"
        "saket" → "sakit"
        "giubo" → "ubu"
        "sakitan" → "sakit"
    """
    normalized = word.lower().strip()
    
    # Strip common Tagalog/Bisaya affixes (prefix first, then suffix)
    # Prefixes: nag-, naka-, mag-, maka-, gi-, gika-
    prefixes = [r'^nag', r'^naka', r'^mag', r'^maka', r'^gi', r'^gika']
    for prefix in prefixes:
        normalized = re.sub(prefix, '', normalized)
    
    # Suffixes: -an, -en, -in, -hin  (NOT -on because of sipon/lagnat/etc.)
    suffixes = [r'an$', r'en$', r'in$', r'hin$']
    for suffix in suffixes:
        normalized = re.sub(suffix, '', normalized)
    
    # Consonant normalization: c/ck → k
    normalized = re.sub(r'ck\b', 'k', normalized)
    normalized = re.sub(r'\bc(?=[aouei])', 'k', normalized)
    
    # Vowel normalization (create a phonetic "fingerprint")
    # o↔u and e↔i are often confused
    # Use str.maketrans for single-pass translation
    vowel_map = str.maketrans({'o': 'u', 'e': 'i', 'O': 'U', 'E': 'I'})
    normalized = normalized.translate(vowel_map)
    
    return normalized


# ---------------------------------------------------------------------------
# 2. KEYBOARD-WEIGHTED LEVENSHTEIN
# ---------------------------------------------------------------------------

# QWERTY keyboard layout: adjacent keys have lower edit cost
_QWERTY_ADJACENCY = {
    'q': set('wa'),
    'w': set('qeas'),
    'e': set('wrds'),
    'r': set('etdf'),
    't': set('ryfg'),
    'y': set('tugh'),
    'u': set('yihj'),
    'i': set('uojk'),
    'o': set('ipkl'),
    'p': set('ol'),
    'a': set('qwsz'),
    's': set('awedxz'),
    'd': set('serfcx'),
    'f': set('drtgvc'),
    'g': set('ftyhbv'),
    'h': set('gyujnb'),
    'j': set('huikmn'),
    'k': set('jiolm'),
    'l': set('kop'),
    'z': set('asx'),
    'x': set('zsdc'),
    'c': set('xdfv'),
    'v': set('cfgb'),
    'b': set('vghn'),
    'n': set('bhjm'),
    'm': set('njk'),
}


def _are_adjacent_keys(char1: str, char2: str) -> bool:
    """Check if two characters are adjacent on QWERTY keyboard."""
    if not char1.isalpha() or not char2.isalpha():
        return False
    c1, c2 = char1.lower(), char2.lower()
    return c2 in _QWERTY_ADJACENCY.get(c1, set())


def keyboard_weighted_distance(a: str, b: str, max_dist: float = 2.0) -> float:
    """
    Compute edit distance with keyboard-aware weighting.
    
    Adjacent key substitutions cost 0.5 instead of 1.0.
    - "sakut" → "sakit" (u→i adjacent): distance = 0.5
    - "sakzt" → "sakit" (z→k non-adjacent): distance = 1.0
    
    Returns:
        Float distance, or float('inf') if exceeds max_dist
    """
    if a == b:
        return 0.0
    
    la, lb = len(a), len(b)
    if abs(la - lb) > max_dist:
        return float('inf')
    
    # Ensure b is longer
    if la > lb:
        a, b = b, a
        la, lb = lb, la
    
    prev = [float(i) for i in range(lb + 1)]
    
    for i, ca in enumerate(a, start=1):
        cur = [float(i)] + [0.0] * lb
        row_min = cur[0]
        
        for j, cb in enumerate(b, start=1):
            if ca == cb:
                cost = 0.0
            elif _are_adjacent_keys(ca, cb):
                cost = 0.5  # Adjacent keys on keyboard
            else:
                cost = 1.0  # Non-adjacent keys
            
            cur[j] = min(
                prev[j] + 1.0,           # deletion
                cur[j - 1] + 1.0,        # insertion
                prev[j - 1] + cost       # substitution
            )
            
            if cur[j] < row_min:
                row_min = cur[j]
        
        # Early exit if entire row exceeds threshold
        if row_min > max_dist:
            return float('inf')
        
        prev = cur
    
    return prev[lb]


# ---------------------------------------------------------------------------
# 3. EXPANDED ANCHOR SET (English + Tagalog + Bisaya)
# ---------------------------------------------------------------------------

# Format: (canonical_form, symptom_label, max_keyboard_distance, phonetic_variants)
_ADVANCED_ANCHORS: List[Tuple[str, str, float, List[str]]] = [
    # English anchors (original)
    ("headache", "HEADACHE", 2.0, ["hedache", "headake", "hedake"]),
    ("toothache", "TOOTHACHE", 2.0, ["totache", "tothache"]),
    ("stomach", "STOMACH_ACHE", 2.0, ["stomak", "stomack", "stomake"]),
    ("stomachache", "STOMACH_ACHE", 2.5, ["stomakache", "stomackache"]),
    ("fever", "FEVER", 1.5, ["feaver", "faver"]),
    ("cough", "COUGH_GENERAL", 2.0, ["couhg", "coff", "koff", "kof"]),
    ("diarrhea", "DIARRHEA", 2.0, ["diarrea", "diarhea", "diarrhoea"]),
    ("runny", "RUNNY_NOSE", 1.5, ["runy"]),
    ("sore", "SORE_THROAT", 1.5, ["soar"]),
    ("dizzy", "DIZZINESS", 1.5, ["dizy", "disy"]),
    
    # Tagalog/Bisaya anchors (NEW!)
    ("sipon", "RUNNY_NOSE", 2.0, ["sipoon", "sipun", "csipon"]),
    ("ubo", "COUGH_GENERAL", 1.5, ["obo"]),  # Removed "ubu" to avoid matching "ulo" (head)
    ("lagnat", "FEVER", 1.5, ["lgnat", "lagnt"]),
    # REMOVED: ("sakit", "BODY_ACHES") - "sakit" is generic pain, needs body context
    ("masakit", "BODY_ACHES", 2.0, ["masakut", "masaket"]),
    ("labad", "BODY_ACHES", 2.0, ["labd", "labud", "labod"]),
    ("hilantan", "FEVER", 2.0, ["hilatan", "hilantn"]),
    ("pag_ubo", "COUGH_GENERAL", 1.5, ["pagubo", "pag-ubo"]),
]


# ---------------------------------------------------------------------------
# 4. CHARACTER N-GRAM SIMILARITY (FastText-style)
# ---------------------------------------------------------------------------

def _char_ngrams(word: str, n: int = 3) -> Set[str]:
    """
    Extract character n-grams from a word.
    
    Example:
        _char_ngrams("headache", 3) → {"hea", "ead", "ada", "dac", "ach", "che"}
    
    For short words, use bigrams and the word itself.
    """
    if len(word) < n:
        # Use bigrams for short words
        if len(word) >= 2:
            return {word[i:i+2] for i in range(len(word) - 1)} | {word}
        return {word}
    return {word[i:i+n] for i in range(len(word) - n + 1)}


def ngram_similarity(a: str, b: str, n: int = 3) -> float:
    """
    Compute Jaccard similarity between character n-grams.
    
    Returns:
        Float in [0.0, 1.0] where 1.0 = identical, 0.0 = no overlap
    
    Example:
        ngram_similarity("hedache", "headache", 3) → 0.71
    """
    ngrams_a = _char_ngrams(a.lower(), n)
    ngrams_b = _char_ngrams(b.lower(), n)
    
    if not ngrams_a or not ngrams_b:
        return 0.0
    
    intersection = len(ngrams_a & ngrams_b)
    union = len(ngrams_a | ngrams_b)
    
    return intersection / union if union > 0 else 0.0


# ---------------------------------------------------------------------------
# 5. UNIFIED MATCHING FUNCTION
# ---------------------------------------------------------------------------

def advanced_fuzzy_match(
    token: str,
    anchor: str,
    label: str,
    max_keyboard_dist: float,
    phonetic_variants: List[str],
    min_ngram_score: float = 0.55
) -> Optional[str]:
    """
    Multi-strategy fuzzy matching combining all 4 techniques.
    
    Matching strategies (tried in order):
    1. Exact match → immediate return
    2. Phonetic normalization + exact match
    3. Keyboard-weighted Levenshtein ≤ max_dist
    4. Character n-gram similarity ≥ min_ngram_score
    
    Args:
        token: User input word
        anchor: Canonical symptom word
        label: Symptom label to return
        max_keyboard_dist: Maximum keyboard-weighted edit distance
        phonetic_variants: Known phonetic variants (for logging)
        min_ngram_score: Minimum n-gram similarity threshold
    
    Returns:
        Symptom label if match found, None otherwise
    """
    token_lower = token.lower()
    anchor_lower = anchor.lower()
    
    # Strategy 1: Exact match
    if token_lower == anchor_lower:
        return label
    
    # Strategy 2: Phonetic normalization
    token_phonetic = phonetic_normalize(token_lower)
    anchor_phonetic = phonetic_normalize(anchor_lower)
    
    if token_phonetic == anchor_phonetic:
        return label
    
    # Strategy 3: Keyboard-weighted distance
    kbd_dist = keyboard_weighted_distance(token_lower, anchor_lower, max_keyboard_dist)
    if kbd_dist <= max_keyboard_dist:
        return label
    
    # Also try phonetic-normalized versions with keyboard distance
    kbd_dist_phon = keyboard_weighted_distance(token_phonetic, anchor_phonetic, max_keyboard_dist)
    if kbd_dist_phon <= max_keyboard_dist:
        return label
    
    # Strategy 4: N-gram similarity
    ngram_score = ngram_similarity(token_lower, anchor_lower, n=3)
    if ngram_score >= min_ngram_score:
        return label
    
    return None


# ---------------------------------------------------------------------------
# 6. MAIN RESCUE FUNCTION (drop-in replacement)
# ---------------------------------------------------------------------------

def advanced_fuzzy_rescue(
    normalized_text: str,
    detected: List[str],
    negated_labels: set,
    wellness_negated: set,
    dict_words: Set[str],
    neg_words: Set[str],
    fuzzy_token_is_negated_fn
) -> None:
    """
    Advanced fuzzy rescue using phonetic + keyboard-aware + n-gram matching.
    
    This is a drop-in replacement for _fuzzy_symptom_rescue in step1.py.
    
    Args:
        normalized_text: Pre-normalized user input
        detected: List of already detected labels (modified in place)
        negated_labels: Set of negated labels (modified in place)
        wellness_negated: Set of wellness-negated labels
        dict_words: Dictionary word set (skip real words)
        neg_words: Negation words (skip negators)
        fuzzy_token_is_negated_fn: Function to check token negation
    """
    for token in normalized_text.split():
        # Skip short tokens, non-alpha, dictionary words, negators
        if len(token) < 3 or not token.isalpha():
            continue
        if token in dict_words or token in neg_words:
            continue
        
        # Try each anchor
        for anchor, label, max_dist, variants in _ADVANCED_ANCHORS:
            # Skip if already detected/negated
            if label in detected or label in negated_labels or label in wellness_negated:
                continue
            
            # Try advanced matching
            matched_label = advanced_fuzzy_match(
                token, anchor, label, max_dist, variants, min_ngram_score=0.55
            )
            
            if matched_label:
                # Check negation
                if fuzzy_token_is_negated_fn(normalized_text, token):
                    negated_labels.add(label)
                    break
                
                detected.append(label)
                break


# ---------------------------------------------------------------------------
# 7. UTILITY: Get matching details for debugging/logging
# ---------------------------------------------------------------------------

def get_match_details(token: str, anchor: str) -> dict:
    """
    Return detailed matching scores for debugging.
    
    Returns dict with:
        - exact_match: bool
        - phonetic_match: bool
        - keyboard_distance: float
        - ngram_similarity: float
        - token_phonetic: str
        - anchor_phonetic: str
    """
    token_lower = token.lower()
    anchor_lower = anchor.lower()
    token_phon = phonetic_normalize(token_lower)
    anchor_phon = phonetic_normalize(anchor_lower)
    
    return {
        "exact_match": token_lower == anchor_lower,
        "phonetic_match": token_phon == anchor_phon,
        "keyboard_distance": keyboard_weighted_distance(token_lower, anchor_lower, max_dist=5.0),
        "ngram_similarity": ngram_similarity(token_lower, anchor_lower, n=3),
        "token_phonetic": token_phon,
        "anchor_phonetic": anchor_phon,
    }
