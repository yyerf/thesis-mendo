"""Find optimal threshold for V2 model."""
import joblib

v1 = joblib.load("training/symptom_classifier_v1.joblib")
v2 = joblib.load("training/symptom_classifier_v2.joblib")

# Test cases with expected labels
test_cases = [
    ("sepun ako", ["runny_nose"]),
    ("masaket ulo", ["headache"]),
    ("lagnt ko", ["fever"]),
    ("init init katawan", ["fever"]),
    ("ubu ako grabe", ["cough"]),  # This might fail
    ("moubo ko", ["cough"]),  # This might fail
]

print("="*70)
print("🔍 FINDING OPTIMAL THRESHOLD FOR V2")
print("="*70)

# Test different thresholds
thresholds = [0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]

for threshold in thresholds:
    correct = 0
    print(f"\n📊 Testing threshold = {threshold:.2f}")
    
    for text, expected in test_cases:
        X = v2['vectorizer'].transform([text])
        probs = v2['classifier'].predict_proba(X)[0]
        
        predicted = [
            v2['label_binarizer'].classes_[i]
            for i, p in enumerate(probs)
            if p >= threshold
        ]
        
        is_correct = any(label in predicted for label in expected)
        if is_correct:
            correct += 1
            print(f"  ✅ '{text}' → {predicted}")
        else:
            print(f"  ❌ '{text}' → {predicted} (expected {expected})")
    
    accuracy = correct / len(test_cases) * 100
    print(f"  🎯 Accuracy: {correct}/{len(test_cases)} ({accuracy:.1f}%)")

print("\n" + "="*70)
print("💡 RECOMMENDATION:")
print("="*70)

# Now compare V1 vs V2 at optimal thresholds
print("\n🔬 V1 (threshold=0.5) vs V2 (threshold=0.3):")
v1_correct = 0
v2_correct = 0

for text, expected in test_cases:
    # V1 prediction
    X_v1 = v1['vectorizer'].transform([text])
    probs_v1 = v1['classifier'].predict_proba(X_v1)[0]
    pred_v1 = [v1['label_binarizer'].classes_[i] for i, p in enumerate(probs_v1) if p >= 0.5]
    
    # V2 prediction
    X_v2 = v2['vectorizer'].transform([text])
    probs_v2 = v2['classifier'].predict_proba(X_v2)[0]
    pred_v2 = [v2['label_binarizer'].classes_[i] for i, p in enumerate(probs_v2) if p >= 0.3]
    
    v1_match = any(label in pred_v1 for label in expected)
    v2_match = any(label in pred_v2 for label in expected)
    
    if v1_match: v1_correct += 1
    if v2_match: v2_correct += 1
    
    symbol_v1 = "✅" if v1_match else "❌"
    symbol_v2 = "✅" if v2_match else "❌"
    
    print(f"  '{text}':")
    print(f"    V1 (0.5): {symbol_v1} {pred_v1}")
    print(f"    V2 (0.3): {symbol_v2} {pred_v2}")

print(f"\n🎯 FINAL COMPARISON:")
print(f"   V1 (threshold=0.5): {v1_correct}/{len(test_cases)} ({v1_correct/len(test_cases)*100:.1f}%)")
print(f"   V2 (threshold=0.3): {v2_correct}/{len(test_cases)} ({v2_correct/len(test_cases)*100:.1f}%)")

if v2_correct >= v1_correct:
    print(f"\n✅ V2 is BETTER with threshold=0.3!")
    print("   → Update V2 model to use threshold=0.3")
else:
    print(f"\n⚠️  V1 is still better even with optimized threshold")
    print("   → V2 needs dataset review and retraining")
