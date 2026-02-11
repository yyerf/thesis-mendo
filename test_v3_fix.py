"""Quick test to verify V3 model label mapping fix."""

import os
os.environ["MENDO_ML_VERSION"] = "v3"  # Force V3 model usage

from mendo_core.step3_hybrid import extract_symptoms_hybrid_report
from mendo_core.step4_recommend import load_mendo_dataset, recommend_from_dataset, DATASET_DEFAULT

def test_v3_recommendations():
    """Test that V3 model produces recommendations."""
    
    test_cases = [
        ("I have a cough and fever", 25),
        ("Masakit ulo ko", 30),
        ("May ubo at lagnat ako", 20),
        ("Coughing with phlegm", 25),
        ("Nahihilo at sumasakit ang ulo", 28),
    ]
    
    rows = load_mendo_dataset(DATASET_DEFAULT)
    
    print("=" * 80)
    print("V3 MODEL LABEL MAPPING FIX TEST")
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
        
        print(f"Detected symptoms: {detected}")
        print(f"Detection source: {source}")
        
        # Get recommendations
        rec = recommend_from_dataset(detected, rows, user_age=age, user_input=text)
        
        action = rec.get("action", "unknown")
        print(f"Recommendation action: {action}")
        
        if action == "recommend":
            recommendations = rec.get("recommendations", [])
            print(f"Number of recommendations: {len(recommendations)}")
            if recommendations:
                print("\nTop 3 recommendations:")
                for i, r in enumerate(recommendations[:3], 1):
                    brand = r.get("brand", "Unknown")
                    generic = r.get("generic", "Unknown")
                    reasons = r.get("reasons", [])
                    print(f"  {i}. {brand} ({generic})")
                    print(f"     Reasons: {', '.join(reasons)}")
            else:
                print("⚠️  WARNING: No recommendations returned!")
        elif action == "ask_clarify":
            question = rec.get("question", "")
            print(f"Clarification needed: {question}")
        else:
            print(f"⚠️  WARNING: Unexpected action: {action}")
        
        # Check for warnings
        warnings = rec.get("warnings", [])
        if warnings:
            print(f"Warnings: {warnings}")
    
    print(f"\n{'=' * 80}")
    print("TEST COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    test_v3_recommendations()
