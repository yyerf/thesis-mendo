"""
3-Way Comparison: Baseline vs ML v1 vs ML v2

Tests three versions of the symptom detection system:
1. BASELINE: Dictionary + Semantic only (no ML)
2. ML V1: With classifier trained on 2,170 samples
3. ML V2: With classifier trained on 3,670 samples

Focus: Typo handling, slang detection, multilingual support
"""

import json
import os
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_with_version(text: str, ml_version: str = None):
    """Test with specific ML version."""
    # Set environment variable
    if ml_version:
        os.environ["MENDO_ML_VERSION"] = ml_version
    else:
        os.environ.pop("MENDO_ML_VERSION", None)
    
    # Force reload of module to pick up new environment
    import importlib
    import mendo_core.step3_hybrid as step3
    importlib.reload(step3)
    
    # Reset global state
    step3._ML_CLASSIFIER = None
    step3._ML_VECTORIZER = None
    step3._ML_LABEL_BINARIZER = None
    step3._ML_VERSION = None
    
    result = step3.extract_symptoms_hybrid_report(
        text,
        semantic_threshold=0.65,
        semantic_top_margin=0.08,
        semantic_max_symptoms=2,
        enable_semantic_fallback=True
    )
    
    return result["final"]["symptoms"], result["final"]["source"]


def run_comparison():
    """Run comprehensive 3-way comparison."""
    
    test_cases = [
        # Typos
        ("sepun ako", ["runny_nose"], "Tagalog typo"),
        ("ubu ako grabe", ["cough"], "Tagalog typo (ubo)"),
        ("hedache ko", ["headache"], "English typo"),
        ("lagnt ako", ["fever"], "Tagalog typo (lagnat)"),
        ("masaket ulo", ["headache"], "Typo (masakit)"),
        
        # Slang/Colloquial
        ("grabi ubu ko sis", ["cough"], "Slang + typo"),
        ("shuta sakit ulo ko mars", ["headache"], "Slang"),
        ("sepun ako besh", ["runny_nose"], "Slang + typo"),
        
        # Correct spellings (should work in all versions)
        ("masakit ulo ko", ["headache"], "Correct Tagalog"),
        ("may sipon ako", ["runny_nose"], "Correct Tagalog"),
        ("umuubo ako", ["cough"], "Correct Tagalog"),
        
        # Cebuano
        ("sakit ulo ko karon", ["headache"], "Cebuano"),
        ("gihilantan ko", ["fever"], "Cebuano"),
        ("moubo ko", ["cough"], "Cebuano"),
        
        # Mixed/Complex
        ("init init katawan ko", ["fever"], "Natural expression"),
        ("parang binibiyak ulo ko", ["headache"], "Metaphor"),
    ]
    
    print("="*80)
    print("🔬 3-WAY SYMPTOM DETECTION COMPARISON")
    print("="*80)
    print("\nVersions:")
    print("  1️⃣  BASELINE: Dictionary + Semantic (no ML)")
    print("  2️⃣  ML V1: Trained on 2,170 samples (91.2% F1)")
    print("  3️⃣  ML V2: Trained on 3,670 samples (74.8% F1)")
    print("\n" + "="*80)
    
    baseline_correct = 0
    v1_correct = 0
    v2_correct = 0
    
    for text, expected, description in test_cases:
        print(f"\n📝 TEST: {text}")
        print(f"   Description: {description}")
        print(f"   Expected: {expected}")
        
        # Baseline (no ML - disable by using non-existent version)
        baseline_result, baseline_source = test_with_version(text, "none")
        baseline_match = set(baseline_result) == set(expected)
        if baseline_match:
            baseline_correct += 1
        
        # ML V1
        v1_result, v1_source = test_with_version(text, "v1")
        v1_match = set(v1_result) == set(expected)
        if v1_match:
            v1_correct += 1
        
        # ML V2
        v2_result, v2_source = test_with_version(text, "v2")
        v2_match = set(v2_result) == set(expected)
        if v2_match:
            v2_correct += 1
        
        check = lambda x: "✅" if x else "❌"
        print(f"\n   1️⃣  Baseline: {baseline_result} ({baseline_source[:12]}) {check(baseline_match)}")
        print(f"   2️⃣  ML V1:    {v1_result} ({v1_source[:12]}) {check(v1_match)}")
        print(f"   3️⃣  ML V2:    {v2_result} ({v2_source[:12]}) {check(v2_match)}")
    
    print("\n" + "="*80)
    print("📊 FINAL RESULTS")
    print("="*80)
    total = len(test_cases)
    print(f"\n1️⃣  BASELINE: {baseline_correct}/{total} correct ({baseline_correct/total:.1%})")
    print(f"2️⃣  ML V1:    {v1_correct}/{total} correct ({v1_correct/total:.1%})")
    print(f"3️⃣  ML V2:    {v2_correct}/{total} correct ({v2_correct/total:.1%})")
    
    print("\n💡 INSIGHTS:")
    if v2_correct > v1_correct:
        print("   ✅ V2 performs BETTER on typos/slang despite lower overall F1!")
    elif v2_correct == v1_correct:
        print("   ⚖️  V2 performs EQUALLY to V1 on typos/slang")
    else:
        print("   ⚠️  V2 performs WORSE - may need dataset review")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    run_comparison()
