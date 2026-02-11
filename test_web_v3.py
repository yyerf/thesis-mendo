"""Test web app endpoint with V3 model."""

import os
os.environ["MENDO_ML_VERSION"] = "v3"

from web.app import app

def test_web_interface():
    """Test the web app recommendation endpoint."""
    
    with app.test_client() as client:
        test_cases = [
            {
                "text": "My head is pounding",
                "age": 25,
                "cough_type": None
            },
            {
                "text": "I'm burning up and my head hurts",
                "age": 30,
                "cough_type": None
            },
            {
                "text": "Can't stop coughing",
                "age": 25,
                "cough_type": "dry"
            }
        ]
        
        print("=" * 80)
        print("WEB APP V3 MODEL TEST")
        print("=" * 80)
        
        for test_data in test_cases:
            print(f"\n{'─' * 80}")
            print(f"Input: {test_data['text']!r}")
            print(f"Age: {test_data['age']}, Cough Type: {test_data['cough_type']}")
            print(f"{'─' * 80}")
            
            # Simulate the API call
            from web.app import _compute_recommendation
            
            result = _compute_recommendation(
                text=test_data["text"],
                age=test_data["age"],
                cough_type=test_data["cough_type"],
                debug=True,
                show_flow=True
            )
            
            if result.get("ok") == False:
                print(f"❌ ERROR: {result.get('error')}")
                continue
            
            # Check if we got recommendations
            recs = result.get("recommendations", [])
            clarify = result.get("clarify", {})
            
            if clarify.get("needed"):
                print(f"✓ Clarification needed: {clarify.get('question')}")
            elif recs:
                print(f"✅ SUCCESS: Got {len(recs)} recommendations")
                for i, rec in enumerate(recs[:3], 1):
                    print(f"  {i}. {rec.get('brand')} - {rec.get('generic')}")
                    print(f"     Age: {rec.get('age_dosage', 'N/A')}")
            else:
                print(f"⚠️  No recommendations (might be expected for some symptoms)")
        
        print(f"\n{'=' * 80}")
        print("WEB APP TEST COMPLETE ✅")
        print("=" * 80)

if __name__ == "__main__":
    test_web_interface()
