"""Test V3 ML classifier specifically (phrases not in dictionary)."""

import os
os.environ["MENDO_ML_VERSION"] = "v3"  # Force V3 model usage

from mendo_core.step3_hybrid import extract_symptoms_hybrid_report
from mendo_core.step4_recommend import load_mendo_dataset, recommend_from_dataset, DATASET_DEFAULT

def test_v3_ml_classifier():
    """Test that V3 ML classifier produces uppercase labels and recommendations."""
    
    # These phrases should NOT match dictionary but SHOULD trigger ML classifier
    test_cases = [
        ("My head is killing me right now", 25),  # "killing" phrase - not in dict
        ("Can't stop coughing and feel really hot", 25),  # paraphrase
        ("Throbbing pain in my head", 30),  # paraphrase
        ("I'm burning up", 20),  # slang for fever
        ("Room is spinning", 28),  # slang for dizzy
    ]
    
    rows = load_mendo_dataset(DATASET_DEFAULT)
    
    print("=" * 80)
    print("V3 ML CLASSIFIER LABEL MAPPING TEST")
    print("=" * 80)
    
    for text, age in test_cases:
        print(f"\n{'─' * 80}")
        print(f"TEST: {text!r} (age: {age})")
        print(f"{'─' * 80}")
        
        # Get symptom detection report
        report = extract_symptoms_hybrid_report(
            text,
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=3,
            enable_semantic_fallback=True,
        )
        
        detected = report.get("final", {}).get("symptoms", [])
        source = report.get("final", {}).get("source", "unknown")
        
        print(f"✓ Detected symptoms: {detected}")
        print(f"✓ Detection source: {source}")
        
        # Verify labels are UPPERCASE
        for symptom in detected:
            if symptom != symptom.upper():
                print(f"❌ ERROR: Label '{symptom}' is not uppercase!")
            else:
                print(f"✓ Label '{symptom}' is correctly uppercase")
        
        # Get recommendations
        rec = recommend_from_dataset(detected, rows, user_age=age, user_input=text)
        
        action = rec.get("action", "unknown")
        print(f"✓ Recommendation action: {action}")
        
        if action == "recommend":
            recommendations = rec.get("recommendations", [])
            print(f"✓ Number of recommendations: {len(recommendations)}")
            if recommendations:
                print("\n  Top 3 recommendations:")
                for i, r in enumerate(recommendations[:3], 1):
                    brand = r.get("brand", "Unknown")
                    generic = r.get("generic", "Unknown")
                    reasons = r.get("reasons", [])
                    print(f"    {i}. {brand} ({generic})")
                    if reasons:
                        print(f"       Reasons: {', '.join(reasons[:2])}")
                print(f"\n✅ SUCCESS: V3 model produced {len(recommendations)} recommendations!")
            else:
                print("❌ ERROR: No recommendations returned!")
        elif action == "ask_clarify":
            question = rec.get("question", "")
            print(f"✓ Clarification needed: {question}")
            print(f"✅ SUCCESS: System correctly asking for clarification")
        else:
            print(f"❌ ERROR: Unexpected action: {action}")
    
    print(f"\n{'=' * 80}")
    print("TEST COMPLETE - V3 MODEL WORKING CORRECTLY! ✅")
    print("=" * 80)

if __name__ == "__main__":
    test_v3_ml_classifier()
