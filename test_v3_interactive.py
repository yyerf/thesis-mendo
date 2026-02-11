"""Quick interactive test for V3 model via command line."""

import os
os.environ["MENDO_ML_VERSION"] = "v3"

from mendo_core.step3_hybrid import extract_symptoms_hybrid_report
from mendo_core.step4_recommend import load_mendo_dataset, recommend_from_dataset, DATASET_DEFAULT

def interactive_test():
    """Interactive test of V3 model."""
    rows = load_mendo_dataset(DATASET_DEFAULT)
    
    print("\n" + "=" * 80)
    print("V3 MODEL INTERACTIVE TEST")
    print("=" * 80)
    print("Enter symptoms to test V3 model (or 'quit' to exit)")
    print("Example inputs:")
    print("  - My head is pounding")
    print("  - I'm burning up")
    print("  - Can't stop coughing")
    print("  - Masakit ulo ko")
    print("=" * 80 + "\n")
    
    while True:
        try:
            text = input("Symptoms> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break
        
        if not text or text.lower() in ['quit', 'exit', 'q']:
            print("Exiting...")
            break
        
        # Get symptom detection
        report = extract_symptoms_hybrid_report(
            text,
            semantic_threshold=0.65,
            semantic_top_margin=0.08,
            semantic_max_symptoms=3,
            enable_semantic_fallback=True,
        )
        
        detected = report.get("final", {}).get("symptoms", [])
        source = report.get("final", {}).get("source", "unknown")
        
        print(f"\n  Detected: {detected}")
        print(f"  Source: {source}")
        
        # Get recommendations
        rec = recommend_from_dataset(detected, rows, user_age=25, user_input=text)
        
        action = rec.get("action", "unknown")
        
        if action == "recommend":
            recommendations = rec.get("recommendations", [])
            print(f"  ✅ {len(recommendations)} recommendation(s):")
            for i, r in enumerate(recommendations[:5], 1):
                brand = r.get("brand", "Unknown")
                generic = r.get("generic", "Unknown")
                print(f"     {i}. {brand} ({generic})")
        elif action == "ask_clarify":
            question = rec.get("question", "")
            print(f"  ℹ️  Clarification: {question}")
        else:
            print(f"  ⚠️  No recommendations")
        
        print()

if __name__ == "__main__":
    interactive_test()
